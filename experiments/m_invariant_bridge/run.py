#!/usr/bin/env python3
"""M-invariant cross-substrate bridge: MFN <-> BN-Syn (1D-histogram operator).

Pre-registered hypothesis: M = H/(W2*sqrt(I)), reduced to its 1D specialisation
on a value histogram, gives a comparable value during the metastable /
pattern-formation phase across MFN Gray-Scott and BN-Syn AdEx spiking dynamics.

Pre-registration contract: contracts/M_INVARIANT_BNSYN_BRIDGE.yaml v1.1
Forbidden post-hoc actions (widen threshold, drop seeds, redefine window/bins,
swap I-proxy) are enumerated in that contract; this script must respect them.

Verdict semantics:
    PASS               relative_diff <= 0.20 AND both nulls outside band AND HWI holds >= 95%
    FAIL_OFFBAND       relative_diff > 0.20
    FAIL_NULL_LEAK     relative_diff <= 0.20 BUT a null lands inside band
    INVALID_HWI        HWI inequality violated on >= 5% of samples
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.stats import gaussian_kde

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "substrates" / "mfn" / "src"))
sys.path.insert(0, str(REPO_ROOT / "substrates" / "bn_syn" / "src"))

import mycelium_fractal_net as mfn

from bnsyn.config import AdExParams, CriticalityParams, SynapseParams
from bnsyn.rng import seed_all
from bnsyn.sim.network import Network, NetworkParams

# ─────────────────────────────────────────────────────────────────────────────
# PRE-REGISTERED CONSTANTS — mirror contracts/M_INVARIANT_BNSYN_BRIDGE.yaml v1.1
# Do NOT modify these after observing results. Any change requires v2 contract.
# ─────────────────────────────────────────────────────────────────────────────
THRESHOLD_REL: float = 0.20
HWI_VIOLATION_TOLERANCE: float = 0.05

EVAL_POINTS: int = 256
BNSYN_HIST_RANGE: tuple[float, float] = (-90.0, 30.0)
MFN_HIST_RANGE: tuple[float, float] = (0.0, 1.0)

N_NEURONS: int = 64
N_STEPS: int = 2000
DT_MS: float = 0.1
EXT_CURRENT_PA: float = 400.0
SEEDS: tuple[int, ...] = (42, 43, 44, 45, 46)
CAPTURE_STRIDE: int = 1

MFN_GRID: int = 32
MFN_STEPS: int = 60

CONTRACT_PATH = REPO_ROOT / "contracts" / "M_INVARIANT_BNSYN_BRIDGE.yaml"
EVIDENCE_PATH = REPO_ROOT / "results" / "m_invariant_bridge" / "run_v1.json"


@dataclass(frozen=True)
class MStats:
    M_morph: float
    M_mean: float
    M_std: float
    n_samples: int
    hwi_violation_frac: float
    M_trajectory: list[float]


# ─────────────────────────────────────────────────────────────────────────────
# 1D HWI / M operator on histograms with a meaningful position axis
# ─────────────────────────────────────────────────────────────────────────────


def _kde_density(snapshot: np.ndarray, eval_range: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """KDE-smooth the snapshot; return (density_pmf, eval_grid).

    Scott's-rule bandwidth via scipy.stats.gaussian_kde. The KDE is evaluated
    on a fixed `EVAL_POINTS`-grid over `eval_range` and renormalised to a
    discrete probability vector summing to 1. Constant-snapshot edge case
    (zero variance) falls back to a delta-bin at the snapshot mean.
    """
    flat = snapshot.ravel().astype(np.float64)
    grid = np.linspace(eval_range[0], eval_range[1], EVAL_POINTS)
    if np.std(flat) < 1e-9:
        # degenerate: place all mass on the closest grid point
        idx = int(np.clip(np.argmin(np.abs(grid - float(np.mean(flat)))), 0, EVAL_POINTS - 1))
        p = np.full(EVAL_POINTS, 1e-12)
        p[idx] += 1.0
        p /= p.sum()
        return p, grid
    kde = gaussian_kde(flat, bw_method="scott")
    raw = kde(grid).astype(np.float64)
    raw = np.maximum(raw, 0.0) + 1e-12
    p = raw / raw.sum()
    return p, grid


def _w2_1d(p: np.ndarray, q: np.ndarray, grid: np.ndarray) -> float:
    """Wasserstein-2 between two discrete densities on a shared 1D grid.

    Discrete W2 via inverse-CDF on a fine quantile probe. Both distributions
    live on the same `grid`, so positions are directly comparable.
    """
    n_q = 4096
    u = (np.arange(n_q) + 0.5) / n_q
    cdf_p = np.cumsum(p)
    cdf_q = np.cumsum(q)
    inv_p = grid[np.searchsorted(cdf_p, u, side="left").clip(0, len(grid) - 1)]
    inv_q = grid[np.searchsorted(cdf_q, u, side="left").clip(0, len(grid) - 1)]
    return float(np.sqrt(np.mean((inv_p - inv_q) ** 2)))


@dataclass(frozen=True)
class HWI1D:
    H: float
    W2: float
    I: float
    M: float
    hwi_holds: bool


def compute_hwi_1d(snapshot: np.ndarray, reference: np.ndarray, eval_range: tuple[float, float]) -> HWI1D:
    """Compute (H, W2, I, M) on KDE-smoothed value densities.

    H  = KL(p || q)         relative entropy on KDE densities
    W2 = W2(p, q)           1-D Wasserstein-2 on the eval grid
    I  = JSD(p, q)          symmetric bounded Fisher proxy (matches MFN)
    M  = H / (W2 * sqrt(I)) HWI saturation ratio, clamped to [0, 1]
    """
    p, grid = _kde_density(snapshot, eval_range)
    q, _ = _kde_density(reference, eval_range)

    # H = KL[p || q]
    H = float(np.sum(p * np.log(p / (q + 1e-12))))
    H = max(H, 0.0)

    W2 = _w2_1d(p, q, grid)

    m = 0.5 * (p + q)
    I = float(
        0.5 * np.sum(p * np.log(p / (m + 1e-12)))
        + 0.5 * np.sum(q * np.log(q / (m + 1e-12)))
    )

    sqrt_I = float(np.sqrt(max(I, 1e-12)))
    rhs = W2 * sqrt_I
    hwi_holds = rhs + 1e-6 >= H
    M = float(H / (rhs + 1e-10)) if rhs > 1e-6 else 0.0
    return HWI1D(H=H, W2=W2, I=I, M=min(M, 1.0), hwi_holds=hwi_holds)


# ─────────────────────────────────────────────────────────────────────────────
# Substrate drivers
# ─────────────────────────────────────────────────────────────────────────────


def simulate_bnsyn(seed: int) -> np.ndarray:
    """Drive deterministic BN-Syn; return V_history shape [T_samples, N]."""
    pack = seed_all(seed)
    net = Network(
        NetworkParams(N=N_NEURONS),
        AdExParams(),
        SynapseParams(),
        CriticalityParams(),
        dt_ms=DT_MS,
        rng=pack.np_rng,
    )
    injected = np.full(N_NEURONS, EXT_CURRENT_PA, dtype=np.float64)
    history: list[np.ndarray] = []
    for step in range(N_STEPS):
        net.step(external_current_pA=injected)
        if step % CAPTURE_STRIDE == 0:
            history.append(net.state.V_mV.copy())
    return np.asarray(history, dtype=np.float64)


def simulate_mfn(seed: int) -> np.ndarray:
    """Drive MFN Gray-Scott; return field history shape [T, grid, grid]."""
    seq = mfn.simulate(mfn.SimulationSpec(grid_size=MFN_GRID, steps=MFN_STEPS, seed=seed))
    return np.asarray(seq.history, dtype=np.float64)


# ─────────────────────────────────────────────────────────────────────────────
# M trajectory on a [T_samples, ...] history (reference = final snapshot)
# ─────────────────────────────────────────────────────────────────────────────


def _trajectory_indices(T_samples: int) -> list[int]:
    stride = max(1, (T_samples - 10) // 15)
    return list(range(10, T_samples - 1, stride))


def m_trajectory(history: np.ndarray, eval_range: tuple[float, float]) -> MStats:
    if history.ndim < 2:
        raise ValueError(f"history must have time as axis 0; got shape {history.shape}")
    T_samples = history.shape[0]
    if T_samples < 30:
        raise ValueError(f"history too short for stable M trajectory: {T_samples}")

    ref = history[-1]
    indices = _trajectory_indices(T_samples)
    M_values: list[float] = []
    hwi_violations = 0
    for t in indices:
        c = compute_hwi_1d(history[t], ref, eval_range)
        M_values.append(c.M)
        if not c.hwi_holds:
            hwi_violations += 1

    n = max(len(M_values), 1)
    half = max(1, n // 2)
    return MStats(
        M_morph=float(np.mean(M_values[:half])),
        M_mean=float(np.mean(M_values)),
        M_std=float(np.std(M_values)),
        n_samples=n,
        hwi_violation_frac=hwi_violations / n,
        M_trajectory=[round(v, 6) for v in M_values],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Nulls (must land outside the acceptance band per contract)
# ─────────────────────────────────────────────────────────────────────────────


def null_white_noise(seed: int, shape: tuple[int, ...], scale_to: tuple[float, float]) -> np.ndarray:
    """Gaussian noise rescaled to span the substrate's histogram range."""
    rng = np.random.default_rng(seed ^ 0xC0DECAFE)
    raw = rng.standard_normal(shape).astype(np.float64)
    # rescale so the noise actually populates the histogram axis (avoid degenerate single-bin null)
    lo, hi = scale_to
    centre = 0.5 * (lo + hi)
    span = 0.25 * (hi - lo)
    return centre + span * raw


