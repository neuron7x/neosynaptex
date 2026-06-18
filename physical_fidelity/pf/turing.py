"""MFN Turing instability, operationalized (GAP-M-03).

The Plan cited the Turing condition but never named the reaction terms, the
homogeneous steady state, the Jacobian, or the critical diffusion ratio -- so the
test could not be run. Here we close all four for a concrete, literature-standard
model (Schnakenberg) and provide a *generic* analyzer for any 2-component system.

A homogeneous steady state (u*, v*) is Turing-unstable iff:

    (T1) tr J < 0                         (stable without diffusion)
    (T2) det J > 0                        (stable without diffusion)
    (T3) D_v f_u + D_u g_v > 0            (diffusion can destabilize)
    (T4) (D_v f_u + D_u g_v)^2 > 4 D_u D_v det J   (some band actually grows)

with critical wavenumber ``k_c^2 = sqrt(det J / (D_u D_v))`` at onset.

References
----------
* Turing, A. (1952). The chemical basis of morphogenesis. Phil. Trans. R. Soc. B.
* Murray, J.D. (2003). Mathematical Biology II, Ch. 2. Springer.
* Schnakenberg, J. (1979). Simple chemical reaction systems with limit cycle
  behaviour. J. Theor. Biol. 81(3), 389-400.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]
Jacobian = NDArray[np.float64]  # 2x2


@dataclass(frozen=True)
class TuringVerdict:
    """Full Turing analysis of a 2-component reaction-diffusion steady state."""

    steady_state: tuple[float, float]
    jacobian: tuple[tuple[float, float], tuple[float, float]]
    trace: float
    det: float
    cond_t1_trace_neg: bool
    cond_t2_det_pos: bool
    cond_t3_diff_term_pos: bool
    cond_t4_band_grows: bool
    is_turing_unstable: bool
    k_critical_sq: float
    max_growth_rate: float


def schnakenberg_steady_state(a: float, b: float) -> tuple[float, float]:
    """Schnakenberg homogeneous steady state: u* = a+b, v* = b/(a+b)^2."""
    u = a + b
    v = b / (a + b) ** 2
    return float(u), float(v)


def schnakenberg_jacobian(a: float, b: float) -> Jacobian:
    """Reaction Jacobian of Schnakenberg (f = a - u + u^2 v, g = b - u^2 v) at SS."""
    u, v = schnakenberg_steady_state(a, b)
    f_u = -1.0 + 2.0 * u * v
    f_v = u * u
    g_u = -2.0 * u * v
    g_v = -u * u
    return np.array([[f_u, f_v], [g_u, g_v]], dtype=np.float64)


def dispersion_growth_rate(jac: Jacobian, d_u: float, d_v: float, k_sq: float) -> float:
    """Largest real part of the eigenvalues of ``J - k^2 diag(D_u, D_v)``."""
    m = jac - k_sq * np.diag([d_u, d_v])
    return float(np.max(np.real(np.linalg.eigvals(m))))


def analyze_turing(jac: Jacobian, d_u: float, d_v: float, *, k_max: float = 20.0) -> TuringVerdict:
    """Generic Turing analysis for any 2-component reaction-diffusion Jacobian."""
    f_u, f_v = float(jac[0, 0]), float(jac[0, 1])
    g_u, g_v = float(jac[1, 0]), float(jac[1, 1])
    tr = f_u + g_v
    det = f_u * g_v - f_v * g_u
    diff_term = d_v * f_u + d_u * g_v
    t1 = tr < 0
    t2 = det > 0
    t3 = diff_term > 0
    t4 = diff_term**2 > 4.0 * d_u * d_v * det
    unstable = bool(t1 and t2 and t3 and t4)
    kc_sq = float(np.sqrt(det / (d_u * d_v))) if (det > 0 and d_u > 0 and d_v > 0) else float("nan")
    ks = np.linspace(0.0, k_max, 2000) ** 2
    growth = np.array([dispersion_growth_rate(jac, d_u, d_v, k) for k in ks])
    return TuringVerdict(
        steady_state=(float("nan"), float("nan")),
        jacobian=((f_u, f_v), (g_u, g_v)),
        trace=tr,
        det=det,
        cond_t1_trace_neg=t1,
        cond_t2_det_pos=t2,
        cond_t3_diff_term_pos=t3,
        cond_t4_band_grows=t4,
        is_turing_unstable=unstable,
        k_critical_sq=kc_sq,
        max_growth_rate=float(growth.max()),
    )


def analyze_schnakenberg(a: float, b: float, d_u: float, d_v: float) -> TuringVerdict:
    """Convenience: full Turing verdict for the Schnakenberg model."""
    jac = schnakenberg_jacobian(a, b)
    v = analyze_turing(jac, d_u, d_v)
    ss = schnakenberg_steady_state(a, b)
    return TuringVerdict(
        steady_state=ss,
        jacobian=v.jacobian,
        trace=v.trace,
        det=v.det,
        cond_t1_trace_neg=v.cond_t1_trace_neg,
        cond_t2_det_pos=v.cond_t2_det_pos,
        cond_t3_diff_term_pos=v.cond_t3_diff_term_pos,
        cond_t4_band_grows=v.cond_t4_band_grows,
        is_turing_unstable=v.is_turing_unstable,
        k_critical_sq=v.k_critical_sq,
        max_growth_rate=v.max_growth_rate,
    )


def critical_diffusion_ratio(jac: Jacobian, *, lo: float = 1.0, hi: float = 1e4) -> float:
    """Smallest d = D_v/D_u (with D_u=1) admitting Turing instability (bisection)."""
    f_u, f_v = float(jac[0, 0]), float(jac[0, 1])
    g_u, g_v = float(jac[1, 0]), float(jac[1, 1])
    det = f_u * g_v - f_v * g_u

    def grows(d: float) -> bool:
        diff_term = d * f_u + g_v
        return diff_term > 0 and diff_term**2 > 4.0 * 1.0 * d * det

    if not grows(hi):
        return float("nan")
    a, b = lo, hi
    for _ in range(100):
        mid = 0.5 * (a + b)
        if grows(mid):
            b = mid
        else:
            a = mid
    return float(b)


def reaction_diffusion_rhs(
    f: Callable[[Array, Array], Array],
    g: Callable[[Array, Array], Array],
    d_u: float,
    d_v: float,
    dx: float,
) -> Callable[[Array, Array], tuple[Array, Array]]:
    """Build a periodic 1-D FTCS RHS for verifying onset against the linear theory."""

    def laplacian(field: Array) -> Array:
        return (np.roll(field, 1) + np.roll(field, -1) - 2.0 * field) / (dx * dx)

    def rhs(u: Array, v: Array) -> tuple[Array, Array]:
        return d_u * laplacian(u) + f(u, v), d_v * laplacian(v) + g(u, v)

    return rhs
