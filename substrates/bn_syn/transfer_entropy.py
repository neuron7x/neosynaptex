"""Transfer Entropy Engine -- directed information flow measurement.

TE(X->Y) = H(Y_t | Y_{t-1}) - H(Y_t | Y_{t-1}, X_{t-1})

Asymmetric by definition: TE(X->Y) != TE(Y->X).
This is the key property that distinguishes causal influence from correlation.

Author: Yaroslav Vasylenko / neuron7xLab
License: AGPL-3.0-or-later
"""

from __future__ import annotations

import numpy as np


def transfer_entropy(
    source: np.ndarray,
    target: np.ndarray,
    lag: int = 1,
    bins: int = 10,
) -> float:
    """Compute TE(source -> target) via binning estimator.

    TE(X->Y) = H(Y_t | Y_{t-1}) - H(Y_t | Y_{t-1}, X_{t-1})
             = H(Y_t, Y_{t-1}) - H(Y_{t-1}) - H(Y_t, Y_{t-1}, X_{t-1}) + H(Y_{t-1}, X_{t-1})

    Args:
        source: time series, shape (T,)
        target: time series, shape (T,)
        lag:    temporal lag in timesteps
        bins:   number of bins for entropy estimation

    Returns:
        float: transfer entropy in nats (>= 0)

    Properties:
        TE(X->Y) > 0: X causally influences Y
        TE(X->Y) ~ 0: no causal influence
        TE(X->Y) != TE(Y->X): asymmetric
    """
    source = np.asarray(source, dtype=np.float64).ravel()
    target = np.asarray(target, dtype=np.float64).ravel()
    n = min(len(source), len(target))
    if n < lag + 10:
        return 0.0

    source = source[:n]
    target = target[:n]

    # Align with lag
    t_future = target[lag:]
    t_past = target[:-lag]
    s_past = source[:-lag]

    # Uniform binning for entropy estimation
    def _digitize(x: np.ndarray) -> np.ndarray:
        lo, hi = float(np.min(x)), float(np.max(x))
        if hi - lo < 1e-15:
            return np.zeros(len(x), dtype=np.int64)
        edges = np.linspace(lo - 1e-10, hi + 1e-10, bins + 1)
        return np.asarray(np.digitize(x, edges[1:-1]), dtype=np.int64)

    tf = _digitize(t_future)
    tp = _digitize(t_past)
    sp = _digitize(s_past)

    def _entropy(*arrays: np.ndarray) -> float:
        """Joint entropy from co-occurrence counts."""
        combined = arrays[0].copy()
        for arr in arrays[1:]:
            combined = combined * (bins + 1) + arr
        _, counts = np.unique(combined, return_counts=True)
        p = counts / counts.sum()
        return -float(np.sum(p * np.log(p + 1e-300)))

    # TE = H(Y_t, Y_{t-1}) - H(Y_{t-1}) - H(Y_t, Y_{t-1}, X_{t-1}) + H(Y_{t-1}, X_{t-1})
    h_tf_tp = _entropy(tf, tp)
    h_tp = _entropy(tp)
    h_tf_tp_sp = _entropy(tf, tp, sp)
    h_tp_sp = _entropy(tp, sp)

    te = h_tf_tp - h_tp - h_tf_tp_sp + h_tp_sp
    return max(0.0, float(te))


def transfer_entropy_matrix(
    signals: np.ndarray,
    lag: int = 1,
    bins: int = 10,
) -> np.ndarray:
    """Compute pairwise TE matrix for N signals.

    Args:
        signals: shape (N, T)

    Returns:
        TE matrix shape (N, N) where [i,j] = TE(i->j)
    """
    n = signals.shape[0]
    te_mat = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                te_mat[i, j] = transfer_entropy(signals[i], signals[j], lag, bins)
    return te_mat


def verify_te_implementation() -> bool:
    """Numerical verification per MASTER PROTOCOL. Run FIRST.

    Uses temporal (lagged) coupling: Y[t] = a*X[t-1] + noise.
    This is the correct structure for lag-1 transfer entropy.
    """
    np.random.seed(42)
    T = 5000

    # Case 1: directed temporal causal X -> Y
    # Y[t] depends on X[t-1], not X[t] — proper lag structure
    X = np.random.randn(T)
    Y = np.empty(T)
    Y[0] = np.random.randn()
    for t in range(1, T):
        Y[t] = 0.7 * X[t - 1] + 0.3 * np.random.randn()

    te_xy = transfer_entropy(X, Y, bins=6)
    te_yx = transfer_entropy(Y, X, bins=6)
    assert te_xy > te_yx, f"TE(X->Y)={te_xy:.4f} must > TE(Y->X)={te_yx:.4f}"

    # Case 2: independent -> TE near zero (binning has positive bias ~O(bins/N))
    A = np.random.randn(T)
    B = np.random.randn(T)
    te_ab = transfer_entropy(A, B, bins=6)
    assert te_ab < te_xy, f"Independent TE >= causal: {te_ab:.4f} >= {te_xy:.4f}"

    # Case 3: non-negative
    assert te_xy >= 0.0, f"TE must be non-negative: {te_xy}"
    assert te_yx >= 0.0, f"TE must be non-negative: {te_yx}"
    assert te_ab >= 0.0, f"TE must be non-negative: {te_ab}"

    print(f"TE VERIFIED: TE(X->Y)={te_xy:.4f}, TE(Y->X)={te_yx:.4f}, TE(indep)={te_ab:.4f}")
    return True


if __name__ == "__main__":
    verify_te_implementation()
