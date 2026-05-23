# GEOSYNC-ACCEL — Python Integration Layer
#
# Provides transparent fallback between Rust-accelerated and pure-Python
# implementations of gamma-scaling computation kernels.
#
# If the Rust extension `geosync_accel` is installed (via `maturin develop`),
# calls are routed to SIMD-accelerated Rust kernels with GIL release.
# Otherwise, falls back to numpy/scipy with identical semantics.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = [
    "compute_gamma_accel",
    "hilbert_sort",
    "hilbert_indices",
    "euclidean_distances",
    "simd_info",
    "ACCEL_BACKEND",
]

# ═══════════════════════════════════════════════════════════════════
# Backend detection: try Rust extension, fall back to numpy/scipy
# ═══════════════════════════════════════════════════════════════════

try:
    import geosync_accel as _rust

    ACCEL_BACKEND: str = "rust+simd"
except ImportError:
    _rust = None
    ACCEL_BACKEND = "numpy"


# ═══════════════════════════════════════════════════════════════════
# Gamma computation — unified interface
# ═══════════════════════════════════════════════════════════════════


def compute_gamma_accel(
    topo: np.ndarray | list[float],
    cost: np.ndarray | list[float],
    *,
    min_pairs: int = 5,
    log_range_gate: float = 0.5,
    r2_gate: float = 0.3,
    bootstrap_n: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute gamma-scaling via Theil-Sen regression.

    Routes to Rust SIMD kernel when available, falls back to numpy/scipy.

    Returns dict with keys:
        gamma, r2, ci_low, ci_high, n_valid, verdict, bootstrap_gammas
    """
    topo_list = list(np.asarray(topo, dtype=np.float64).ravel())
    cost_list = list(np.asarray(cost, dtype=np.float64).ravel())

    if _rust is not None:
        return dict(
            _rust.compute_gamma(
                topo_list,
                cost_list,
                min_pairs=min_pairs,
                log_range_gate=log_range_gate,
                r2_gate=r2_gate,
                bootstrap_n=bootstrap_n,
                seed=seed,
            )
        )

    # numpy/scipy fallback — mirrors core.gamma.compute_gamma()
    from core.gamma import compute_gamma as _py_gamma

    result = _py_gamma(
        np.array(topo_list),
        np.array(cost_list),
        min_pairs=min_pairs,
        log_range_gate=log_range_gate,
        r2_gate=r2_gate,
        bootstrap_n=bootstrap_n,
        seed=seed,
    )
    return {
        "gamma": result.gamma,
        "r2": result.r2,
        "ci_low": result.ci_low,
        "ci_high": result.ci_high,
        "n_valid": result.n_valid,
        "verdict": result.verdict,
        "bootstrap_gammas": list(result.bootstrap_gammas),
    }


# ═══════════════════════════════════════════════════════════════════
# Hilbert curve spatial indexing
# ═══════════════════════════════════════════════════════════════════


def hilbert_sort(
    coords: list[tuple[float, float]] | np.ndarray,
    order: int = 16,
) -> list[int]:
    """Sort coordinates by Hilbert curve index for cache-optimal access.

    Returns permutation indices for Hilbert-optimal ordering.
    """
    if isinstance(coords, np.ndarray):
        coord_list = [(float(row[0]), float(row[1])) for row in coords]
    else:
        coord_list = list(coords)

    if _rust is not None:
        return list(_rust.hilbert_sort(coord_list, order=order))

    # Pure Python fallback (O(n log n) with simple Z-order approximation)
    return _hilbert_sort_fallback(coord_list, order)


def hilbert_indices(
    coords: list[tuple[float, float]] | np.ndarray,
    order: int = 16,
) -> list[int]:
    """Compute Hilbert curve indices for a batch of coordinates."""
    if isinstance(coords, np.ndarray):
        coord_list = [(float(row[0]), float(row[1])) for row in coords]
    else:
        coord_list = list(coords)

    if _rust is not None:
        return list(_rust.hilbert_indices(coord_list, order=order))

    # Fallback: Z-order (Morton code) approximation
    return _hilbert_indices_fallback(coord_list, order)


def _hilbert_sort_fallback(coords: list[tuple[float, float]], order: int) -> list[int]:
    """Pure Python Hilbert sort fallback using Z-order approximation."""
    indices = _hilbert_indices_fallback(coords, order)
    return sorted(range(len(coords)), key=lambda i: indices[i])


def _hilbert_indices_fallback(coords: list[tuple[float, float]], order: int) -> list[int]:
    """Pure Python Z-order (Morton code) index computation."""
    if not coords:
        return []

    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max(max_x - min_x, 1e-15)
    range_y = max(max_y - min_y, 1e-15)
    max_val = (1 << order) - 1

    results = []
    for x, y in coords:
        gx = int(((x - min_x) / range_x) * max_val)
        gy = int(((y - min_y) / range_y) * max_val)
        # Z-order interleave bits
        z = 0
        for bit in range(order):
            z |= ((gx >> bit) & 1) << (2 * bit)
            z |= ((gy >> bit) & 1) << (2 * bit + 1)
        results.append(z)
    return results


# ═══════════════════════════════════════════════════════════════════
# Euclidean distances — SIMD-dispatched
# ═══════════════════════════════════════════════════════════════════


def euclidean_distances(
    ax: np.ndarray | list[float],
    ay: np.ndarray | list[float],
    bx: float,
    by: float,
) -> list[float]:
    """SIMD-dispatched Euclidean distance from each (ax[i], ay[i]) to (bx, by)."""
    ax_list = list(np.asarray(ax, dtype=np.float64).ravel())
    ay_list = list(np.asarray(ay, dtype=np.float64).ravel())

    if _rust is not None:
        return list(_rust.euclidean_distances(ax_list, ay_list, bx, by))

    # numpy fallback
    ax_arr = np.array(ax_list)
    ay_arr = np.array(ay_list)
    return list(np.sqrt((ax_arr - bx) ** 2 + (ay_arr - by) ** 2))


# ═══════════════════════════════════════════════════════════════════
# System info
# ═══════════════════════════════════════════════════════════════════


def simd_info() -> dict[str, Any]:
    """Report SIMD capability level and system info."""
    if _rust is not None:
        return dict(_rust.simd_info())

    import os

    return {
        "simd_level": "numpy (no Rust extension)",
        "cache_line_bytes": 64,
        "f64_per_cache_line": 8,
        "num_cores": os.cpu_count() or 1,
        "features": [],
    }