def null_time_shuffled(history: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed ^ 0x1234ABCD)
    perm = rng.permutation(history.shape[0])
    return history[perm].copy()


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation + verdict (pure functions)
# ─────────────────────────────────────────────────────────────────────────────


def aggregate(per_seed: list[MStats]) -> dict[str, float | list[float] | int]:
    morph = np.array([s.M_morph for s in per_seed])
    full = np.array([s.M_mean for s in per_seed])
    viol = np.array([s.hwi_violation_frac for s in per_seed])
    return {
        "M_morph_mean": float(np.mean(morph)),
        "M_morph_std": float(np.std(morph)),
        "M_full_mean": float(np.mean(full)),
        "M_full_std": float(np.std(full)),
        "hwi_violation_frac_max": float(np.max(viol)),
        "n_seeds": len(per_seed),
        "M_morph_per_seed": [round(float(v), 6) for v in morph.tolist()],
    }


def relative_diff(a: float, ref: float) -> float:
    return abs(a - ref) / max(abs(ref), 1e-12)


def in_band(x: float, ref: float) -> bool:
    return relative_diff(x, ref) <= THRESHOLD_REL


def decide(
    bnsyn_agg: dict, wn_agg: dict, sh_agg: dict, mfn_agg: dict,
) -> tuple[str, str, dict[str, float]]:
    metrics = {
        "M_REF_1D_runtime": float(mfn_agg["M_morph_mean"]),
        "rel_diff_bnsyn": relative_diff(bnsyn_agg["M_morph_mean"], mfn_agg["M_morph_mean"]),
        "rel_diff_white_noise": relative_diff(wn_agg["M_morph_mean"], mfn_agg["M_morph_mean"]),
        "rel_diff_time_shuffled": relative_diff(sh_agg["M_morph_mean"], mfn_agg["M_morph_mean"]),
    }

    if any(
        a["hwi_violation_frac_max"] > HWI_VIOLATION_TOLERANCE
        for a in (bnsyn_agg, wn_agg, sh_agg, mfn_agg)
    ):
        return ("INVALID_HWI", "HWI inequality violated above tolerance", metrics)

    bn_in = in_band(bnsyn_agg["M_morph_mean"], mfn_agg["M_morph_mean"])
    if not bn_in:
        return (
            "FAIL_OFFBAND",
            f"rel_diff(BN-Syn vs MFN_1D) = {metrics['rel_diff_bnsyn']:.3f} > {THRESHOLD_REL}",
            metrics,
        )

    leaks: list[str] = []
    if in_band(wn_agg["M_morph_mean"], mfn_agg["M_morph_mean"]):
        leaks.append("white_noise")
    if in_band(sh_agg["M_morph_mean"], mfn_agg["M_morph_mean"]):
        leaks.append("time_shuffled")
    if leaks:
        return ("FAIL_NULL_LEAK", f"null(s) inside band: {', '.join(leaks)}", metrics)

    return ("PASS", "BN-Syn in-band; both nulls outside; HWI holds", metrics)


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────


