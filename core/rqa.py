"""Recurrence Quantification Analysis (RQA) for gamma traces.

Metrics:
  - RR:  Recurrence Rate
  - DET: Determinism (fraction of recurrent points forming diagonal lines)
  - LAM: Laminarity (fraction forming vertical lines)
  - ENT: Diagonal line length entropy

Takens embedding: embed_dim >= 2*D+1 (D = estimated dimension).
Auto-selects tau via Average Mutual Information (AMI) if not provided.
"""

from __future__ import annotations

__all__ = ["recurrence_quantification"]

import numpy as np


def _ami_tau(signal: np.ndarray, max_tau: int = 20, bins: int = 16) -> int:
    """Select embedding delay via first minimum of Average Mutual Information."""
    n = len(signal)
    if n < max_tau + 2:
        return 1

    best_tau = 1
    prev_ami = float("inf")

    for tau in range(1, min(max_tau + 1, n // 3)):
        x = signal[: n - tau]
        y = signal[tau:]

        # Joint histogram
        counts_xy, _, _ = np.histogram2d(x, y, bins=bins)
        p_xy = counts_xy / counts_xy.sum()

        # Marginals
        p_x = p_xy.sum(axis=1)
        p_y = p_xy.sum(axis=0)

        # MI = sum p(x,y) * log(p(x,y) / (p(x)*p(y)))
        mi = 0.0
        for i in range(bins):
            for j in range(bins):
                if p_xy[i, j] > 0 and p_x[i] > 0 and p_y[j] > 0:
                    mi += p_xy[i, j] * np.log2(p_xy[i, j] / (p_x[i] * p_y[j]))

        if mi > prev_ami:
            best_tau = tau - 1
            break
        prev_ami = mi
        best_tau = tau

    return max(1, best_tau)


def _embed_nd(signal: np.ndarray, dim: int, tau: int) -> np.ndarray:
    """Takens time-delay embedding."""
    n = len(signal)
    m = n - (dim - 1) * tau
    if m <= 0:
        return np.empty((0, dim))
    embedded = np.empty((m, dim))
    for d in range(dim):
        embedded[:, d] = signal[d * tau : d * tau + m]
    return embedded


def _recurrence_matrix(embedded: np.ndarray, threshold: float) -> np.ndarray:
    """Binary recurrence matrix: R[i,j] = 1 if ||x_i - x_j|| < threshold."""
    n = len(embedded)
    dists = np.zeros((n, n))
    for i in range(n):
        dists[i] = np.linalg.norm(embedded - embedded[i], axis=1)
    return (dists < threshold).astype(int)


def _diagonal_lines(R: np.ndarray, min_len: int = 2) -> list[int]:
    """Extract lengths of diagonal lines from recurrence matrix."""
    n = R.shape[0]
    lengths = []
    for offset in range(1, n):
        diag = np.diag(R, offset)
        count = 0
        for val in diag:
            if val:
                count += 1
            else:
                if count >= min_len:
                    lengths.append(count)
                count = 0
        if count >= min_len:
            lengths.append(count)
    return lengths


def _vertical_lines(R: np.ndarray, min_len: int = 2) -> list[int]:
    """Extract lengths of vertical lines from recurrence matrix."""
    n = R.shape[0]
    lengths = []
    for col in range(n):
        count = 0
        for row in range(n):
            if R[row, col]:
                count += 1
            else:
                if count >= min_len:
                    lengths.append(count)
                count = 0
        if count >= min_len:
            lengths.append(count)
    return lengths


def recurrence_quantification(
    signal: np.ndarray,
    embedding_dim: int = 3,
    tau: int | None = None,
    threshold: float = 0.1,
    n_surrogate: int = 200,
    seed: int = 42,
) -> dict[str, object]:
    """Recurrence Quantification Analysis.

    Returns:
        {rr, det, lam, ent, tau_used, p_value}

    rr:  Recurrence Rate
    det: Determinism
    lam: Laminarity
    ent: Shannon entropy of diagonal line length distribution
    p_value: from IAAFT surrogate test on RR
    """
    signal = np.asarray(signal, dtype=np.float64)

    # Remove NaN
    signal = signal[np.isfinite(signal)]
    if len(signal) < embedding_dim * 3 + 5:
        return {
            "rr": float("nan"),
            "det": float("nan"),
            "lam": float("nan"),
            "ent": float("nan"),
            "tau_used": None,
            "p_value": float("nan"),
        }

    # Auto-select tau
    if tau is None:
        tau = _ami_tau(signal)

    # Embed
    embedded = _embed_nd(signal, embedding_dim, tau)
    n = len(embedded)
    if n < 5:
        return {
            "rr": float("nan"),
            "det": float("nan"),
            "lam": float("nan"),
            "ent": float("nan"),
            "tau_used": tau,
            "p_value": float("nan"),
        }

    # Adaptive threshold: fraction of max distance
    if threshold <= 0:
        threshold = 0.1
    dists_flat = []
    step = max(1, n // 50)
    for i in range(0, n, step):
        dists_flat.extend(np.linalg.norm(embedded - embedded[i], axis=1).tolist())
    eps = threshold * np.percentile(dists_flat, 95)
    eps = max(eps, 1e-10)

    # Recurrence matrix
    R = _recurrence_matrix(embedded, eps)

    # RR: recurrence rate (excluding main diagonal)
    np.fill_diagonal(R, 0)
    total_pairs = n * (n - 1)
    rr = float(R.sum() / total_pairs) if total_pairs > 0 else 0.0

    diag_lengths = _diagonal_lines(R)
    diag_total = sum(diag_lengths)
    rec_total = R.sum()
    det = float(diag_total / rec_total) if rec_total > 0 else 0.0

    vert_lengths = _vertical_lines(R)
    vert_total = sum(vert_lengths)
    lam = float(vert_total / rec_total) if rec_total > 0 else 0.0

    # ENT: Shannon entropy of diagonal line lengths
    if diag_lengths:
        lengths_arr = np.array(diag_lengths, dtype=float)
        p = lengths_arr / lengths_arr.sum()
        ent = -float(np.sum(p * np.log2(p + 1e-15)))
    else:
        ent = 0.0

    # Surrogate test for RR significance
    rng = np.random.default_rng(seed)
    count_ge = 0
    sorted_sig = np.sort(signal)
    fft_amp = np.abs(np.fft.rfft(signal))

    for _ in range(n_surrogate):
        # IAAFT surrogate
        surr = rng.permutation(signal).copy()
        for _iter in range(10):
            fft_s = np.fft.rfft(surr)
            phases = np.angle(fft_s)
            fft_new = fft_amp * np.exp(1j * phases)
            surr = np.fft.irfft(fft_new, n=len(signal))
            rank = np.argsort(np.argsort(surr))
            surr = sorted_sig[rank]

        emb_surr = _embed_nd(surr, embedding_dim, tau)
        if len(emb_surr) < 5:
            continue
        R_surr = _recurrence_matrix(emb_surr, eps)
        np.fill_diagonal(R_surr, 0)
        rr_surr = float(R_surr.sum() / total_pairs) if total_pairs > 0 else 0.0
        if rr_surr >= rr:
            count_ge += 1

    p_value = float((count_ge + 1) / (n_surrogate + 1))

    return {
        "rr": round(rr, 6),
        "det": round(det, 6),
        "lam": round(lam, 6),
        "ent": round(ent, 6),
        "tau_used": tau,
        "p_value": round(p_value, 6),
    }
