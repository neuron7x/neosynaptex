"""Five γ-estimator implementations under admissibility trial.

Common signature (kept tight on purpose so the trial orchestrator can
treat estimators as interchangeable functions of (logC, logK)):

    estimator(log_c: np.ndarray, log_k: np.ndarray) -> EstimatorResult

with ``EstimatorResult`` carrying ``gamma`` (point estimate, defined as
the negative slope of log_k vs log_c, i.e. K ∝ C^(-γ)), and a 95 %
confidence interval ``(ci95_low, ci95_high)``.

All estimators are deterministic given the input arrays. Stochastic
estimators (bootstrap_median_slope) seed an RNG from a hash of the
input so that re-running produces byte-identical γ̂ — a hard
requirement for the trial's ``result_hash`` reproducibility contract.
"""

from __future__ import annotations

import dataclasses
import hashlib
import warnings
from collections.abc import Callable
from typing import Final

import numpy as np
from scipy import stats as _stats

__all__ = [
    "ESTIMATOR_NAMES",
    "ESTIMATOR_REGISTRY",
    "EstimatorResult",
    "bootstrap_median_slope",
    "canonical_theil_sen",
    "odr_log_log",
    "quantile_pivoted_slope",
    "subwindow_bagged_theil_sen",
]


_MIN_POINTS: Final[int] = 5

# Spec value for the canonical run: B=1000. Smoke/CI runs override
# this via :func:`set_bootstrap_b` to keep the matrix tractable in the
# CI time budget. Two runs at the same B value produce byte-identical
# γ̂; runs at different B values produce different result_hashes by
# design — the value of B is part of the hashable payload via
# ``config.bootstrap_b``.
_BOOTSTRAP_B: int = 1000


def set_bootstrap_b(b: int) -> None:
    """Override the bootstrap resample count B for the current process.

    Used by the CLI smoke path to reduce B from 1000 to 200 so that
    the smoke matrix fits in CI time budget. Canonical (M=1000) runs
    keep B=1000.
    """
    global _BOOTSTRAP_B
    if b < 10:
        raise ValueError(f"bootstrap B must be >= 10; got {b}")
    _BOOTSTRAP_B = int(b)


def get_bootstrap_b() -> int:
    """Return the current bootstrap resample count B."""
    return _BOOTSTRAP_B


