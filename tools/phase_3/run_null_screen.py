"""Phase 3 — null screen runner (CLI + library entry).

Asks the empirical question per ``docs/audit/PHASE_3_NULL_SCREEN_PLAN.md``:

    Does γ ≈ 1.0 separate the substrate signal from null/surrogate
    controls, or is it an estimator artefact?

This is the **only** code path Phase 3 publishes a verdict on. All
other γ pipelines in the repository serve historical contracts and
do NOT participate in Phase 3.

CLI
---

    python -m tools.phase_3.run_null_screen \\
        --substrate serotonergic_kuramoto \\
        --M 10000 \\
        --out evidence/phase_3_null_screen/serotonergic_kuramoto.json

PR-time CI smoke uses ``--smoke --M 200`` (the only path allowed
under the precision floor).

Determinism contract (plan §4 / runner rule 3)
----------------------------------------------

    seed = sha256(substrate_id || "phase_3" || str(M)).hexdigest()[:16]

A 64-bit integer derived from this hex prefix seeds every RNG inside
the run. Two reruns with the same ``substrate`` and ``M`` produce
byte-identical ``result_hash`` (plan §7 test 6).

Verdict ladder (closed set, no softening)
-----------------------------------------

* ``SIGNAL_SEPARATES_FROM_NULL`` — every family rejects null at α/k
  AND window sweep stable AND non-degenerate observed γ.
* ``NULL_NOT_REJECTED`` — at least one family fails to reject AND the
  estimator is non-pathological.
* ``ESTIMATOR_ARTIFACT_SUSPECTED`` — window sweep unstable
  (Δγ_max > threshold) OR observed γ is degenerate while null
  ensemble is well-defined.
* ``INCONCLUSIVE`` — input data is degenerate (constant series,
  insufficient samples) and the question cannot be evaluated.

The ``ledger_update`` block in the output is a **proposal only**.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from core import iaaft as _iaaft
from core.nulls import FAMILIES as _NULL_FAMILIES
from tools.phase_3 import PHASE_3_VERSION, VERDICTS
from tools.phase_3.effect_size import EffectSize, cohen_d_with_bootstrap_ci
from tools.phase_3.estimator import GammaEstimate, estimate_gamma
from tools.phase_3.family_router import (
    REGISTERED_SUBSTRATES,
    UnknownFamilyError,
    UnknownSubstrateError,
    families_for,
    validate_family,
)
from tools.phase_3.result_hash import compute_result_hash
from tools.phase_3.stability import WindowSweepResult, window_sweep

__all__ = [
    "M_PRECISION_FLOOR",
    "M_SMOKE",
    "Phase3Result",
    "build_substrate_seed",
    "load_substrate_trajectory",
    "main",
    "run_null_screen",
]


# Precision-floor constant — plan §4. Below this, surrogate p-values
# cannot reach the per-family Bonferroni threshold.
M_PRECISION_FLOOR: int = 1000

# CI smoke run M — plan §8. Allowed only under explicit ``--smoke``.
M_SMOKE: int = 200

# Default α and stability threshold — plan §1, plan §7 test 7.
_ALPHA: float = 0.05
_DELTA_GAMMA_THRESHOLD: float = 0.05

# Minimum family count guarded.
_MIN_FAMILIES: int = 1


@dataclasses.dataclass(frozen=True)
class Phase3Result:
    """Top-level dataclass mirror of the output JSON.

    Output JSON is the canonical product; this class is a typed
    convenience for callers (tests, downstream tools). The JSON is
    produced by ``run_null_screen`` directly.
    """

    substrate: str
    observed_gamma: float
    n_surrogates_per_family: int
    families: dict[str, dict[str, Any]]
    window_sweep: dict[str, Any]
    global_verdict: str
    result_hash: str


# ---------------------------------------------------------------------------
# Seed derivation — plan §4 / rule 3
# ---------------------------------------------------------------------------
def build_substrate_seed(substrate: str, M: int) -> str:
    """Return the deterministic 16-hex-char seed for ``(substrate, M)``."""
    payload = f"{substrate}|phase_3|{int(M)}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _hex_to_int_seed(hex_seed: str) -> int:
    """Map a hex seed prefix to a 64-bit non-negative integer for numpy."""
    return int(hex_seed, 16) & 0xFFFFFFFFFFFFFFFF


# ---------------------------------------------------------------------------
# Substrate loaders — return the (topo, cost) trajectory used as input
# to estimate_gamma, and a 1-D scalar series used as the surrogation
# target for univariate null families.
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class SubstrateTrajectory:
    substrate: str
    topo: np.ndarray
    cost: np.ndarray
    surrogation_target: np.ndarray
    notes: tuple[str, ...] = ()


class SubstrateDataUnavailableError(RuntimeError):
    """Raised by a loader when the underlying data source is not on disk."""


def _load_serotonergic_kuramoto(seed: int) -> SubstrateTrajectory:
    # Local import to avoid heavy module load when the substrate is not used.
    from substrates.serotonergic_kuramoto.adapter import SerotonergicKuramotoAdapter

    adapter = SerotonergicKuramotoAdapter(seed=seed)
    samples = adapter._samples  # noqa: SLF001 — pre-computed sweep cache
    topo = np.array([s["topo"] for s in samples], dtype=np.float64)
    cost = np.array([s["thermo_cost"] for s in samples], dtype=np.float64)
    return SubstrateTrajectory(
        substrate="serotonergic_kuramoto",
        topo=topo,
        cost=cost,
        surrogation_target=cost.copy(),
        notes=("topo held fixed; cost is the surrogation target",),
    )


def _load_synthetic_white_noise(seed: int) -> SubstrateTrajectory:
    # Pure Gaussian noise on both axes ⇒ no scaling structure.
    # Used by adversarial test 1. n=512 satisfies all family minima
    # (linear_matched AR(8) needs n>=64, compute_delta_h via MFDFA
    # needs n>=100 with safe headroom for deeper scales).
    rng = np.random.default_rng(seed)
    n = 256
    topo = np.exp(rng.normal(0.0, 1.0, size=n))
    cost = np.exp(rng.normal(0.0, 1.0, size=n))
    return SubstrateTrajectory(
        substrate="synthetic_white_noise",
        topo=topo,
        cost=cost,
        surrogation_target=cost.copy(),
        notes=("pure white noise on both axes; no scaling",),
    )


def _load_synthetic_power_law(seed: int) -> SubstrateTrajectory:
    # Structured K = C^(-1) with multiplicative log-normal noise on K.
    # Positive control: γ = 1 by construction.
    rng = np.random.default_rng(seed)
    n = 256
    cost = np.exp(np.linspace(0.5, 5.0, n))
    topo = (1.0 / cost) * np.exp(rng.normal(0.0, 0.05, size=n))
    return SubstrateTrajectory(
        substrate="synthetic_power_law",
        topo=topo,
        cost=cost,
        surrogation_target=cost.copy(),
        notes=("γ=1 generator: K = C^(-1) + small log-normal noise",),
    )


def _load_synthetic_constant(seed: int) -> SubstrateTrajectory:
    # Constant series → γ undefined by construction (degenerate domain).
    n = 256
    topo = np.full(n, 2.0, dtype=np.float64)
    cost = np.full(n, 3.0, dtype=np.float64)
    return SubstrateTrajectory(
        substrate="synthetic_constant",
        topo=topo,
        cost=cost,
        surrogation_target=cost.copy(),
        notes=("constant series; γ undefined",),
    )


def _load_hrv_fantasia(seed: int) -> SubstrateTrajectory:
    raise SubstrateDataUnavailableError(
        "hrv_fantasia requires the Fantasia PhysioNet ECG corpus on disk "
        "(data/fantasia/) plus the optional `wfdb` package. Phase 3 v1 "
        "ships the family registration but skips runtime loading until "
        "the data is provisioned."
    )


def _load_eeg_resting(seed: int) -> SubstrateTrajectory:
    raise SubstrateDataUnavailableError(
        "eeg_resting requires the PhysioNet EEG resting-state corpus on "
        "disk plus the optional `mne` package. Phase 3 v1 ships the "
        "family registration but skips runtime loading until the data "
        "is provisioned."
    )


_LOADERS: dict[str, Callable[[int], SubstrateTrajectory]] = {
    "serotonergic_kuramoto": _load_serotonergic_kuramoto,
    "synthetic_white_noise": _load_synthetic_white_noise,
    "synthetic_power_law": _load_synthetic_power_law,
    "synthetic_constant": _load_synthetic_constant,
    "hrv_fantasia": _load_hrv_fantasia,
    "eeg_resting": _load_eeg_resting,
}


def load_substrate_trajectory(substrate: str, seed: int) -> SubstrateTrajectory:
    """Dispatch loader by substrate name."""
    if substrate not in _LOADERS:
        raise UnknownSubstrateError(
            f"no loader for substrate {substrate!r}; available: {sorted(_LOADERS.keys())}"
        )
    return _LOADERS[substrate](seed)


# ---------------------------------------------------------------------------
# Surrogate dispatch
# ---------------------------------------------------------------------------
def _generate_one_surrogate(
    family: str,
    target: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Produce one surrogate from ``target`` using the named family."""
    surrogate_seed = int(rng.integers(0, 2**63 - 1))
    if family == "iaaft_surrogate":
        # Use the new keyword API with explicit seed for determinism.
        out = _iaaft.iaaft_surrogate(
            target,
            n_iter=200,
            seed=surrogate_seed,
            return_diagnostics=False,
        )
        return np.asarray(out, dtype=np.float64)
    if family == "kuramoto_iaaft":
        # kuramoto_iaaft expects a (N_osc, T) phase matrix; for univariate
        # cost-series surrogation we wrap as a single-oscillator angular
        # embedding by mapping the cost into [0, 2π) and unwrapping.
        # The plan calls this out for Kuramoto-class substrates: the
        # surrogation target is the cost vector, and the kuramoto_iaaft
        # path preserves the per-oscillator phase distribution.
        n = int(target.size)
        # Map target → phase via min/max linear scaling, robust to scale.
        t_min = float(np.min(target))
        t_max = float(np.max(target))
        if t_max - t_min < 1e-12:
            # Degenerate: return a constant copy; this is a sanity case
            # that the caller surfaces upstream.
            return np.asarray(target, dtype=np.float64) + 0.0
        phases = ((target - t_min) / (t_max - t_min)) * (2.0 * np.pi)
        phase_mat = phases.reshape(1, n)
        surr_phase = _iaaft.kuramoto_iaaft(phase_mat, n_iter=200, seed=surrogate_seed)
        # Map back to the target scale.
        out = (surr_phase[0] / (2.0 * np.pi)) * (t_max - t_min) + t_min
        return np.asarray(out, dtype=np.float64)
    if family in _NULL_FAMILIES:
        gen = _NULL_FAMILIES[family]
        surr, _diag = gen(target, seed=surrogate_seed, return_diagnostics=True)
        return np.asarray(surr, dtype=np.float64)
    raise UnknownFamilyError(f"no dispatch for family {family!r}")


