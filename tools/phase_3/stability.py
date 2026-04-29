"""Window-sweep stability check.

The plan §1 PASS rule includes:

    |γ̂_obs − γ̂_obs(window_swept)| ≤ 0.05 for every window in sweep

i.e. γ must not depend on which contiguous sub-window of the
``(topo, cost)`` trajectory the estimator is fed. A large
``Δγ_max`` indicates an estimator artefact (sensitivity to range or
to a single critical-region pivot point) rather than a robust
scaling exponent.

This module provides the helper that computes the sweep and reports
``stable=True/False`` against a user-supplied threshold (default 0.05
per plan §7 test 7).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from tools.phase_3.estimator import estimate_gamma

__all__ = [
    "WindowSweepResult",
    "window_sweep",
]


@dataclasses.dataclass(frozen=True)
class WindowSweepResult:
    """Window-sweep stability summary.

    Attributes
    ----------
    windows : tuple of (int, int)
        Half-open ``(start, stop)`` index pairs actually evaluated.
    gammas : tuple of float
        γ̂ for each window.
    delta_gamma_max : float
        ``max(|γ̂_window − γ̂_full|)`` over the sweep. ``nan`` if the
        full-trajectory fit is degenerate.
    stable : bool
        ``delta_gamma_max <= threshold``. False if any window gives
        non-finite γ̂.
    threshold : float
        The threshold the verdict was evaluated against.
    """

    windows: tuple[tuple[int, int], ...]
    gammas: tuple[float, ...]
    delta_gamma_max: float
    stable: bool
    threshold: float


_DEFAULT_THRESHOLD: float = 0.05
_DEFAULT_N_WINDOWS: int = 4
_MIN_WINDOW_LEN: int = 5


def window_sweep(
    topo: np.ndarray,
    cost: np.ndarray,
    *,
    n_windows: int = _DEFAULT_N_WINDOWS,
    threshold: float = _DEFAULT_THRESHOLD,
) -> WindowSweepResult:
    """Sweep contiguous half-overlapping windows; return Δγ_max.

    The trajectory length ``N`` is partitioned into ``n_windows``
    overlapping windows of width ``2N/(n_windows+1)`` shifted by
    ``N/(n_windows+1)``. The full-trajectory γ̂ is the reference.
    """
    if n_windows < 1:
        raise ValueError(f"n_windows must be >= 1; got {n_windows}")
    if threshold <= 0.0:
        raise ValueError(f"threshold must be positive; got {threshold}")

    t = np.asarray(topo, dtype=np.float64).ravel()
    c = np.asarray(cost, dtype=np.float64).ravel()
    if t.shape != c.shape:
        raise ValueError(f"topo and cost must have identical shape; got {t.shape} vs {c.shape}")
    n_total = int(t.size)

    full = estimate_gamma(t, c)
    if full.degenerate or not np.isfinite(full.gamma):
        return WindowSweepResult(
            windows=(),
            gammas=(),
            delta_gamma_max=float("nan"),
            stable=False,
            threshold=threshold,
        )

    if n_total < _MIN_WINDOW_LEN * 2:
        return WindowSweepResult(
            windows=((0, n_total),),
            gammas=(float(full.gamma),),
            delta_gamma_max=0.0,
            stable=True,
            threshold=threshold,
        )

    width = max(_MIN_WINDOW_LEN, (2 * n_total) // (n_windows + 1))
    shift = max(1, n_total // (n_windows + 1))

    windows: list[tuple[int, int]] = []
    gammas: list[float] = []
    deltas: list[float] = []

    for i in range(n_windows):
        start = i * shift
        stop = min(start + width, n_total)
        if stop - start < _MIN_WINDOW_LEN:
            continue
        if start >= n_total:
            break
        sub = estimate_gamma(t[start:stop], c[start:stop])
        windows.append((int(start), int(stop)))
        gamma_w = float(sub.gamma)
        gammas.append(gamma_w)
        if np.isfinite(gamma_w):
            deltas.append(abs(gamma_w - float(full.gamma)))
        else:
            deltas.append(float("inf"))

    if not windows:
        return WindowSweepResult(
            windows=(),
            gammas=(),
            delta_gamma_max=float("nan"),
            stable=False,
            threshold=threshold,
        )

    delta_max = float(max(deltas))
    stable = bool(delta_max <= threshold)
    return WindowSweepResult(
        windows=tuple(windows),
        gammas=tuple(gammas),
        delta_gamma_max=delta_max,
        stable=stable,
        threshold=threshold,
    )
