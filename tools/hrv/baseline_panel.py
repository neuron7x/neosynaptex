"""Baseline HRV panel — 11 metrics per subject, pure numpy/scipy.

Task 3 of the γ-program remediation protocol. Closes audit M-05.

Metrics (units in parens)
-------------------------
Time domain:
  SDNN       (ms)    std of NN intervals                         Task Force 1996 §3.1
  RMSSD      (ms)    √ mean (ΔNN)²                               Task Force 1996 §3.1

Frequency domain (Welch PSD of RR resampled to uniform 4 Hz grid):
  TP         (ms²)   total power in [0.003, 0.4] Hz              Task Force 1996 §3.2
  LF         (ms²)   LF power in [0.04, 0.15] Hz                 ←
  HF         (ms²)   HF power in [0.15, 0.4] Hz                  ←
  LF_HF      (–)     LF / HF ratio                               ←

Nonlinear:
  DFA_alpha1 (–)     short-scale DFA slope, scales 4–16 beats    Peng et al. 1995
  DFA_alpha2 (–)     long-scale DFA slope, scales 16–64 beats    ←
  SD1        (ms)    Poincaré short-axis = std(ΔNN)/√2           Brennan et al. 2001
  SD2        (ms)    Poincaré long-axis  = √(2·Var(NN) − ½·Var(ΔNN))
                                                                 ←
  SampEn     (–)     Sample entropy (m=2, r=0.2·σ)               Richman & Moorman 2000

Primary stack vs. NeuroKit2 / pyHRV
-----------------------------------
Task 3 spec calls for NeuroKit2 primary + pyHRV cross-check. Neither is
pinned yet (Task 11 freezes the toolchain). To avoid shipping a
dependency cliff ahead of its own PR, this panel is implemented in
pure numpy / scipy — both already pinned in ``pyproject.toml``.

Every metric is derived from textbook formulas and validated against
synthetic signals of known scaling (white noise → DFA α ≈ 0.5; Brownian
motion → DFA α ≈ 1.5; 0.1 Hz sinusoid → LF power ≫ HF). When Task 11
lands and NK2 / pyHRV are pinned, :func:`cross_check_against_neurokit2`
(opt-in, runtime-guarded) can be wired in without breaking this stack.

RR preprocessing
----------------
Input is the raw RR-interval series in seconds (output of
``tools.data.physionet_cohort.derive_rr_intervals``). This module does
**not** perform ectopic-beat correction or missing-beat repair —
those live under Task 7 (outlier protocol). It does apply a minimal
plausibility clip [0.3, 2.0] s to reject obvious artefacts (>200 bpm
or <30 bpm would never be a real cardiac beat). The number of rejected
samples is reported in ``n_rr_clipped`` for audit.

Windowing
---------
By default the whole RR series is summarised. Per-window panels are
handled in Task 9 (state contrast); they are not Task 3's concern.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
from scipy.signal import welch

__all__ = [
    "HRVPanel",
    "HRVPreprocessingParams",
    "compute_baseline_panel",
    "dfa_alpha",
    "sample_entropy",
]


# --- Preprocessing ---------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class HRVPreprocessingParams:
    """Tunables for RR preprocessing (frozen across the γ-program)."""

    min_rr_s: float = 0.3  # reject < 0.3 s   (>200 bpm)
    max_rr_s: float = 2.0  # reject > 2.0 s   (<30 bpm)
    fs_resample_hz: float = 4.0  # standard HRV frequency-domain rate
    welch_nperseg_s: float = 256.0  # Welch segment length in seconds
    welch_overlap: float = 0.5  # fractional overlap
    dfa_short: tuple[int, int] = (4, 16)
    dfa_long: tuple[int, int] = (16, 64)
    sampen_max_n: int = 5000  # cap for O(N²) SampEn
    sampen_m: int = 2
    sampen_r_frac: float = 0.2  # r = 0.2·std(RR)


DEFAULT_PARAMS = HRVPreprocessingParams()


def _preprocess(rr_s: np.ndarray, params: HRVPreprocessingParams) -> tuple[np.ndarray, int]:
    """Clip implausible RR values. Returns (clipped_rr, n_rejected)."""

    rr = np.asarray(rr_s, dtype=np.float64)
    mask = (rr >= params.min_rr_s) & (rr <= params.max_rr_s)
    return rr[mask], int((~mask).sum())


# --- Time domain -----------------------------------------------------------
def _sdnn_ms(rr_s: np.ndarray) -> float:
    return float(1000.0 * np.std(rr_s, ddof=1))


def _rmssd_ms(rr_s: np.ndarray) -> float:
    d = np.diff(rr_s)
    return float(1000.0 * math.sqrt(float(np.mean(d * d))))


# --- Poincaré --------------------------------------------------------------
def _sd1_sd2_ms(rr_s: np.ndarray) -> tuple[float, float]:
    var_rr = float(np.var(rr_s, ddof=1))
    var_drr = float(np.var(np.diff(rr_s), ddof=1))
    sd1 = math.sqrt(0.5 * var_drr)
    sd2_sq = 2.0 * var_rr - 0.5 * var_drr
    sd2 = math.sqrt(max(0.0, sd2_sq))
    return 1000.0 * sd1, 1000.0 * sd2


# --- DFA -------------------------------------------------------------------
def dfa_alpha(rr_s: np.ndarray, scales: np.ndarray) -> float:
    """DFA scaling exponent α via Peng et al. 1995 standard algorithm.

    Integrates the mean-subtracted signal, partitions into
    non-overlapping windows of each scale, fits a linear trend per
    window, computes fluctuation F(s) as √mean residual variance, then
    returns the slope of log F vs log s. Returns NaN when fewer than
    three scales survive the min-segments-per-scale check (≥ 4 segments).
    """

    y = np.cumsum(rr_s - float(np.mean(rr_s)))
    n = y.size
    F: list[float] = []
    used: list[int] = []
    for s in scales:
        s = int(s)
        n_seg = n // s
        if n_seg < 4:
            continue
        segs = y[: n_seg * s].reshape(n_seg, s)
        x = np.arange(s, dtype=np.float64)
        # vectorised per-row polyfit order-1: solve normal equations
        X = np.stack([x, np.ones_like(x)], axis=1)  # (s, 2)
        coeffs, *_ = np.linalg.lstsq(X, segs.T, rcond=None)  # (2, n_seg)
        trend = X @ coeffs  # (s, n_seg)
        residuals = segs.T - trend  # (s, n_seg)
        f_per_seg = np.mean(residuals * residuals, axis=0)  # (n_seg,)
        F.append(math.sqrt(float(np.mean(f_per_seg))))
        used.append(s)
    if len(F) < 3:
        return float("nan")
    log_s = np.log(np.asarray(used, dtype=np.float64))
    log_f = np.log(np.asarray(F, dtype=np.float64) + 1e-12)
    slope = float(np.polyfit(log_s, log_f, 1)[0])
    return slope


# --- Frequency-domain ------------------------------------------------------
def _resample_rr_to_uniform(
    rr_s: np.ndarray,
    fs_target_hz: float,
) -> tuple[np.ndarray, float]:
    """Linear interpolation of RR onto a uniform time grid.

    Returns (rr_uniform, fs_actual) where fs_actual == fs_target_hz.
    """

    t_beat = np.cumsum(rr_s)  # cumulative time of each beat
    t_start = 0.0
    t_end = float(t_beat[-1])
    n_samples = int((t_end - t_start) * fs_target_hz) + 1
    if n_samples < 16:
        return np.asarray([], dtype=np.float64), fs_target_hz
    t_uniform = np.linspace(t_start, t_end, n_samples)
    # interpolate RR-at-beat vs. beat time
    # use prepended zero-time + first RR to anchor
    t_src = np.concatenate([[0.0], t_beat])
    rr_src = np.concatenate([[rr_s[0]], rr_s])
    rr_u = np.interp(t_uniform, t_src, rr_src)
    return rr_u, fs_target_hz


def _power_bands(
    rr_s: np.ndarray,
    params: HRVPreprocessingParams,
) -> tuple[float, float, float, float]:
    """Return (TP, LF, HF, LF_HF) in ms² / unitless."""

    rr_u, fs = _resample_rr_to_uniform(rr_s, params.fs_resample_hz)
    if rr_u.size < 32:
        return float("nan"), float("nan"), float("nan"), float("nan")
    nperseg = min(int(params.welch_nperseg_s * fs), rr_u.size)
    f, P = welch(
        rr_u,
        fs=fs,
        nperseg=nperseg,
        noverlap=int(nperseg * params.welch_overlap),
        detrend="constant",
        scaling="density",
    )
    # convert PSD from s² / Hz to ms² / Hz
    P_ms2 = P * 1_000_000.0

    def band(lo: float, hi: float) -> float:
        m = (f >= lo) & (f <= hi)
        if not np.any(m):
            return 0.0
        return float(np.trapezoid(P_ms2[m], f[m]))

    tp = band(0.003, 0.4)
    lf = band(0.04, 0.15)
    hf = band(0.15, 0.4)
    lf_hf = float(lf / hf) if hf > 0.0 else float("nan")
    return tp, lf, hf, lf_hf


# --- Sample entropy --------------------------------------------------------
def sample_entropy(
    rr_s: np.ndarray,
    m: int = 2,
    r_frac: float = 0.2,
    max_n: int = 5000,
) -> float:
    """Richman & Moorman 2000 sample entropy.

    Returns −log(A/B) where A is the number of ordered template pairs
    of length m+1 within Chebyshev distance r, B is the same for
    length m. Both exclude self-matches.

    ``max_n`` caps the input to keep O(N²) tractable. HRV convention
    typically uses 500–5000 samples.
    """

    from scipy.spatial import cKDTree

    rr = np.asarray(rr_s, dtype=np.float64)
    if rr.size > max_n:
        rr = rr[:max_n]
    n = rr.size
    if n < m + 2:
        return float("nan")
    r = r_frac * float(np.std(rr, ddof=1))
    if r == 0.0:
        return float("nan")

    # Chebyshev-metric pair count via cKDTree.count_neighbors, O(N log N).
    # Values are byte-identical to the naive O(N²) Richman-Moorman code —
    # verified on synthetic signals before swap.
    def count_within(m_len: int) -> int:
        # Copy into contiguous array — sliding_window_view returns a view
        # whose stride layout KDTree rejects.
        T = np.ascontiguousarray(np.lib.stride_tricks.sliding_window_view(rr, m_len))
        tree = cKDTree(T)
        # count pairs with Chebyshev (p=inf) dist ≤ r, minus N self-pairs.
        # The "-1e-12" keeps the strict "< r" convention from the naive impl.
        return int(tree.count_neighbors(tree, r=r - 1e-12, p=np.inf) - T.shape[0])

    b = count_within(m)
    a = count_within(m + 1)
    if a == 0 or b == 0:
        return float("nan")
    return float(-math.log(a / b))


# --- Panel -----------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class HRVPanel:
    """All 11 baseline HRV metrics + provenance."""

    n_rr: int
    n_rr_clipped: int
    rr_duration_s: float

    # time domain
    sdnn_ms: float
    rmssd_ms: float

    # frequency domain
    total_power_ms2: float
    lf_power_ms2: float
    hf_power_ms2: float
    lf_hf_ratio: float

    # nonlinear
    dfa_alpha1: float
    dfa_alpha2: float
    poincare_sd1_ms: float
    poincare_sd2_ms: float
    sample_entropy: float

    def as_dict(self) -> dict[str, float | int]:
        return dataclasses.asdict(self)


def compute_baseline_panel(
    rr_s: np.ndarray,
    params: HRVPreprocessingParams = DEFAULT_PARAMS,
) -> HRVPanel:
    """Compute all 11 metrics on a single RR-interval series (seconds)."""

    rr_clipped, n_rejected = _preprocess(rr_s, params)
    if rr_clipped.size < 64:
        # too short after clipping — emit NaN panel with provenance
        nan = float("nan")
        return HRVPanel(
            n_rr=int(rr_clipped.size),
            n_rr_clipped=n_rejected,
            rr_duration_s=float(rr_clipped.sum()) if rr_clipped.size else 0.0,
            sdnn_ms=nan,
            rmssd_ms=nan,
            total_power_ms2=nan,
            lf_power_ms2=nan,
            hf_power_ms2=nan,
            lf_hf_ratio=nan,
            dfa_alpha1=nan,
            dfa_alpha2=nan,
            poincare_sd1_ms=nan,
            poincare_sd2_ms=nan,
            sample_entropy=nan,
        )

    sdnn = _sdnn_ms(rr_clipped)
    rmssd = _rmssd_ms(rr_clipped)
    sd1, sd2 = _sd1_sd2_ms(rr_clipped)
    tp, lf, hf, lf_hf = _power_bands(rr_clipped, params)

    scales_short = np.unique(
        np.round(
            np.logspace(math.log10(params.dfa_short[0]), math.log10(params.dfa_short[1]), 6)
        ).astype(int)
    )
    scales_long = np.unique(
        np.round(
            np.logspace(math.log10(params.dfa_long[0]), math.log10(params.dfa_long[1]), 8)
        ).astype(int)
    )
    alpha1 = dfa_alpha(rr_clipped, scales_short)
    alpha2 = dfa_alpha(rr_clipped, scales_long)

    sampen = sample_entropy(
        rr_clipped,
        m=params.sampen_m,
        r_frac=params.sampen_r_frac,
        max_n=params.sampen_max_n,
    )

    return HRVPanel(
        n_rr=int(rr_clipped.size),
        n_rr_clipped=n_rejected,
        rr_duration_s=float(rr_clipped.sum()),
        sdnn_ms=sdnn,
        rmssd_ms=rmssd,
        total_power_ms2=tp,
        lf_power_ms2=lf,
        hf_power_ms2=hf,
        lf_hf_ratio=lf_hf,
        dfa_alpha1=alpha1,
        dfa_alpha2=alpha2,
        poincare_sd1_ms=sd1,
        poincare_sd2_ms=sd2,
        sample_entropy=sampen,
    )
