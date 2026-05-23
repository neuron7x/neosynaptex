"""Coherence state-space model — discrete-time dynamical system for NFI coherence.

Task 1 deliverable (feat/task-1-2-coherence-state-space-fdt-gamma).

Formalizes the qualitative NFI "coherence + gamma + objection + noise" picture
into a concrete 4-dimensional state-space model

    x_t = (S, gamma, E_obj, sigma2)

with explicit transition f(x_t, u_t) -> x_{t+1}, observation h(x_t) -> y_t,
and stability helpers (Jacobian eigenvalues, convergence-time estimate, dS/dt
entropy-slope sign).

Design notes
------------
* INV-1 compliant: gamma is NEVER stored as a persistent attribute on any
  long-lived orchestrator / engine object. It appears only as an *element of
  a state vector* that is the explicit, derived output of step()/rollout(),
  i.e. a derived trajectory, not a cached scalar.
* No dependency on substrates / agents / evl — safe for core layer.
* Reuses numpy primitives only. Does not attempt to compete with
  ``core.coherence.transfer_entropy_gamma``; instead, it provides a *model*
  whose trajectories could be fed into that estimator.
* All arithmetic is deterministic given a seed. Noise is injected via an
  explicit ``numpy.random.Generator`` supplied by the caller.

The model
---------
State x = (S, g, E, v) with

    S     : coherence level in [0, 1]        (order parameter)
    g     : gamma scaling exponent (>0)       (regime indicator, derived elsewhere)
    E     : objection-energy proxy (>=0)      (opposition / adversarial load)
    v     : noise variance sigma^2 (>=0)      (stochastic bath amplitude)

Input u = (u_S, u_E) is an exogenous drive on coherence and objection.

Transition (discretised Lotka–Volterra-ish coupling around a metastable
fixed point at gamma = 1):

    S_{t+1}     = clip( S_t + dt * (alpha * (g_t - 1) * S_t
                                   - beta * E_t * S_t
                                   + u_S - kappa * (S_t - 0.5))
                        + noise_S, 0, 1 )
    g_{t+1}     = g_t + dt * (-lam_g * (g_t - g_target) + mu_g * (S_t - 0.5))
    E_{t+1}     = max(0, E_t + dt * (-lam_E * E_t + nu_E * (1 - S_t) + u_E))
    v_{t+1}     = max(0, (1 - rho) * v_t + rho * v_target)

where noise_S ~ N(0, v_t).

This is intentionally a *minimal* model — not a scientific claim about NFI
dynamics, but a concrete, analysable surrogate on which the estimators
(Task 2 FDT γ-estimator, Tasks 3–7 ...) can be validated.

Stability
---------
Linearising around the metastable fixed point
``x* = (S*, g_target, E*, v_target)`` with ``S* = 0.5, E* = 0`` (when
``u_S = u_E = 0``, ``g_target = 1``), the Jacobian is closed-form; see
``CoherenceStateSpace.linearized_jacobian``. The system is asymptotically
stable iff all eigenvalues of that matrix lie strictly inside the unit
circle. ``convergence_time()`` converts the spectral radius into an
e-folding timescale ``tau = -1 / log(rho)``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "CoherenceState",
    "CoherenceStateSpaceParams",
    "CoherenceStateSpace",
    "StabilityReport",
]

FloatArray = NDArray[np.float64]

# ------------------------------------------------------------------
# State + parameters
# ------------------------------------------------------------------


@dataclass(frozen=True)
class CoherenceState:
    """Immutable state of the coherence state-space model.

    Attributes:
        S: coherence order parameter in [0, 1].
        gamma: gamma scaling exponent (> 0). Derived-observable; held as a
            trajectory element only, not as an orchestrator attribute
            (INV-1 compliant).
        E_obj: objection-energy proxy, >= 0.
        sigma2: noise variance, >= 0.
    """

    S: float
    gamma: float
    E_obj: float
    sigma2: float

    def as_vector(self) -> FloatArray:
        return np.array([self.S, self.gamma, self.E_obj, self.sigma2], dtype=np.float64)

    @classmethod
    def from_vector(cls, v: FloatArray) -> CoherenceState:
        if v.shape != (4,):
            raise ValueError(f"state vector must have shape (4,), got {v.shape}")
        return cls(S=float(v[0]), gamma=float(v[1]), E_obj=float(v[2]), sigma2=float(v[3]))


@dataclass(frozen=True)
class CoherenceStateSpaceParams:
    """Parameters of the discrete-time coherence state-space model.

    Defaults are chosen so that the metastable fixed point
    ``(S*, g_target, 0, v_target)`` is asymptotically stable.
    """

    dt: float = 0.1
    alpha: float = 0.8
    beta: float = 0.6
    kappa: float = 0.5
    lam_g: float = 1.2
    mu_g: float = 0.1
    g_target: float = 1.0
    lam_e: float = 1.5
    nu_e: float = 0.3
    rho: float = 0.2
    v_target: float = 1e-3
    observation_noise: float = 0.0

    def __post_init__(self) -> None:
        if self.dt <= 0:
            raise ValueError("dt must be positive")
        if not 0 < self.rho <= 1:
            raise ValueError("rho must be in (0, 1]")
        if self.v_target < 0 or self.observation_noise < 0:
            raise ValueError("variances must be non-negative")


# ------------------------------------------------------------------
# Stability report
# ------------------------------------------------------------------


@dataclass(frozen=True)
class StabilityReport:
    """Linear-stability analysis around a fixed point."""

    eigenvalues: FloatArray
    spectral_radius: float
    is_stable: bool
    convergence_time: float
    entropy_slope: float


# ------------------------------------------------------------------
# Main class
# ------------------------------------------------------------------


_STATE_DIM: Final[int] = 4


class CoherenceStateSpace:
    """Discrete-time coherence state-space model.

    Usage:

    >>> import numpy as np
    >>> from core.coherence_state_space import (
    ...     CoherenceStateSpace, CoherenceState, CoherenceStateSpaceParams,
    ... )
    >>> params = CoherenceStateSpaceParams()
    >>> model = CoherenceStateSpace(params)
    >>> x0 = CoherenceState(S=0.4, gamma=1.1, E_obj=0.05, sigma2=1e-3)
    >>> rng = np.random.default_rng(0)
    >>> traj = model.rollout(x0, n_steps=50, rng=rng)
    >>> traj.shape
    (51, 4)
    """

    state_dim: Final[int] = _STATE_DIM
    obs_dim: Final[int] = 2  # we expose (S, gamma) as observables by default

    def __init__(self, params: CoherenceStateSpaceParams | None = None) -> None:
        self.params: CoherenceStateSpaceParams = params or CoherenceStateSpaceParams()

    # -- Transition ------------------------------------------------

    def step(
        self,
        state: CoherenceState,
        u: tuple[float, float] = (0.0, 0.0),
        rng: np.random.Generator | None = None,
    ) -> CoherenceState:
        """Advance the state one timestep under input ``u``.

        Args:
            state: current state.
            u: exogenous input ``(u_S, u_E)``.
            rng: RNG used for the coherence-channel noise term. If None, a
                deterministic default is used (zero noise).

        Returns:
            New ``CoherenceState``.
        """
        p = self.params
        u_S, u_E = float(u[0]), float(u[1])

        noise_S = 0.0 if rng is None else float(rng.normal(0.0, np.sqrt(max(state.sigma2, 0.0))))

        dS = (
            p.alpha * (state.gamma - 1.0) * state.S
            - p.beta * state.E_obj * state.S
            + u_S
            - p.kappa * (state.S - 0.5)
        )
        S_new = float(np.clip(state.S + p.dt * dS + noise_S, 0.0, 1.0))

        dg = -p.lam_g * (state.gamma - p.g_target) + p.mu_g * (state.S - 0.5)
        g_new = float(state.gamma + p.dt * dg)

        dE = -p.lam_e * state.E_obj + p.nu_e * (1.0 - state.S) + u_E
        E_new = max(0.0, float(state.E_obj + p.dt * dE))

        v_new = max(0.0, float((1.0 - p.rho) * state.sigma2 + p.rho * p.v_target))

        return CoherenceState(S=S_new, gamma=g_new, E_obj=E_new, sigma2=v_new)

    # -- Observation ----------------------------------------------

    def observe(
        self,
        state: CoherenceState,
        rng: np.random.Generator | None = None,
    ) -> FloatArray:
        """Observation equation ``h(x)`` — returns ``(S, gamma)`` with optional noise."""
        y = np.array([state.S, state.gamma], dtype=np.float64)
        if self.params.observation_noise > 0.0 and rng is not None:
            y = y + rng.normal(0.0, self.params.observation_noise, size=y.shape)
        return y

    # -- Rollout ---------------------------------------------------

    def rollout(
        self,
        initial: CoherenceState,
        n_steps: int,
        inputs: FloatArray | None = None,
        rng: np.random.Generator | None = None,
    ) -> FloatArray:
        """Run the model for ``n_steps`` steps and return the full trajectory.

        Args:
            initial: starting state.
            n_steps: number of transition steps (not counting the initial state).
            inputs: optional ``(n_steps, 2)`` array of inputs; defaults to zero.
            rng: RNG for stochastic noise.

        Returns:
            Array of shape ``(n_steps + 1, 4)``. Row 0 is ``initial``.
        """
        if n_steps < 0:
            raise ValueError("n_steps must be non-negative")
        if inputs is None:
            inputs_arr = np.zeros((n_steps, 2), dtype=np.float64)
        else:
            inputs_arr = np.asarray(inputs, dtype=np.float64)
            if inputs_arr.shape != (n_steps, 2):
                raise ValueError(f"inputs must have shape ({n_steps}, 2), got {inputs_arr.shape}")

        traj = np.empty((n_steps + 1, _STATE_DIM), dtype=np.float64)
        traj[0] = initial.as_vector()
        state = initial
        for t in range(n_steps):
            state = self.step(state, (float(inputs_arr[t, 0]), float(inputs_arr[t, 1])), rng)
            traj[t + 1] = state.as_vector()
        return traj

    def observe_trajectory(
        self,
        trajectory: FloatArray,
        rng: np.random.Generator | None = None,
    ) -> FloatArray:
        """Apply ``observe`` row-wise to a state trajectory."""
        if trajectory.ndim != 2 or trajectory.shape[1] != _STATE_DIM:
            raise ValueError(
                f"trajectory must have shape (T, {_STATE_DIM}), got {trajectory.shape}"
            )
        out = np.empty((trajectory.shape[0], self.obs_dim), dtype=np.float64)
        for i in range(trajectory.shape[0]):
            out[i] = self.observe(CoherenceState.from_vector(trajectory[i]), rng)
        return out

    # -- Stability analysis ---------------------------------------

    def linearized_jacobian(self, fixed_point: CoherenceState) -> FloatArray:
        """Jacobian of the deterministic (noise-free) transition at ``fixed_point``.

        Derivation: we differentiate the discrete map
        ``x_{t+1} = x_t + dt * F(x_t) + G(x_t)`` (for rows S, g, E; the
        sigma2 row is a linear contraction toward ``v_target``).

        Returns:
            4x4 ``numpy.ndarray`` of ``dx_{t+1}/dx_t``.
        """
        p = self.params
        S = fixed_point.S
        g = fixed_point.gamma
        E = fixed_point.E_obj

        # dS_{t+1}/dx
        dS_dS = 1.0 + p.dt * (p.alpha * (g - 1.0) - p.beta * E - p.kappa)
        dS_dg = p.dt * p.alpha * S
        dS_dE = -p.dt * p.beta * S
        dS_dv = 0.0

        # dg_{t+1}/dx
        dg_dS = p.dt * p.mu_g
        dg_dg = 1.0 - p.dt * p.lam_g
        dg_dE = 0.0
        dg_dv = 0.0

        # dE_{t+1}/dx  (valid where E > 0; at E == 0 the clamp is one-sided,
        # but for local stability of interior fixed points this is fine)
        dE_dS = -p.dt * p.nu_e
        dE_dg = 0.0
        dE_dE = 1.0 - p.dt * p.lam_e
        dE_dv = 0.0

        # dv_{t+1}/dx  (only depends on v)
        dv_dS = 0.0
        dv_dg = 0.0
        dv_dE = 0.0
        dv_dv = 1.0 - p.rho

        return np.array(
            [
                [dS_dS, dS_dg, dS_dE, dS_dv],
                [dg_dS, dg_dg, dg_dE, dg_dv],
                [dE_dS, dE_dg, dE_dE, dE_dv],
                [dv_dS, dv_dg, dv_dE, dv_dv],
            ],
            dtype=np.float64,
        )

    def stability(self, fixed_point: CoherenceState) -> StabilityReport:
        """Linear-stability analysis around ``fixed_point``.

        Returns eigenvalues of the Jacobian, spectral radius, a boolean
        ``is_stable`` (spectral radius < 1), an e-folding convergence time,
        and the entropy slope ``dS/dt`` evaluated at the fixed point (which
        is zero at a true FP — useful only as a sign diagnostic for
        non-fixed-points passed in).
        """
        J = self.linearized_jacobian(fixed_point)
        eigs = np.linalg.eigvals(J)
        rho = float(np.max(np.abs(eigs)))
        stable = bool(rho < 1.0 - 1e-12)
        if stable and rho > 0.0:
            tau = float(-1.0 / np.log(rho)) if rho < 1.0 else float("inf")
        else:
            tau = float("inf")

        # Entropy-slope sign convention: dS/dt > 0 means coherence rising.
        p = self.params
        dS = (
            p.alpha * (fixed_point.gamma - 1.0) * fixed_point.S
            - p.beta * fixed_point.E_obj * fixed_point.S
            - p.kappa * (fixed_point.S - 0.5)
        )
        return StabilityReport(
            eigenvalues=np.asarray(eigs, dtype=np.complex128).real.astype(np.float64),
            spectral_radius=rho,
            is_stable=stable,
            convergence_time=tau,
            entropy_slope=float(dS),
        )

    # -- INV-YV1 gradient ontology check ----------------------------

    def check_gradient_ontology(
        self,
        trajectory: FloatArray,
    ) -> dict[str, object]:
        """Verify INV-YV1 (ΔV > 0 ∧ dΔV/dt ≠ 0) on a state trajectory.

        Delegates to ``core.axioms.check_inv_yv1``. Returns diagnosis:
        "living_gradient", "static_capacitor", "dead_equilibrium",
        or "transient".
        """
        from core.axioms import check_inv_yv1

        return check_inv_yv1(trajectory, dt=self.params.dt)

    # -- Convenience -----------------------------------------------

    def with_params(self, **overrides: float) -> CoherenceStateSpace:
        """Return a new model with updated parameter overrides."""
        new_params = replace(self.params, **overrides)
        return CoherenceStateSpace(new_params)
