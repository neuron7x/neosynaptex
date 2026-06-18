"""GeoSync mathematical object (GAP-O-02): Kuramoto + discrete Ricci flow.

The audit (GAP-O-02) found the Plan invoked Kuramoto (graph ODE on S^1) and
Ricci flow (manifold PDE) without a coupling. We resolve this by committing to
a **single, well-posed** object: a graph-Kuramoto system whose coupling weights
are evolved by a **discrete (Ollivier-style) Ricci flow that conserves total
graph weight**. Both halves are specified below; the coupling map is explicit.

Equations
---------
Phase dynamics (graph Kuramoto, Sakaguchi phase-lag alpha optional)::

    theta_dot_i = omega_i + (K / d_i) * sum_j w_ij(t) * sin(theta_j - theta_i - alpha)

with d_i = sum_j w_ij the weighted degree.  Coupling weights w_ij(t) >= 0 evolve
by normalized discrete Ricci flow::

    w_ij <- w_ij * (1 - eps * kappa_ij)          (flow)
    w_ij <- w_ij * (W0 / sum_kl w_kl)            (renormalize: conserves total W0)

where kappa_ij is a graph (Ollivier-Lin) curvature proxy. Renormalization makes
**total edge weight a conserved invariant** -- the falsifiable physical contract
the operator requested.

Well-posedness: w_ij(t) stays bounded in [0, W0], so the Kuramoto RHS is globally
Lipschitz in theta; by Picard-Lindelof the IVP has a unique solution. The flow
map is a bounded contraction on the weight simplex scaled by W0.

References
----------
* Kuramoto, Y. (1984). Chemical Oscillations, Waves, and Turbulence. Springer.
* Dorfler, F. & Bullo, F. (2014). Synchronization in complex networks of phase
  oscillators: a survey. Automatica 50(6), 1539-1564.
* Ollivier, Y. (2009). Ricci curvature of Markov chains on metric spaces.
  J. Funct. Anal. 256(3), 810-864.
* Ni, C.-C. et al. (2019). Community detection on networks with Ricci flow.
  Scientific Reports 9, 9984.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


# --------------------------------------------------------------------------- #
# Observables
# --------------------------------------------------------------------------- #
def order_parameter(theta: Array) -> tuple[float, float]:
    """Kuramoto complex order parameter ``r e^{i psi}``.

    Returns ``(r, psi)`` with ``r in [0, 1]`` by construction (triangle
    inequality on unit phasors). ``r`` is the synchronization magnitude.
    """
    z = np.mean(np.exp(1j * np.asarray(theta, dtype=np.float64)))
    return float(np.abs(z)), float(np.angle(z))


def incoherent_order_parameter_scale(n: int) -> float:
    """Expected order parameter for ``n`` i.i.d. uniform phases (K=0 null model).

    For n unit phasors with uniform random angles, ``E[r] = (sqrt(pi)/2)/sqrt(n)``
    to leading order (Rayleigh limit of the resultant length). This is the
    O(1/sqrt(N)) finite-size floor the audit (GAP-M-05) and the operator's
    scaling note both reference.
    """
    return float(np.sqrt(np.pi) / 2.0 / np.sqrt(n))


def mean_field_critical_coupling_lorentzian(gamma: float) -> float:
    """All-to-all Kuramoto critical coupling for Lorentzian frequencies.

    For ``g(omega) = gamma / (pi (omega^2 + gamma^2))`` the mean-field onset is
    ``K_c = 2 / (pi g(0)) = 2 gamma`` (Kuramoto 1984; Strogatz 2000).
    """
    if gamma <= 0:
        raise ValueError("gamma must be positive")
    return 2.0 * gamma


def fiedler_value(weights: Array) -> float:
    """Algebraic connectivity lambda_2 of the weighted graph Laplacian.

    NOTE (correction to NFI-GAP-001 GAP-O-02 corrective text): the smallest
    Laplacian eigenvalue is identically 0 (constant eigenvector), so the cited
    ``K_c = 2 omega_max / lambda_min(L)`` is singular. The Dorfler-Bullo
    connectivity bound uses the **Fiedler value** lambda_2 (second-smallest).
    """
    w = np.asarray(weights, dtype=np.float64)
    deg = np.diag(w.sum(axis=1))
    lap = deg - w
    eig = np.linalg.eigvalsh(lap)
    return float(eig[1])


def dorfler_bullo_sync_bound(omega: Array, weights: Array) -> float:
    """Sufficient coupling for synchronization (connectivity heuristic).

    ``K_c <= 2 * (omega_max - omega_min) / lambda_2(L)`` -- a conservative
    Dorfler-Bullo-style bound. Above this the locked state exists.
    """
    omega = np.asarray(omega, dtype=np.float64)
    spread = float(omega.max() - omega.min())
    lam2 = fiedler_value(weights)
    if lam2 <= 1e-12:
        return float("inf")
    return 2.0 * spread / lam2


# --------------------------------------------------------------------------- #
# Kuramoto integrator (hand-rolled RK4 -- solver-independent reference, GAP-E-06)
# --------------------------------------------------------------------------- #
def kuramoto_rhs(theta: Array, omega: Array, k: float, w: Array, alpha: float) -> Array:
    deg = w.sum(axis=1)
    deg = np.where(deg > 0, deg, 1.0)
    diff = theta[None, :] - theta[:, None] - alpha
    coupling = (w * np.sin(diff)).sum(axis=1)
    out: Array = np.asarray(omega + (k / deg) * coupling, dtype=np.float64)
    return out


@dataclass(frozen=True)
class KuramotoResult:
    """Trajectory summary of a Kuramoto integration."""

    theta_final: Array
    r_series: Array
    t: Array

    @property
    def r_final(self) -> float:
        return float(self.r_series[-1])

    @property
    def r_mean_tail(self) -> float:
        tail = self.r_series[len(self.r_series) // 2 :]
        return float(np.mean(tail))


def integrate_kuramoto(
    omega: Array,
    weights: Array,
    k: float,
    *,
    t_end: float = 50.0,
    dt: float = 0.01,
    alpha: float = 0.0,
    theta0: Array | None = None,
    seed: int = 0,
) -> KuramotoResult:
    """Deterministic RK4 integration of graph Kuramoto. dt is caller's CFL choice."""
    omega = np.asarray(omega, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    n = omega.shape[0]
    rng = np.random.default_rng(seed)
    theta: Array = np.asarray(
        theta0 if theta0 is not None else rng.uniform(-np.pi, np.pi, size=n),
        dtype=np.float64,
    ).copy()
    steps = int(round(t_end / dt))
    r_series = np.empty(steps + 1, dtype=np.float64)
    r_series[0] = order_parameter(theta)[0]
    for s in range(steps):
        k1 = kuramoto_rhs(theta, omega, k, w, alpha)
        k2 = kuramoto_rhs(theta + 0.5 * dt * k1, omega, k, w, alpha)
        k3 = kuramoto_rhs(theta + 0.5 * dt * k2, omega, k, w, alpha)
        k4 = kuramoto_rhs(theta + dt * k3, omega, k, w, alpha)
        theta = theta + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        r_series[s + 1] = order_parameter(theta)[0]
    t = np.linspace(0.0, steps * dt, steps + 1)
    return KuramotoResult(
        theta_final=np.mod(theta + np.pi, 2 * np.pi) - np.pi, r_series=r_series, t=t
    )


# --------------------------------------------------------------------------- #
# Discrete Ricci flow with total-weight conservation (operator's invariant)
# --------------------------------------------------------------------------- #
def ollivier_lin_curvature(weights: Array) -> Array:
    """Graph (Lin-Lu-Yau-style) curvature proxy per edge from common neighbours.

    kappa_ij = (#common neighbours of i,j) / max(deg_i, deg_j) - bridge penalty.
    Positive on dense/clustered edges, negative on bridges -- the sign structure
    that drives Ricci-flow community separation. This is a *proxy*; exact
    Ollivier curvature needs an optimal-transport solve per edge.
    """
    w = np.asarray(weights, dtype=np.float64)
    adj = (w > 0).astype(np.float64)
    deg = adj.sum(axis=1)
    common = adj @ adj  # common-neighbour counts
    n = w.shape[0]
    kappa = np.zeros_like(w)
    for i in range(n):
        for j in range(n):
            if adj[i, j] > 0 and i != j:
                denom = max(deg[i], deg[j], 1.0)
                kappa[i, j] = common[i, j] / denom - 1.0 / denom
    return kappa


def ricci_flow_step(weights: Array, eps: float = 0.1) -> Array:
    """One normalized discrete Ricci-flow step. Conserves total weight exactly.

    Flow ``w <- w (1 - eps kappa)`` then renormalize to the original total. The
    renormalization is what makes ``sum w`` a conserved invariant (analogous to
    volume-normalized Ricci flow). Weights are clamped to be non-negative.
    """
    w: Array = np.asarray(weights, dtype=np.float64).copy()
    total0 = w.sum()
    if total0 <= 0:
        return w
    kappa = ollivier_lin_curvature(w)
    w = w * (1.0 - eps * kappa)
    w = np.maximum(w, 0.0)
    total1 = w.sum()
    if total1 > 0:
        w *= total0 / total1
    out: Array = np.asarray(w, dtype=np.float64)
    return out


def ricci_flow(weights: Array, steps: int, eps: float = 0.1) -> tuple[Array, Array]:
    """Run ``steps`` of normalized Ricci flow. Returns (final_weights, total_history)."""
    w = np.asarray(weights, dtype=np.float64).copy()
    totals = np.empty(steps + 1, dtype=np.float64)
    totals[0] = w.sum()
    for s in range(steps):
        w = ricci_flow_step(w, eps)
        totals[s + 1] = w.sum()
    return w, totals
