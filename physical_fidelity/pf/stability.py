"""Numerical stability (GAP-M-04) and regime-conditioned Lyapunov (GAP-M-05).

GAP-M-04: the Plan applied the CFL condition ``dt <= dx/c`` (hyperbolic) to a
parabolic reaction-diffusion system. The correct explicit-scheme limit for
diffusion is ``dt <= dx^2 / (2 d D)`` in d spatial dimensions. These differ by a
factor O(dx) and conflating them mis-sizes the timestep by orders of magnitude.

GAP-M-05: the Plan set absolute MLE targets (``MLE ~ 0`` for GeoSync, ``MLE < 0``
for BN-Syn) that contradict the dynamics in the stated regimes. MLE sign is a
*function of regime*, so we expose a regime-conditioned classifier and a finite-N
caveat (the Kuramoto critical point only has MLE -> 0 as N -> inf).

References
----------
* Strikwerda, J. (2004). Finite Difference Schemes and PDEs. SIAM.
* Benettin, G. et al. (1980). Lyapunov characteristic exponents... Meccanica.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def cfl_dt_hyperbolic(dx: float, c: float, *, courant: float = 1.0) -> float:
    """Stable timestep for an explicit hyperbolic scheme: dt <= courant * dx / c."""
    if c <= 0 or dx <= 0:
        raise ValueError("dx and c must be positive")
    return courant * dx / c


def diffusion_dt_parabolic(dx: float, d_max: float, *, ndim: int = 2, safety: float = 0.9) -> float:
    """Stable timestep for an explicit parabolic (diffusion) scheme.

    ``dt <= dx^2 / (2 * ndim * D_max)`` for d-dimensional FTCS diffusion.
    This is the condition the Plan SHOULD have used for MFN, not CFL.
    """
    if d_max <= 0 or dx <= 0:
        raise ValueError("dx and D_max must be positive")
    return safety * dx * dx / (2.0 * ndim * d_max)


@dataclass(frozen=True)
class StabilityComparison:
    """Side-by-side of the two timestep limits and their ratio."""

    dt_hyperbolic: float
    dt_parabolic: float
    ratio: float  # how much smaller the (correct) parabolic step is


def compare_cfl_vs_diffusion(
    dx: float, c: float, d_max: float, *, ndim: int = 2
) -> StabilityComparison:
    """Quantify the GAP-M-04 error: parabolic step is smaller by O(dx)."""
    dth = cfl_dt_hyperbolic(dx, c)
    dtp = diffusion_dt_parabolic(dx, d_max, ndim=ndim)
    return StabilityComparison(dt_hyperbolic=dth, dt_parabolic=dtp, ratio=dtp / dth)


# --------------------------------------------------------------------------- #
# Maximal Lyapunov exponent (Benettin) -- regime-conditioned
# --------------------------------------------------------------------------- #
def max_lyapunov(
    rhs: Callable[[Array], Array],
    x0: Array,
    *,
    dt: float = 0.01,
    n_steps: int = 20000,
    n_transient: int = 2000,
    delta0: float = 1e-8,
    seed: int = 0,
) -> float:
    """Maximal Lyapunov exponent via the Benettin two-trajectory rescaling method.

    Integrates a reference and a perturbed trajectory with RK4, renormalizing the
    separation each step and accumulating its log-growth. Positive => chaos,
    negative => contraction.
    """
    rng = np.random.default_rng(seed)
    x = np.asarray(x0, dtype=np.float64).copy()
    pert = rng.standard_normal(x.shape)
    pert = pert / np.linalg.norm(pert) * delta0
    xp = x + pert

    def step(state: Array) -> Array:
        k1 = rhs(state)
        k2 = rhs(state + 0.5 * dt * k1)
        k3 = rhs(state + 0.5 * dt * k2)
        k4 = rhs(state + dt * k3)
        return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

    for _ in range(n_transient):
        x = step(x)
        xp = step(xp)
        d = xp - x
        nrm = np.linalg.norm(d)
        if nrm > 0:
            xp = x + d / nrm * delta0

    log_sum = 0.0
    for _ in range(n_steps):
        x = step(x)
        xp = step(xp)
        d = xp - x
        nrm = np.linalg.norm(d)
        if nrm > 0:
            log_sum += np.log(nrm / delta0)
            xp = x + d / nrm * delta0
    return float(log_sum / (n_steps * dt))


def classify_regime(mle: float, *, eps: float = 1e-2) -> str:
    """Map an MLE to a regime label (GAP-M-05 regime-conditioned target)."""
    if mle > eps:
        return "chaotic/unstable (MLE>0)"
    if mle < -eps:
        return "contracting/stable (MLE<0)"
    return "neutral/critical (MLE~0)"
