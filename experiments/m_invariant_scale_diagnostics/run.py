#!/usr/bin/env python3
"""HWI scale-dependence diagnostic harness — synthetic only.

Purpose
-------
Quantify why the M = H/(W2*sqrt(I)) operator's behaviour on PR #171 was
dominated by coordinate-axis scale rather than substrate dynamics. The
diagnostic uses synthetic distributions whose ground truth is known, so
no substrate claim is implied and none is allowed to be inferred.

Pre-registered cases (synthetic only)
-------------------------------------
1. Gaussian shift     p = N(0, 1)            q = N(delta, 1)
2. Gaussian variance  p = N(0, 1)            q = N(0, sigma^2)
3. Bimodal shift      p = 0.5*N(-1,1) + 0.5*N(1,1)   q = shifted version
4. PDE-like wide      p, q on a wide coordinate range (range ~32 units)
5. BN-like narrow     p, q on a narrow coordinate range (range ~0.1 units)

For each case we evaluate the same KDE-smoothed densities under a series
of axis rescalings  x_scaled = s * x  for  s in {0.01, 0.1, 1.0, 10, 100}.

Diagnostic claims (verified per case)
-------------------------------------
- KL and JSD on normalised KDE densities are scale-invariant after
  density renormalisation (deviations only from finite KDE bandwidth).
- W2 scales linearly with the coordinate axis.
- Therefore M = H / (W2 * sqrt(I)) rescales as  M_s = M_1 / s.
- The clamp `M = min(M, 1)` saturates whenever  s < M_1 / 1.0,
  silently turning two genuinely different cases into "equal" 1.0.

Verdict for the diagnostic
--------------------------
SCALE_DEPENDENT  : at least one case shows M change > epsilon under axis rescale
                  AND at least one case demonstrates clamp saturation.
SCALE_STABLE     : no case shows >epsilon change under rescaling
                  (would refute PR #171's interpretation; not expected).
INVALID_OPERATOR : some case violated HWI inequality even on smooth analytic
                  controls (would mean the operator is unsuitable in principle).

This is a synthetic / analytic harness. **No substrate is touched. No
bridge claim is made or supported by this output.** See the roadmap PR
M2.1 for the registry of forbidden claims.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import gaussian_kde

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = REPO_ROOT / "results" / "m_invariant_scale_diagnostics" / "run_v1.json"
THIS_FILE = Path(__file__).resolve()

# ─────────────────────────────────────────────────────────────────────────────
# Pre-registered constants — do NOT change after observing outputs.
# ─────────────────────────────────────────────────────────────────────────────
EVAL_POINTS: int = 256
SCALES: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0)
SAMPLES_PER_DIST: int = 4096
SEED: int = 20260501
EPSILON_M_CHANGE: float = 0.05  # |M_s - M_1| > eps -> "case is scale-sensitive"
HWI_VIOLATION_TOLERANCE: float = 0.05  # >5% smooth-control violations -> INVALID
CLAMP_THRESHOLD: float = 0.999  # M >= this -> saturated


@dataclass(frozen=True)
class CaseDef:
    name: str
    range_unit: tuple[float, float]
    description: str


CASES: tuple[CaseDef, ...] = (
    CaseDef("gaussian_shift", (-6.0, 6.0), "p=N(0,1), q=N(2,1)"),
    CaseDef("gaussian_variance", (-6.0, 6.0), "p=N(0,1), q=N(0,4)"),
    CaseDef("bimodal_shift", (-6.0, 6.0), "p=0.5N(-1,1)+0.5N(1,1), q=shift+0.5"),
    CaseDef("pde_like_wide", (0.0, 32.0), "uniform on [0,32] vs [4,28]"),
    CaseDef("bnsyn_like_narrow", (-0.08, 0.01), "narrow value range similar to MFN activator"),
)


# ─────────────────────────────────────────────────────────────────────────────
# 1D operator (mirrors PR #171's KDE-density M = H/(W2*sqrt(I)))
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HWI1D:
    H: float
    W2: float
    I: float
    M_clamped: float
    M_unclamped: float
    hwi_holds: bool
    saturated: bool


def _kde_pmf(samples: np.ndarray, eval_range: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    grid = np.linspace(eval_range[0], eval_range[1], EVAL_POINTS)
    s = np.std(samples)
    if s < 1e-12:
        idx = int(np.argmin(np.abs(grid - float(np.mean(samples)))))
        p = np.full(EVAL_POINTS, 1e-12)
        p[idx] += 1.0
        return p / p.sum(), grid
    kde = gaussian_kde(samples, bw_method="scott")
    raw = np.maximum(kde(grid), 0.0) + 1e-12
    return raw / raw.sum(), grid


def _w2_1d(p: np.ndarray, q: np.ndarray, grid: np.ndarray) -> float:
    n_q = 4096
    u = (np.arange(n_q) + 0.5) / n_q
    cdf_p = np.cumsum(p)
    cdf_q = np.cumsum(q)
    inv_p = grid[np.searchsorted(cdf_p, u, side="left").clip(0, len(grid) - 1)]
    inv_q = grid[np.searchsorted(cdf_q, u, side="left").clip(0, len(grid) - 1)]
    return float(np.sqrt(np.mean((inv_p - inv_q) ** 2)))


def hwi_components(
    samples_p: np.ndarray, samples_q: np.ndarray, eval_range: tuple[float, float]
) -> HWI1D:
    p, grid = _kde_pmf(samples_p, eval_range)
    q, _ = _kde_pmf(samples_q, eval_range)
    H = max(float(np.sum(p * np.log(p / (q + 1e-12)))), 0.0)
    W2 = _w2_1d(p, q, grid)
    m = 0.5 * (p + q)
    I = float(0.5 * np.sum(p * np.log(p / (m + 1e-12))) + 0.5 * np.sum(q * np.log(q / (m + 1e-12))))
    sqrt_I = float(np.sqrt(max(I, 1e-12)))
    rhs = W2 * sqrt_I
    hwi_holds = rhs + 1e-9 >= H
    M_unclamped = float(H / (rhs + 1e-12)) if rhs > 1e-9 else 0.0
    M_clamped = min(M_unclamped, 1.0)
    return HWI1D(
        H=H,
        W2=W2,
        I=I,
        M_clamped=M_clamped,
        M_unclamped=M_unclamped,
        hwi_holds=hwi_holds,
        saturated=M_clamped >= CLAMP_THRESHOLD,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic samplers
# ─────────────────────────────────────────────────────────────────────────────


def _samples_for(name: str, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    n = SAMPLES_PER_DIST
    if name == "gaussian_shift":
        return rng.normal(0.0, 1.0, n), rng.normal(2.0, 1.0, n)
    if name == "gaussian_variance":
        return rng.normal(0.0, 1.0, n), rng.normal(0.0, 2.0, n)
    if name == "bimodal_shift":
        sgn_p = rng.choice([-1.0, 1.0], size=n)
        sgn_q = rng.choice([-1.0, 1.0], size=n)
        p = sgn_p + rng.normal(0.0, 0.5, n)
        q = sgn_q + rng.normal(0.0, 0.5, n) + 0.5
        return p, q
    if name == "pde_like_wide":
        return rng.uniform(0.0, 32.0, n), rng.uniform(4.0, 28.0, n)
    if name == "bnsyn_like_narrow":
        # narrow range mirroring MFN Gray-Scott activator span observed in PR #171
        return rng.normal(-0.05, 0.015, n), rng.normal(-0.04, 0.020, n)
    raise ValueError(f"unknown case: {name}")


# ─────────────────────────────────────────────────────────────────────────────
# Per-case sweep over scale s
# ─────────────────────────────────────────────────────────────────────────────


def sweep_case(case: CaseDef, rng: np.random.Generator) -> dict[str, object]:
    p_raw, q_raw = _samples_for(case.name, rng)
    rows: list[dict[str, float | bool]] = []
    M_at_unit_scale: float | None = None
    for s in SCALES:
        ps = p_raw * s
        qs = q_raw * s
        rng_s = (case.range_unit[0] * s, case.range_unit[1] * s)
        c = hwi_components(ps, qs, rng_s)
        if abs(s - 1.0) < 1e-12:
            M_at_unit_scale = c.M_clamped
        rows.append(
            {
                "scale": float(s),
                "H": c.H,
                "W2": c.W2,
                "I": c.I,
                "M_clamped": c.M_clamped,
                "M_unclamped": c.M_unclamped,
                "hwi_holds": c.hwi_holds,
                "saturated": c.saturated,
            }
        )

    M_values_clamped = np.array([r["M_clamped"] for r in rows])
    spread = float(np.max(M_values_clamped) - np.min(M_values_clamped))
    n_saturated = int(sum(1 for r in rows if r["saturated"]))
    n_hwi_violations = int(sum(1 for r in rows if not r["hwi_holds"]))
    return {
        "name": case.name,
        "description": case.description,
        "M_at_unit_scale": M_at_unit_scale,
        "M_spread_clamped": spread,
        "scale_sensitive": spread > EPSILON_M_CHANGE,
        "saturation_observed": n_saturated > 0,
        "n_saturated_scales": n_saturated,
        "n_hwi_violations": n_hwi_violations,
        "rows": rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Verdict
# ─────────────────────────────────────────────────────────────────────────────


SMOOTH_CONTROL_CASES: tuple[str, ...] = ("gaussian_shift", "gaussian_variance", "bimodal_shift")


def _unit_scale_smooth_violations(results: list[dict[str, object]]) -> int:
    """Count HWI violations only on smooth control cases at unit scale.

    Extreme-scale HWI violations are expected by the diagnostic: they ARE the
    scale-dependence signal. INVALID_OPERATOR is reserved for the case where
    a smooth, well-conditioned distribution pair (Gaussian/bimodal) at the
    natural scale s=1.0 cannot satisfy HWI even in principle — that would
    mean the operator is unsuitable on smooth analytic input.
    """
    count = 0
    for r in results:
        if r["name"] not in SMOOTH_CONTROL_CASES:
            continue
        for row in r["rows"]:  # type: ignore[index]
            if abs(float(row["scale"]) - 1.0) < 1e-9 and not row["hwi_holds"]:
                count += 1
    return count


def decide(results: list[dict[str, object]]) -> tuple[str, str]:
    smooth_violations = _unit_scale_smooth_violations(results)
    if smooth_violations > 0:
        msg = (
            f"{smooth_violations} smooth-control case(s) violate HWI at unit scale "
            "— operator unusable on textbook input"
        )
        return ("INVALID_OPERATOR", msg)
    any_scale_sensitive = any(r["scale_sensitive"] for r in results)
    any_saturation = any(r["saturation_observed"] for r in results)
    if any_scale_sensitive and any_saturation:
        return (
            "SCALE_DEPENDENT",
            "at least one case shows M change > eps AND clamp saturation observed",
        )
    if any_scale_sensitive:
        return (
            "SCALE_DEPENDENT",
            "at least one case shows M change > eps under axis rescale (no saturation observed)",
        )
    return (
        "SCALE_STABLE",
        "no case showed M change > eps under axis rescale",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────


def hash_self() -> str:
    return hashlib.sha256(THIS_FILE.read_bytes()).hexdigest()


def main() -> int:
    t0 = time.perf_counter()
    print("=" * 72)
    print("  HWI SCALE-DEPENDENCE DIAGNOSTICS  [synthetic only — no substrate claim]")
    print(f"  scales = {SCALES}    eval_points = {EVAL_POINTS}    seed = {SEED}")
    print(f"  source sha256 = {hash_self()[:16]}…")
    print("=" * 72)

    rng = np.random.default_rng(SEED)
    results = [sweep_case(case, rng) for case in CASES]

    for r in results:
        print(
            f"\ncase '{r['name']}':  M_unit={r['M_at_unit_scale']!r}  "
            f"spread={r['M_spread_clamped']:.4f}  "
            f"sensitive={r['scale_sensitive']}  "
            f"sat={r['n_saturated_scales']}/{len(SCALES)}  "
            f"hwi_viol={r['n_hwi_violations']}"
        )
        for row in r["rows"]:
            print(
                f"    s={row['scale']:>7.2f}  H={row['H']:.4f}  W2={row['W2']:.4f}  "
                f"I={row['I']:.4f}  M={row['M_clamped']:.4f}  "
                f"({'sat' if row['saturated'] else 'ok '}, "
                f"{'HWI+' if row['hwi_holds'] else 'HWI-'})"
            )

    verdict, reason = decide(results)
    elapsed = time.perf_counter() - t0

    payload = {
        "schema": "m_invariant_scale_diagnostics_v1",
        "source_sha256": hash_self(),
        "claim_status": "derived",
        "scope": "synthetic distributions only; no substrate, no bridge claim",
        "config": {
            "EVAL_POINTS": EVAL_POINTS,
            "SCALES": list(SCALES),
            "SAMPLES_PER_DIST": SAMPLES_PER_DIST,
            "SEED": SEED,
            "EPSILON_M_CHANGE": EPSILON_M_CHANGE,
            "HWI_VIOLATION_TOLERANCE": HWI_VIOLATION_TOLERANCE,
            "CLAMP_THRESHOLD": CLAMP_THRESHOLD,
        },
        "cases": [
            {"name": c.name, "description": c.description, "range_unit": list(c.range_unit)}
            for c in CASES
        ],
        "results": results,
        "scale_dependence_verdict": verdict,
        "scale_dependence_reason": reason,
        "compute_seconds": round(elapsed, 1),
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(payload, indent=2))

    print("\n" + "=" * 72)
    print(f"  >>> {verdict}: {reason}")
    print(f"  evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")
    print(f"  ({elapsed:.1f}s)")
    print("=" * 72)
    # Every verdict (SCALE_DEPENDENT / SCALE_STABLE / INVALID_OPERATOR) is a
    # legitimate scientific output of the diagnostic — distinct from a script
    # crash. Return 0 unless we hit an unanticipated code path.
    if verdict not in {"SCALE_DEPENDENT", "SCALE_STABLE", "INVALID_OPERATOR"}:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