def hash_contract() -> str:
    return hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()


def main() -> int:
    t_start = time.perf_counter()
    print("=" * 70)
    print("  M-INVARIANT BRIDGE: MFN(Gray-Scott) <-> BN-Syn(AdEx)  [1D operator]")
    print(f"  THRESHOLD_REL={THRESHOLD_REL}  EVAL_POINTS={EVAL_POINTS}  seeds={SEEDS}")
    print(f"  contract sha256 = {hash_contract()[:16]}...")
    print("=" * 70)

    # 1. MFN reference (re-measured with 1D operator — apples-to-apples)
    print("\n[1/4] MFN Gray-Scott (multi-seed, 1D operator)")
    mfn_per_seed: list[MStats] = []
    for seed in SEEDS:
        t0 = time.perf_counter()
        h = simulate_mfn(seed)
        s = m_trajectory(h, MFN_HIST_RANGE)
        mfn_per_seed.append(s)
        print(f"  seed={seed:>3d}  M_morph={s.M_morph:.6f}  M_mean={s.M_mean:.6f}  "
              f"hwi_viol={s.hwi_violation_frac:.3f}  ({time.perf_counter() - t0:.1f}s)")
    mfn_agg = aggregate(mfn_per_seed)

    # 2. BN-Syn substrate
    print("\n[2/4] BN-Syn V_mV trajectory (multi-seed)")
    bnsyn_per_seed: list[MStats] = []
    bnsyn_sample_shape: tuple[int, ...] | None = None
    for seed in SEEDS:
        t0 = time.perf_counter()
        h = simulate_bnsyn(seed)
        if bnsyn_sample_shape is None:
            bnsyn_sample_shape = h.shape
        s = m_trajectory(h, BNSYN_HIST_RANGE)
        bnsyn_per_seed.append(s)
        print(f"  seed={seed:>3d}  M_morph={s.M_morph:.6f}  M_mean={s.M_mean:.6f}  "
              f"hwi_viol={s.hwi_violation_frac:.3f}  ({time.perf_counter() - t0:.1f}s)")
    bnsyn_agg = aggregate(bnsyn_per_seed)
    assert bnsyn_sample_shape is not None

    # 3. Null #1: white noise on BN-Syn axis
    print("\n[3/4] Null #1: white noise on voltage axis (no temporal structure)")
    wn_per_seed: list[MStats] = []
    for seed in SEEDS:
        wn = null_white_noise(seed, bnsyn_sample_shape, BNSYN_HIST_RANGE)
        s = m_trajectory(wn, BNSYN_HIST_RANGE)
        wn_per_seed.append(s)
        print(f"  seed={seed:>3d}  M_morph={s.M_morph:.6f}  M_mean={s.M_mean:.6f}  "
              f"hwi_viol={s.hwi_violation_frac:.3f}")
    wn_agg = aggregate(wn_per_seed)

    # 4. Null #2: time-shuffled BN-Syn
    print("\n[4/4] Null #2: time-shuffled BN-Syn trajectory")
    sh_per_seed: list[MStats] = []
    for seed in SEEDS:
        h = simulate_bnsyn(seed)
        sh = null_time_shuffled(h, seed)
        s = m_trajectory(sh, BNSYN_HIST_RANGE)
        sh_per_seed.append(s)
        print(f"  seed={seed:>3d}  M_morph={s.M_morph:.6f}  M_mean={s.M_mean:.6f}  "
              f"hwi_viol={s.hwi_violation_frac:.3f}")
    sh_agg = aggregate(sh_per_seed)

    # 5. Verdict (pure of pre-registered constants)
    verdict, reason, metrics = decide(bnsyn_agg, wn_agg, sh_agg, mfn_agg)
    elapsed = time.perf_counter() - t_start

    payload = {
        "contract": "M_INVARIANT_BNSYN_MFN_BRIDGE_v1.1",
        "contract_sha256": hash_contract(),
        "claim_status": "derived",
        "threshold_relative": THRESHOLD_REL,
        "config": {
            "N_neurons": N_NEURONS, "N_steps": N_STEPS, "dt_ms": DT_MS,
            "external_current_pA": EXT_CURRENT_PA, "seeds": list(SEEDS),
            "capture_stride": CAPTURE_STRIDE, "mfn_grid": MFN_GRID,
            "mfn_steps": MFN_STEPS, "eval_points": EVAL_POINTS,
            "bnsyn_eval_range": list(BNSYN_HIST_RANGE),
            "mfn_eval_range": list(MFN_HIST_RANGE),
        },
        "mfn_1d": {"aggregate": mfn_agg, "per_seed": [asdict(s) for s in mfn_per_seed]},
        "bnsyn": {"aggregate": bnsyn_agg, "per_seed": [asdict(s) for s in bnsyn_per_seed]},
        "null_white_noise": {"aggregate": wn_agg, "per_seed": [asdict(s) for s in wn_per_seed]},
        "null_time_shuffled": {"aggregate": sh_agg, "per_seed": [asdict(s) for s in sh_per_seed]},
        "metrics": metrics,
        "verdict": verdict,
        "verdict_reason": reason,
        "compute_seconds": round(elapsed, 1),
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(payload, indent=2))

    print("\n" + "=" * 70)
    print("  VERDICT")
    print("=" * 70)
    print(f"  MFN_1D (Gray-Scott)  M_morph = {mfn_agg['M_morph_mean']:.6f} +/- {mfn_agg['M_morph_std']:.6f}")
    print(f"  BN-Syn (AdEx)        M_morph = {bnsyn_agg['M_morph_mean']:.6f} +/- {bnsyn_agg['M_morph_std']:.6f}")
    print(f"  Null white noise     M_morph = {wn_agg['M_morph_mean']:.6f} +/- {wn_agg['M_morph_std']:.6f}")
    print(f"  Null time-shuffled   M_morph = {sh_agg['M_morph_mean']:.6f} +/- {sh_agg['M_morph_std']:.6f}")
    print(f"  rel_diff(BN-Syn vs MFN_1D)        = {metrics['rel_diff_bnsyn']:.4f}  (threshold {THRESHOLD_REL})")
    print(f"  rel_diff(white_noise vs MFN_1D)   = {metrics['rel_diff_white_noise']:.4f}")
    print(f"  rel_diff(time_shuffled vs MFN_1D) = {metrics['rel_diff_time_shuffled']:.4f}")
    print()
    print(f"  >>> {verdict}: {reason}")
    print(f"  evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")
    print(f"  ({elapsed:.1f}s total)")
    print("=" * 70)
    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
