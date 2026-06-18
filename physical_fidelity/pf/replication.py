"""Independent replication + convergence (NFI-PROMPT-002 Section 5 A/D, GAP-E-06).

Two solver-independent checks on the canonical small Kuramoto scenario:

* **Convergence (5A)**: refine dt and measure the observed temporal order via
  Richardson differences. RK4 must show order p >= 3.5.
* **Independent replication (5D)**: a hand-rolled RK4 (dynamics.integrate_kuramoto)
  versus SciPy's adaptive ``solve_ivp`` (DOP853). On the canonical scenario
  (N=10, T=100) the trajectories must agree to relative L-inf <= 1e-4.

Julia's DifferentialEquations.jl is the protocol's preferred secondary solver but
is not installed in this environment; SciPy's independent adaptive integrator is
the sanctioned NumPy/SciPy fallback (NFI-PROMPT-002 5.D).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import solve_ivp

from .dynamics import integrate_kuramoto, kuramoto_rhs, order_parameter

Array = NDArray[np.float64]


@dataclass(frozen=True)
class ConvergenceResult:
    """Observed temporal order of accuracy."""

    dts: tuple[float, ...]
    errors: tuple[float, ...]
    observed_order: float


def convergence_order(
    omega: Array,
    weights: Array,
    k: float,
    *,
    t_end: float = 10.0,
    dt_base: float = 0.04,
    seed: int = 0,
) -> ConvergenceResult:
    """Estimate RK4 temporal order by Richardson refinement of the final phase.

    Uses the finest grid as reference; error is L-inf of theta_final on the
    common end time. Observed order p ~ log2(e_coarse / e_fine).
    """
    factors = [1.0, 0.5, 0.25, 0.125]
    finals = []
    for fct in factors:
        res = integrate_kuramoto(
            omega,
            weights,
            k,
            t_end=t_end,
            dt=dt_base * fct,
            theta0=_fixed_theta(omega, seed),
            seed=seed,
        )
        finals.append(np.mod(res.theta_final + np.pi, 2 * np.pi) - np.pi)
    ref = finals[-1]
    errs = [float(np.max(np.abs(np.angle(np.exp(1j * (f - ref)))))) for f in finals[:-1]]
    # successive ratios -> order via the two coarsest stable errors
    ratio = errs[0] / errs[1] if errs[1] > 0 else float("inf")
    order = float(np.log2(ratio)) if np.isfinite(ratio) and ratio > 0 else float("nan")
    return ConvergenceResult(
        dts=tuple(dt_base * f for f in factors[:-1]), errors=tuple(errs), observed_order=order
    )


def _fixed_theta(omega: Array, seed: int) -> Array:
    rng = np.random.default_rng(seed)
    out: Array = np.asarray(
        rng.uniform(-np.pi, np.pi, size=np.asarray(omega).shape[0]), dtype=np.float64
    )
    return out


@dataclass(frozen=True)
class ReplicationResult:
    """Cross-solver agreement on the order-parameter trajectory."""

    rel_linf: float
    passed: bool
    n: int
    t_end: float


def independent_replication(
    *, n: int = 10, t_end: float = 100.0, k: float = 1.5, tol: float = 1e-4, seed: int = 0
) -> ReplicationResult:
    """Hand-rolled RK4 vs SciPy DOP853 on the canonical scenario; rel L-inf <= tol."""
    rng = np.random.default_rng(seed)
    omega = rng.standard_normal(n)
    weights = np.ones((n, n)) - np.eye(n)
    theta0 = rng.uniform(-np.pi, np.pi, size=n)

    # primary: hand-rolled fixed-step RK4 (small dt for fair comparison)
    prim = integrate_kuramoto(omega, weights, k, t_end=t_end, dt=0.005, theta0=theta0, seed=seed)

    # secondary: SciPy adaptive DOP853 on the same vector field
    def rhs(_t: float, y: Array) -> Array:
        return kuramoto_rhs(y, omega, k, weights, 0.0)

    sol = solve_ivp(
        rhs, (0.0, t_end), theta0, method="DOP853", t_eval=prim.t, rtol=1e-10, atol=1e-12
    )
    r_prim = prim.r_series
    r_sec = np.array([order_parameter(sol.y[:, j])[0] for j in range(sol.y.shape[1])])
    scale = max(float(np.max(np.abs(r_prim))), 1e-12)
    rel = float(np.max(np.abs(r_prim - r_sec)) / scale)
    return ReplicationResult(rel_linf=rel, passed=bool(rel <= tol), n=n, t_end=t_end)
