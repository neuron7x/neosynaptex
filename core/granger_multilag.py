"""Multi-lag Granger causality with BIC lag selection.

Extends the single-lag Granger in neosynaptex.py to automatic lag
selection via Bayesian Information Criterion (BIC).
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import lstsq as scipy_lstsq

__all__ = [
    "granger_multilag",
]


def _bic(rss: float, n: int, k: int) -> float:
    """Bayesian Information Criterion: BIC = n*ln(RSS/n) + k*ln(n)."""
    if rss <= 0 or n <= k:
        return float("inf")
    return float(n * np.log(rss / n) + k * np.log(n))


def granger_multilag(
    x: np.ndarray,
    y: np.ndarray,
    max_lag: int = 10,
    n_surrogate: int = 200,
    seed: int = 42,
) -> dict[str, object]:
    """Multivariate Granger causality with BIC lag selection.

    Tests: does x Granger-cause y?
    Selects optimal lag via BIC, then computes F-statistic.

    Returns:
        {lag_selected, f_stat, p_value, bic_per_lag, n_obs}
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    n = min(len(x), len(y))
    if n < max_lag + 5:
        return {
            "lag_selected": None,
            "f_stat": float("nan"),
            "p_value": float("nan"),
            "bic_per_lag": {},
            "n_obs": n,
        }

    x = x[:n]
    y = y[:n]

    # Remove NaN
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    n = len(x)
    if n < max_lag + 5:
        return {
            "lag_selected": None,
            "f_stat": float("nan"),
            "p_value": float("nan"),
            "bic_per_lag": {},
            "n_obs": n,
        }

    # BIC lag selection for the full model: y[t] ~ y[t-1..t-L] + x[t-1..t-L]
    bic_per_lag = {}
    best_lag = 1
    best_bic = float("inf")

    for lag in range(1, min(max_lag + 1, n // 3)):
        y_target = y[lag:]
        cols = []
        for l in range(1, lag + 1):
            cols.append(y[lag - l : n - l])
            cols.append(x[lag - l : n - l])

        X_full = np.column_stack(cols)
        n_obs = len(y_target)
        k_full = X_full.shape[1]

        if n_obs <= k_full + 2:
            continue

        try:
            b, _, _, _ = scipy_lstsq(X_full, y_target)
            rss = float(np.sum((y_target - X_full @ b) ** 2))
            b_val = _bic(rss, n_obs, k_full)
            bic_per_lag[lag] = round(b_val, 4)
            if b_val < best_bic:
                best_bic = b_val
                best_lag = lag
        except Exception:  # nosec B112  # singular matrix in lag estimation
            continue

    if not bic_per_lag:
        return {
            "lag_selected": None,
            "f_stat": float("nan"),
            "p_value": float("nan"),
            "bic_per_lag": {},
            "n_obs": n,
        }

    # F-test at best_lag
    lag = best_lag
    y_target = y[lag:]
    n_obs = len(y_target)

    # Restricted model: y[t] ~ y[t-1..t-L]
    cols_r = [y[lag - l : n - l] for l in range(1, lag + 1)]
    X_r = np.column_stack(cols_r) if cols_r else np.ones((n_obs, 1))

    # Full model: y[t] ~ y[t-1..t-L] + x[t-1..t-L]
    cols_f = []
    for l in range(1, lag + 1):
        cols_f.append(y[lag - l : n - l])
        cols_f.append(x[lag - l : n - l])
    X_f = np.column_stack(cols_f)

    try:
        b_r, _, _, _ = scipy_lstsq(X_r, y_target)
        rss_r = float(np.sum((y_target - X_r @ b_r) ** 2))

        b_f, _, _, _ = scipy_lstsq(X_f, y_target)
        rss_f = float(np.sum((y_target - X_f @ b_f) ** 2))
    except Exception:
        return {
            "lag_selected": best_lag,
            "f_stat": float("nan"),
            "p_value": float("nan"),
            "bic_per_lag": bic_per_lag,
            "n_obs": n_obs,
        }

    p_full = X_f.shape[1]
    p_restricted = X_r.shape[1]
    df1 = p_full - p_restricted
    df2 = n_obs - p_full

    if df2 <= 0 or rss_f < 1e-15:
        f_stat = float("nan")
    else:
        f_stat = float(((rss_r - rss_f) / df1) / (rss_f / df2))

    # Surrogate p-value
    rng = np.random.default_rng(seed)
    count_ge = 0
    for _ in range(n_surrogate):
        x_perm = rng.permutation(x)
        cols_perm = []
        for l in range(1, lag + 1):
            cols_perm.append(y[lag - l : n - l])
            cols_perm.append(x_perm[lag - l : n - l])
        X_perm = np.column_stack(cols_perm)
        try:
            b_p, _, _, _ = scipy_lstsq(X_perm, y_target)
            rss_p = float(np.sum((y_target - X_perm @ b_p) ** 2))
            if df2 > 0 and rss_p > 1e-15:
                f_perm = float(((rss_r - rss_p) / df1) / (rss_p / df2))
                if f_perm >= f_stat:
                    count_ge += 1
        except Exception:  # nosec B112  # singular matrix in lag estimation
            continue

    p_value = float((count_ge + 1) / (n_surrogate + 1))

    return {
        "lag_selected": best_lag,
        "f_stat": round(f_stat, 4),
        "p_value": round(p_value, 6),
        "bic_per_lag": bic_per_lag,
        "n_obs": n_obs,
    }
