"""Transfer Entropy for gamma traces with IAAFT surrogate significance test.

TE(X->Y) = H(Y_future|Y_past) - H(Y_future|Y_past, X_past)
Estimation via KSG-style binning (histogram-based for robustness).
Significance: IAAFT surrogate test.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "transfer_entropy_gamma",
]


def _embed(x: np.ndarray, k: int) -> np.ndarray:
    """Time-delay embedding: rows are [x[t-k], ..., x[t-1], x[t]]."""
    n = len(x)
    if n <= k:
        return np.empty((0, k + 1))
    return np.column_stack([x[i : n - k + i] for i in range(k + 1)])


def _entropy_hist(x: np.ndarray, bins: int = 16) -> float:
    """Marginal entropy via histogram."""
    if len(x) < 2:
        return 0.0
    counts, _ = np.histogram(x, bins=bins)
    p = counts / counts.sum()
    p = p[p > 0]
    return -float(np.sum(p * np.log2(p)))


def _joint_entropy_hist(x: np.ndarray, y: np.ndarray, bins: int = 16) -> float:
    """Joint entropy of two 1D arrays."""
    if len(x) < 2:
        return 0.0
    counts, _, _ = np.histogram2d(x, y, bins=bins)
    p = counts.flatten() / counts.sum()
    p = p[p > 0]
    return -float(np.sum(p * np.log2(p)))


def _conditional_entropy(target: np.ndarray, condition: np.ndarray, bins: int = 16) -> float:
    """H(target | condition) = H(target, condition) - H(condition)."""
    return _joint_entropy_hist(target, condition, bins) - _entropy_hist(condition, bins)


def _iaaft_surrogate(x: np.ndarray, rng: np.random.Generator, n_iter: int = 200) -> np.ndarray:
    """Thin wrapper around the canonical scalar IAAFT.

    Kept as ``_iaaft_surrogate`` to preserve the tests in
    ``tests/test_coherence.py`` that reach for this private helper by
    name. Behaviour now delegates to ``core.iaaft.iaaft_surrogate`` so
    coherence.py can never drift from the canonical alternating-
    projection semantics (per the 2026-04-15 repair protocol).

    The default ``n_iter`` has been lifted from 10 to 200 — the old
    value was visibly insufficient and contributed to the T5
    convergence failure that triggered the repair.
    """

    from core.iaaft import iaaft_surrogate as _canonical

    result = _canonical(x, rng=rng, n_iter=n_iter, return_diagnostics=False)
    # Legacy (rng=) path returns a 3-tuple; take the array head.
    arr = result[0] if isinstance(result, tuple) else result
    return np.asarray(arr)


def transfer_entropy_gamma(
    source_gamma_series: np.ndarray,
    target_gamma_series: np.ndarray,
    k: int = 1,
    n_surrogate: int = 200,
    seed: int = 42,
    bins: int = 16,
) -> dict[str, object]:
    """Transfer entropy from source gamma trace to target gamma trace.

    TE(X->Y) = H(Y_future|Y_past) - H(Y_future|Y_past, X_past)

    Returns:
        {te: float, p_value: float, te_surrogates: list[float]}
    """
    source = np.asarray(source_gamma_series, dtype=np.float64)
    target = np.asarray(target_gamma_series, dtype=np.float64)

    # Align lengths
    n = min(len(source), len(target))
    if n < k + 5:
        return {"te": float("nan"), "p_value": float("nan"), "te_surrogates": []}

    source = source[:n]
    target = target[:n]

    # Remove NaN
    valid = np.isfinite(source) & np.isfinite(target)
    source = source[valid]
    target = target[valid]
    n = len(source)
    if n < k + 5:
        return {"te": float("nan"), "p_value": float("nan"), "te_surrogates": []}

    # Compute TE
    y_future = target[k:]
    y_past = target[: n - k]
    x_past = source[: n - k]

    h_y_given_ypast = _conditional_entropy(y_future, y_past, bins)
    combined_past = y_past + x_past * 1e3  # hash-like combination for histogram
    h_y_given_both = _conditional_entropy(y_future, combined_past, bins)

    te = max(0.0, h_y_given_ypast - h_y_given_both)

    # IAAFT surrogate test
    rng = np.random.default_rng(seed)
    te_surrogates = []
    for _ in range(n_surrogate):
        source_surr = _iaaft_surrogate(source, rng)
        x_past_surr = source_surr[: n - k]
        combined_surr = y_past + x_past_surr * 1e3
        h_surr = _conditional_entropy(y_future, combined_surr, bins)
        te_surr = max(0.0, h_y_given_ypast - h_surr)
        te_surrogates.append(te_surr)

    p_value = float((np.sum(np.array(te_surrogates) >= te) + 1) / (n_surrogate + 1))

    return {
        "te": round(float(te), 6),
        "p_value": round(float(p_value), 6),
        "te_surrogates": [round(float(s), 6) for s in te_surrogates[:10]],
    }