def _fast_theil_sen_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Vectorised median of pairwise slopes — slope only, no CI.

    Used inside ``bootstrap_median_slope`` and
    ``subwindow_bagged_theil_sen`` where only the point estimate is
    needed. Equivalent to ``scipy.stats.theilslopes(y, x).slope`` but
    skips the O(N²) Wilcoxon-rank CI computation that dominates the
    scipy implementation's runtime. Returns NaN when the slope is
    undefined (no admissible pair).
    """
    n = x.size
    if n < 2:
        return float("nan")
    i_idx, j_idx = np.triu_indices(n, k=1)
    dx = x[j_idx] - x[i_idx]
    dy = y[j_idx] - y[i_idx]
    valid = np.abs(dx) > 1e-12
    if not valid.any():
        return float("nan")
    return float(np.median(dy[valid] / dx[valid]))


@dataclasses.dataclass(frozen=True)
class EstimatorResult:
    """Single γ estimate plus 95 % CI.

    A degenerate fit (constant input, fewer than 5 admissible points,
    or a numerical failure inside the underlying solver) yields an
    all-NaN result. NaN γ̂ propagates through the trial — replicates
    that NaN'd out are excluded from the median/RMSE summary, and the
    trial reports the NaN fraction explicitly.
    """

    gamma: float
    ci95_low: float
    ci95_high: float


def _degenerate() -> EstimatorResult:
    """Sentinel for a non-fittable input."""
    return EstimatorResult(
        gamma=float("nan"),
        ci95_low=float("nan"),
        ci95_high=float("nan"),
    )


def _seed_from_arrays(log_c: np.ndarray, log_k: np.ndarray) -> int:
    """Stable 32-bit seed derived from the input arrays.

    Bootstrap estimators must be reproducible — seeding from a hash of
    the input means two calls on the same (log_c, log_k) yield the same
    γ̂, which is what the byte-identical result_hash contract requires.
    """
    h = hashlib.sha256()
    h.update(log_c.tobytes())
    h.update(log_k.tobytes())
    return int.from_bytes(h.digest()[:4], "little", signed=False)


def canonical_theil_sen(log_c: np.ndarray, log_k: np.ndarray) -> EstimatorResult:
    """Estimator 1 — current canonical Theil–Sen slope of log_k vs log_c.

    Mirrors ``tools/phase_3/estimator.py::estimate_gamma`` in spirit:
    γ = -slope, with the CI computed from Theil–Sen's exact pairwise
    distribution at α=0.05 and oriented to (low, high) after sign flip.
    """
    if log_c.shape != log_k.shape or log_c.size < _MIN_POINTS:
        return _degenerate()
    if (log_c.max() - log_c.min()) < 1e-12:
        return _degenerate()
    ts = _stats.theilslopes(log_k, log_c, alpha=0.95)
    slope = float(ts.slope)
    lo_slope = float(ts.low_slope)
    hi_slope = float(ts.high_slope)
    return EstimatorResult(
        gamma=-slope,
        ci95_low=-hi_slope,
        ci95_high=-lo_slope,
    )


def subwindow_bagged_theil_sen(log_c: np.ndarray, log_k: np.ndarray) -> EstimatorResult:
    """Estimator 2 — median over Theil–Sen fits on N/2 sliding windows.

    The window width is fixed at ``N // 2`` with stride 1, giving
    ``N - N//2 + 1`` windows. We Theil–Sen-fit each window, take the
    median of the bag of γ̂'s as the point estimate, and use the
    25th/97.5th percentile as the CI bound (an empirical, conservative
    proxy — bagging variance is the *intra-trajectory* variability).
    """
    n = log_c.size
    if log_c.shape != log_k.shape or n < _MIN_POINTS:
        return _degenerate()
    width = max(_MIN_POINTS, n // 2)
    if width >= n:
        # Falls back to a single canonical Theil–Sen fit.
        return canonical_theil_sen(log_c, log_k)
    bag: list[float] = []
    for start in range(n - width + 1):
        window_c = log_c[start : start + width]
        if (window_c.max() - window_c.min()) < 1e-12:
            continue
        slope = _fast_theil_sen_slope(window_c, log_k[start : start + width])
        if np.isfinite(slope):
            bag.append(-slope)
    if len(bag) == 0:
        return _degenerate()
    arr = np.asarray(bag, dtype=np.float64)
    gamma = float(np.median(arr))
    ci_low = float(np.quantile(arr, 0.025))
    ci_high = float(np.quantile(arr, 0.975))
    return EstimatorResult(gamma=gamma, ci95_low=ci_low, ci95_high=ci_high)


def quantile_pivoted_slope(log_c: np.ndarray, log_k: np.ndarray) -> EstimatorResult:
    """Estimator 3 — pairwise slopes, return Q50 with CI from Q025/Q975.

    For each (i, j) with j > i, compute s_ij = (logK_j − logK_i) /
    (logC_j − logC_i). γ̂ = -median(s_ij). CI from the 2.5th and 97.5th
    percentiles, sign-flipped to maintain (low, high) orientation.
    Equivalent to Theil–Sen on the point estimate (by definition) but
    with a percentile-based CI rather than the Wilcoxon-rank CI used
    by ``scipy.stats.theilslopes``.
    """
    n = log_c.size
    if log_c.shape != log_k.shape or n < _MIN_POINTS:
        return _degenerate()
    # All-pairs slopes; vectorised across the upper triangle.
    i_idx, j_idx = np.triu_indices(n, k=1)
    dc = log_c[j_idx] - log_c[i_idx]
    dk = log_k[j_idx] - log_k[i_idx]
    valid = np.abs(dc) > 1e-12
    if not valid.any():
        return _degenerate()
    slopes = dk[valid] / dc[valid]
    gamma = -float(np.median(slopes))
    lo = -float(np.quantile(slopes, 0.975))
    hi = -float(np.quantile(slopes, 0.025))
    return EstimatorResult(gamma=gamma, ci95_low=lo, ci95_high=hi)


def bootstrap_median_slope(log_c: np.ndarray, log_k: np.ndarray) -> EstimatorResult:
    """Estimator 4 — B=1000 bootstrap Theil–Sen fits, return median γ̂.

    Resamples (log_c[i], log_k[i]) pairs with replacement B times, fits
    Theil–Sen on each resample, returns the median of γ̂'s as the
    point estimate. CI from the 2.5th / 97.5th percentile of the
    bootstrap γ̂ distribution. Seed is derived from the input bytes so
    two calls on identical input give identical output.
    """
    n = log_c.size
    if log_c.shape != log_k.shape or n < _MIN_POINTS:
        return _degenerate()
    rng = np.random.default_rng(_seed_from_arrays(log_c, log_k))
    b_total = _BOOTSTRAP_B
    estimates = np.full(b_total, np.nan, dtype=np.float64)
    for b in range(b_total):
        idx = rng.integers(0, n, size=n)
        c_b = log_c[idx]
        k_b = log_k[idx]
        if (c_b.max() - c_b.min()) < 1e-12:
            continue
        slope = _fast_theil_sen_slope(c_b, k_b)
        if np.isfinite(slope):
            estimates[b] = -slope
    finite = estimates[np.isfinite(estimates)]
    if finite.size == 0:
        return _degenerate()
    gamma = float(np.median(finite))
    ci_low = float(np.quantile(finite, 0.025))
    ci_high = float(np.quantile(finite, 0.975))
    return EstimatorResult(gamma=gamma, ci95_low=ci_low, ci95_high=ci_high)


def _odr_linear(beta: np.ndarray, x: np.ndarray) -> np.ndarray:
    """ODR model function: y = beta[0] * x + beta[1]."""
    out: np.ndarray = beta[0] * x + beta[1]
    return out


def odr_log_log(log_c: np.ndarray, log_k: np.ndarray) -> EstimatorResult:
    """Estimator 5 — orthogonal distance regression on log–log axes.

    Equal x/y standard errors are used (sx = sy = 1), so the fit
    minimises orthogonal residuals — appropriate when both axes are
    noisy. γ = -slope. CI from ``β̂ ± 1.96 · σ̂_β`` from the ODR
    covariance estimate, sign-flipped to maintain (low, high) order.
    """
    n = log_c.size
    if log_c.shape != log_k.shape or n < _MIN_POINTS:
        return _degenerate()
    if (log_c.max() - log_c.min()) < 1e-12:
        return _degenerate()
    # OLS-on-log seed for the slope/intercept; ODR is sensitive to
    # initial conditions and the linear LS is the natural starting
    # point on log-axis data.
    slope_seed, intercept_seed, *_ = _stats.linregress(log_c, log_k)
    # scipy.odr is deprecated (SciPy 1.17) and slated for removal in 1.19, but
    # odr_log_log's γ̂ is byte-frozen into the trial verdict-hash, so the
    # ODRPACK engine cannot be swapped without breaking that contract. Import it
    # lazily and silence only this one known, tracked deprecation so it does not
    # pollute otherwise-clean test logs. The import will fail loudly — not
    # silently — once SciPy actually removes the module, surfacing the migration.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from scipy import odr as _odr
    model = _odr.Model(_odr_linear)
    data = _odr.RealData(log_c, log_k, sx=np.ones(n), sy=np.ones(n))
    odr = _odr.ODR(data, model, beta0=[float(slope_seed), float(intercept_seed)])
    out = odr.run()
    slope = float(out.beta[0])
    sd_slope = float(out.sd_beta[0])
    z = 1.959963984540054  # two-sided 95 % normal quantile
    return EstimatorResult(
        gamma=-slope,
        ci95_low=-slope - z * sd_slope,  # = -(slope + z*sd) → low after flip
        ci95_high=-slope + z * sd_slope,
    )


#: Tuple-ordered, name → function. Keep this ordering stable across
#: releases — the verdict-hash payload includes estimator names in this
#: order, so reordering would break the byte-identical hash contract.
ESTIMATOR_REGISTRY: dict[str, Callable[[np.ndarray, np.ndarray], EstimatorResult]] = {
    "canonical_theil_sen": canonical_theil_sen,
    "subwindow_bagged_theil_sen": subwindow_bagged_theil_sen,
    "quantile_pivoted_slope": quantile_pivoted_slope,
    "bootstrap_median_slope": bootstrap_median_slope,
    "odr_log_log": odr_log_log,
}

ESTIMATOR_NAMES: tuple[str, ...] = tuple(ESTIMATOR_REGISTRY.keys())