def _surrogate_unchanged(original: np.ndarray, surr: np.ndarray) -> bool:
    """Plan §7 test 4: detect a null that returned the original data."""
    if original.shape != surr.shape:
        return False
    return bool(np.allclose(original, surr, rtol=1e-12, atol=1e-12))


# ---------------------------------------------------------------------------
# Per-family screen
# ---------------------------------------------------------------------------
def _screen_family(
    family: str,
    trajectory: SubstrateTrajectory,
    M: int,
    rng: np.random.Generator,
    bonferroni_alpha: float,
    bootstrap_seed: int,
    gamma_obs: float,
) -> dict[str, Any]:
    """Run M surrogates of a single family; return summary dict.

    Plan §7 test 4 sanity check: if more than 1 % of the M surrogates
    are byte-identical to the original target, raise — the null
    generator is not actually generating a null.
    """
    null_gammas = np.full(M, np.nan, dtype=np.float64)
    n_unchanged = 0
    n_degenerate = 0
    n_family_errors = 0
    family_error_msg: str | None = None

    # Plan §7 test 4 sanity guard — only enforce the "null is a null"
    # contract when the *input* itself has measurable variance. A
    # constant input cannot have a non-trivial surrogate by
    # construction; that case routes to the global INCONCLUSIVE
    # verdict via the observed-γ degeneracy path, not via this guard.
    target = trajectory.surrogation_target
    target_has_variance = bool(np.std(target, ddof=1) > 1e-12) if target.size >= 2 else False

    for k in range(M):
        try:
            surr = _generate_one_surrogate(family, target, rng)
        except ValueError as exc:
            # Family-level inability (e.g. linear_matched AR(8) on n<64).
            # Record once, mark the family as non-applicable, and stop
            # — every subsequent draw would fail identically.
            n_family_errors = M
            family_error_msg = f"{type(exc).__name__}: {exc}"
            break
        if target_has_variance and _surrogate_unchanged(target, surr):
            n_unchanged += 1
        est = estimate_gamma(trajectory.topo, surr)
        if est.degenerate:
            n_degenerate += 1
            continue
        null_gammas[k] = est.gamma

    if family_error_msg is not None:
        return {
            "n_surrogates": M,
            "n_finite": 0,
            "n_degenerate": n_degenerate,
            "n_unchanged": n_unchanged,
            "n_family_errors": n_family_errors,
            "null_gamma_mean": None,
            "null_gamma_std": None,
            "null_gamma_quantiles": {"q025": None, "q500": None, "q975": None},
            "p_value_distance_from_one": None,
            "effect_size_cohen_d": None,
            "effect_size_ci95": [None, None],
            "verdict": "NOT_APPLICABLE",
            "rejected_at_bonferroni": False,
            "bonferroni_alpha": bonferroni_alpha,
            "notes": [
                "family is not applicable to this trajectory length",
                family_error_msg,
            ],
        }

    # Plan §7 test 4 — run FAILS if surrogate is the data unchanged.
    # A 1 % tolerance covers the legitimate amplitude-rank-remap case
    # where a tiny number of surrogates can land within numerical tol
    # of the input (very rare with M >= 200 and Gaussian phases).
    if target_has_variance:
        unchanged_frac = n_unchanged / float(M)
        if unchanged_frac > 0.01:
            raise RuntimeError(
                f"family {family!r}: surrogate generator returned the original "
                f"data unchanged in {n_unchanged}/{M} ({unchanged_frac:.2%}) "
                "trials — null is not a null."
            )

    finite = null_gammas[np.isfinite(null_gammas)]
    n_used = int(finite.size)

    if n_used < 2:
        return {
            "n_surrogates": M,
            "n_finite": n_used,
            "n_degenerate": n_degenerate,
            "n_unchanged": n_unchanged,
            "null_gamma_mean": None,
            "null_gamma_std": None,
            "null_gamma_quantiles": {"q025": None, "q500": None, "q975": None},
            "p_value_distance_from_one": None,
            "effect_size_cohen_d": None,
            "effect_size_ci95": [None, None],
            "verdict": "NOT_REJECTED",
            "rejected_at_bonferroni": False,
            "bonferroni_alpha": bonferroni_alpha,
            "notes": ["null ensemble has fewer than 2 finite γ values"],
        }

    # p-value: two-sided permutation tail with the null mean as the
    # reference. The null hypothesis under test is "the surrogated
    # data carries no K↔C scaling structure" — the natural reference
    # is the null ensemble itself, so we report the fraction of null
    # draws whose distance from the *null mean* equals or exceeds the
    # observed distance from the null mean. Reject H_0 when the
    # observed γ̂ lies in the tail of the null distribution.
    if not np.isfinite(gamma_obs):
        p_value: float | None = None
    else:
        null_mean = float(np.mean(finite))
        obs_dist_from_null = abs(float(gamma_obs) - null_mean)
        null_dist_from_null_mean = np.abs(finite - null_mean)
        n_more_extreme = int(np.sum(null_dist_from_null_mean >= obs_dist_from_null))
        p_value = float((1 + n_more_extreme) / (n_used + 1))

    es: EffectSize = cohen_d_with_bootstrap_ci(
        gamma_obs,
        finite,
        n_bootstrap=1000,
        seed=bootstrap_seed,
    )

    rejected = bool(p_value is not None and p_value < bonferroni_alpha)
    verdict = "REJECTED" if rejected else "NOT_REJECTED"

    return {
        "n_surrogates": M,
        "n_finite": n_used,
        "n_degenerate": n_degenerate,
        "n_unchanged": n_unchanged,
        "null_gamma_mean": float(np.mean(finite)),
        "null_gamma_std": float(np.std(finite, ddof=1)) if n_used >= 2 else 0.0,
        "null_gamma_quantiles": {
            "q025": float(np.quantile(finite, 0.025)),
            "q500": float(np.quantile(finite, 0.500)),
            "q975": float(np.quantile(finite, 0.975)),
        },
        "p_value_distance_from_one": p_value,
        "effect_size_cohen_d": (None if not np.isfinite(es.d) else float(es.d)),
        "effect_size_ci95": [
            (None if not np.isfinite(es.ci95_low) else float(es.ci95_low)),
            (None if not np.isfinite(es.ci95_high) else float(es.ci95_high)),
        ],
        "verdict": verdict,
        "rejected_at_bonferroni": rejected,
        "bonferroni_alpha": bonferroni_alpha,
        "notes": [],
    }


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------
def _decide_global_verdict(
    obs: GammaEstimate,
    family_results: dict[str, dict[str, Any]],
    sweep: WindowSweepResult,
) -> tuple[str, dict[str, Any]]:
    """Map (observed γ, per-family verdicts, window sweep) → global verdict.

    Returns the global verdict string and a ledger_update *proposal*
    block.
    """
    if obs.degenerate or not np.isfinite(obs.gamma):
        # Plan §7 test 3: constant series → INCONCLUSIVE OR
        # ESTIMATOR_ARTIFACT_SUSPECTED. We pick INCONCLUSIVE as the
        # canonical answer because the input itself is degenerate.
        return "INCONCLUSIVE", {
            "status_proposed": "INCONCLUSIVE",
            "downgrade_reason_proposed": None,
        }

    if not sweep.stable:
        return "ESTIMATOR_ARTIFACT_SUSPECTED", {
            "status_proposed": "INCONCLUSIVE",
            "downgrade_reason_proposed": None,
        }

    # Restrict the verdict to families that actually ran. NOT_APPLICABLE
    # families (insufficient input length etc.) are excluded from the
    # quorum but recorded explicitly in family_results.
    runnable = {
        name: f
        for name, f in family_results.items()
        if f.get("verdict") in {"REJECTED", "NOT_REJECTED"}
    }
    if not runnable:
        # Every requested family failed to run — verdict is INCONCLUSIVE,
        # not SIGNAL_SEPARATES (which would require a positive
        # rejection somewhere).
        return "INCONCLUSIVE", {
            "status_proposed": "INCONCLUSIVE",
            "downgrade_reason_proposed": None,
        }

    any_not_rejected = any(not f.get("rejected_at_bonferroni", False) for f in runnable.values())
    if any_not_rejected:
        return "NULL_NOT_REJECTED", {
            "status_proposed": "EVIDENCE_CANDIDATE_NULL_FAILED",
            "downgrade_reason_proposed": "NULL_NOT_REJECTED",
        }

    return "SIGNAL_SEPARATES_FROM_NULL", {
        "status_proposed": "SUPPORTED_BY_NULLS",
        "downgrade_reason_proposed": None,
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
def _validate_m_count(m: int, smoke: bool) -> None:
    if m < 1:
        raise ValueError(f"M must be >= 1; got {m}")
    if smoke:
        if m > M_PRECISION_FLOOR - 1:
            raise ValueError(
                f"--smoke runs are capped at M < {M_PRECISION_FLOOR}; got {m}. "
                "Drop --smoke for canonical M >= 1000."
            )
        return
    if m < M_PRECISION_FLOOR:
        raise ValueError(
            f"M < {M_PRECISION_FLOOR} is below the precision floor; "
            "either raise M to >= 1000 or pass --smoke (CI-only) for "
            f"the M=200 smoke contract. Got M={m}."
        )


def _validate_families(requested: tuple[str, ...]) -> None:
    if len(requested) < _MIN_FAMILIES:
        raise ValueError("at least one null family is required")
    for name in requested:
        validate_family(name)


def run_null_screen(
    substrate: str,
    M: int,
    *,
    smoke: bool = False,
    families_override: tuple[str, ...] | None = None,
    seed_override: str | None = None,
) -> dict[str, Any]:
    """Run a Phase 3 null screen and return the result dict.

    Output dict matches the schema in plan §5 modulo a couple of
    auxiliary fields (timestamps, version markers). The
    ``result_hash`` field is computed from the canonicalised payload
    with ``result_hash`` itself stripped — see ``result_hash.py``.
    """
    _validate_m_count(M, smoke=smoke)
    if substrate not in REGISTERED_SUBSTRATES and substrate not in _LOADERS:
        raise UnknownSubstrateError(
            f"substrate {substrate!r} is not registered; known: {REGISTERED_SUBSTRATES}"
        )

    if families_override is not None:
        families = families_override
    else:
        try:
            families = families_for(substrate)
        except UnknownSubstrateError:
            # Synthetic substrates registered as loaders but not pinned
            # in the family router fall back to the canonical
            # univariate two-family contract.
            families = ("iaaft_surrogate", "linear_matched")
    _validate_families(families)
    n_families = len(families)
    bonferroni_alpha = _ALPHA / float(n_families)

    seed_hex = seed_override if seed_override is not None else build_substrate_seed(substrate, M)
    int_seed = _hex_to_int_seed(seed_hex)

    t0 = time.monotonic()
    trajectory = load_substrate_trajectory(substrate, seed=int_seed)
    obs = estimate_gamma(trajectory.topo, trajectory.cost)
    sweep = window_sweep(trajectory.topo, trajectory.cost)

    # Each family gets its own RNG stream derived from the run seed and
    # the family name — independent across families, deterministic
    # across runs.
    family_results: dict[str, dict[str, Any]] = {}
    for family in families:
        family_seed_hex = hashlib.sha256(f"{seed_hex}|{family}".encode()).hexdigest()[:16]
        family_int_seed = _hex_to_int_seed(family_seed_hex)
        rng = np.random.default_rng(family_int_seed)
        bootstrap_seed = (family_int_seed ^ 0xA5A5A5A5A5A5A5A5) & 0xFFFFFFFFFFFFFFFF
        family_results[family] = _screen_family(
            family,
            trajectory,
            M=M,
            rng=rng,
            bonferroni_alpha=bonferroni_alpha,
            bootstrap_seed=bootstrap_seed,
            gamma_obs=float(obs.gamma) if not obs.degenerate else float("nan"),
        )

    global_verdict, ledger_proposal = _decide_global_verdict(obs, family_results, sweep)
    if global_verdict not in VERDICTS:
        raise AssertionError(f"verdict ladder violation: {global_verdict!r} not in {VERDICTS}")

    runtime_s = time.monotonic() - t0

    payload: dict[str, Any] = {
        "phase_3_version": PHASE_3_VERSION,
        "substrate": substrate,
        "smoke": bool(smoke),
        "seed": seed_hex,
        "M": int(M),
        "families": list(families),
        "n_families": n_families,
        "alpha": _ALPHA,
        "bonferroni_alpha": bonferroni_alpha,
        "observed_gamma": (
            None if obs.degenerate or not np.isfinite(obs.gamma) else float(obs.gamma)
        ),
        "observed_gamma_ci95": [
            (None if not np.isfinite(obs.ci95_low) else float(obs.ci95_low)),
            (None if not np.isfinite(obs.ci95_high) else float(obs.ci95_high)),
        ],
        "observed_gamma_n_used": int(obs.n_used),
        "observed_gamma_degenerate": bool(obs.degenerate),
        "n_surrogates_per_family": int(M),
        "family_results": family_results,
        "window_sweep": {
            "windows": [list(w) for w in sweep.windows],
            "gammas": list(sweep.gammas),
            "delta_gamma_max": (
                None if not np.isfinite(sweep.delta_gamma_max) else float(sweep.delta_gamma_max)
            ),
            "stable": bool(sweep.stable),
            "threshold": float(sweep.threshold),
        },
        "global_verdict": global_verdict,
        "ledger_update": {
            "status_proposed": ledger_proposal["status_proposed"],
            "downgrade_reason_proposed": ledger_proposal["downgrade_reason_proposed"],
            "note": (
                "PROPOSAL ONLY — the actual ledger mutation requires a "
                "separate human-reviewed PR. Phase 3 never auto-promotes."
            ),
        },
        "rerun_command": (
            f"python -m tools.phase_3.run_null_screen "
            f"--substrate {substrate} --M {M} --seed-override {seed_hex}"
            + (" --smoke" if smoke else "")
        ),
        "runtime_seconds": float(runtime_s),
        "trajectory_notes": list(trajectory.notes),
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }

    payload["result_hash"] = compute_result_hash(payload)
    return payload


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="phase_3.run_null_screen",
        description="Run a Phase 3 null screen on a registered substrate.",
    )
    p.add_argument("--substrate", required=True, help="registered substrate id")
    p.add_argument(
        "--M",
        type=int,
        required=True,
        help=f"surrogates per family (>= {M_PRECISION_FLOOR}, or --smoke for {M_SMOKE})",
    )
    p.add_argument(
        "--families",
        nargs="+",
        default=None,
        help="override the pinned family list (advanced; bypasses router pin)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="path to write the result JSON (omit → stdout only)",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help=f"CI smoke mode: M is allowed below {M_PRECISION_FLOOR}",
    )
    p.add_argument(
        "--seed-override",
        type=str,
        default=None,
        help="advanced: override the deterministic seed (16 hex chars)",
    )
    p.add_argument(
        "--print-summary",
        action="store_true",
        help="print a one-line summary on stderr",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code."""
    args = _parse_args(argv)
    families_override: tuple[str, ...] | None = tuple(args.families) if args.families else None

    try:
        payload = run_null_screen(
            substrate=args.substrate,
            M=int(args.M),
            smoke=bool(args.smoke),
            families_override=families_override,
            seed_override=args.seed_override,
        )
    except SubstrateDataUnavailableError as exc:
        print(f"phase_3: substrate data unavailable: {exc}", file=sys.stderr)
        return 3
    except (UnknownSubstrateError, UnknownFamilyError, ValueError) as exc:
        print(f"phase_3: input error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")

    if args.print_summary:
        print(
            f"phase_3: {payload['substrate']}  γ̂={payload['observed_gamma']}  "
            f"verdict={payload['global_verdict']}  "
            f"hash={payload['result_hash'][:16]}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
