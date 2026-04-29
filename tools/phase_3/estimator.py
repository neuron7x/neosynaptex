"""γ estimator — single canonical Theil–Sen fit on log(K) vs log(C).

The structural relation under test is

    K ~ C^(-γ)     ⇔     log K = -γ · log C + const

We estimate γ as the **negative** of the Theil–Sen slope of
``log(C) → log(K)``. Theil–Sen is chosen over OLS because:

* It is the median of all pairwise slopes — robust to up to 29 % of
  outlier points without breakdown.
* It does not assume Gaussian residuals (we have no model of the noise
  on either axis).
* It returns identical answers across permutations of the input order
  (deterministic, hashable).

This is the **only** γ implementation Phase 3 uses. Other γ paths in
the repository (``analysis/gamma_meta_analysis.py``,
``substrates/serotonergic_kuramoto/adapter.py::_fit_gamma``) are
historical artefacts and are NOT routed through this module — they
serve different historical contracts. Phase 3 result_hashes are bound
to *this* implementation only.
"""

from __future__ import annotations

import dataclasses

import numpy as np
from scipy import stats as _stats  # type: ignore[import-untyped]

__all__ = [
    "GammaEstimate",
    "estimate_gamma",
]


@dataclasses.dataclass(frozen=True)
class GammaEstimate:
    """Result of a single γ fit.

    Attributes
    ----------
    gamma : float
        Negative Theil–Sen slope of ``log(C) → log(K)``. Returned as
        ``nan`` when the fit cannot be evaluated (constant input,
        negative or zero values, fewer than 5 admissible points).
    ci95_low, ci95_high : float
        95 % confidence interval on γ from Theil–Sen's exact pairwise-
        slope distribution. ``nan`` when the fit is degenerate.
    n_used : int
        Number of admissible (positive, finite) sample points actually
        used in the fit.
    degenerate : bool
        True if the input was constant, all-non-positive, or contained
        fewer than 5 admissible points. A degenerate estimate is the
        only kind that may carry a ``nan`` ``gamma``.
    """

    gamma: float
    ci95_low: float
    ci95_high: float
    n_used: int
    degenerate: bool


_MIN_POINTS: int = 5
_LOG_DOMAIN_FLOOR: float = 1e-30


def estimate_gamma(topo: np.ndarray, cost: np.ndarray) -> GammaEstimate:
    """Estimate γ from the K~C^(-γ) scaling using Theil–Sen.

    Parameters
    ----------
    topo : np.ndarray
        K-axis sample (treated as the dependent variable in log-log
        space). Length N.
    cost : np.ndarray
        C-axis sample (treated as the independent variable in log-log
        space). Length N.

    Returns
    -------
    GammaEstimate
        Frozen dataclass — see class docstring.
    """
    t = np.asarray(topo, dtype=np.float64).ravel()
    c = np.asarray(cost, dtype=np.float64).ravel()
    if t.shape != c.shape:
        raise ValueError(f"topo and cost must have identical shape; got {t.shape} vs {c.shape}")

    finite = np.isfinite(t) & np.isfinite(c)
    positive = (t > _LOG_DOMAIN_FLOOR) & (c > _LOG_DOMAIN_FLOOR)
    mask = finite & positive
    n_used = int(mask.sum())
    if n_used < _MIN_POINTS:
        return GammaEstimate(
            gamma=float("nan"),
            ci95_low=float("nan"),
            ci95_high=float("nan"),
            n_used=n_used,
            degenerate=True,
        )

    log_c = np.log(c[mask])
    log_t = np.log(t[mask])

    # Degenerate input: constant log_c → no slope is defined.
    if (log_c.max() - log_c.min()) < 1e-12 or (log_t.max() - log_t.min()) < 1e-12:
        return GammaEstimate(
            gamma=float("nan"),
            ci95_low=float("nan"),
            ci95_high=float("nan"),
            n_used=n_used,
            degenerate=True,
        )

    # Theil–Sen on (log_c -> log_t); γ is the negative of the slope.
    ts = _stats.theilslopes(log_t, log_c, alpha=0.95)
    slope = float(ts.slope)
    lo_slope = float(ts.low_slope)
    hi_slope = float(ts.high_slope)

    gamma = -slope
    # Negating swaps the CI bounds — preserve [low, high] orientation.
    ci_low = -hi_slope
    ci_high = -lo_slope

    return GammaEstimate(
        gamma=gamma,
        ci95_low=ci_low,
        ci95_high=ci_high,
        n_used=n_used,
        degenerate=False,
    )
