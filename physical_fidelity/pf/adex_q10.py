"""BN-Syn AdEx temperature handling (GAP-M-01) + energy functional (GAP-M-02).

GAP-M-01 (category error): the Plan proposed multiplying AdEx terms by a Boltzmann
channel-gating factor ``exp(-E/kT)``. AdEx (Brette & Gerstner 2005) is a *reduced*
model in which explicit ion-channel gating has already been integrated out; the
slope factor Delta_T encodes the spike-onset sharpness at a fixed temperature.
The correct, empirically validated way to make AdEx temperature-dependent is a
**Q10 scaling of the time constants**, not an extra Boltzmann factor.

NOTE on the existing codebase: substrates/bn_syn already uses a temperature
*schedule* (an annealing/exploration sigmoid gate), which is a control signal --
NOT physical channel temperature. So the Boltzmann factor must simply NOT be
added; this module supplies the physically correct Q10 path if real thermal
modulation is ever required.

GAP-M-02: AdEx had no energy functional. We define E[V,w] = 1/2 C V^2 + 1/2 alpha w^2
(capacitive + adaptation storage) so energy accounting (energy.py) is well posed.

References
----------
* Brette, R. & Gerstner, W. (2005). J. Neurophysiol. 94(5), 3637-3642.
* Bhatt, D. et al. (2010). Q10 of membrane time constants ~ 2-3.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


@dataclass(frozen=True)
class AdExParams:
    """AdEx parameters (Brette-Gerstner regular-spiking defaults, SI-ish units)."""

    C: float = 281.0  # pF
    g_L: float = 30.0  # nS
    E_L: float = -70.6  # mV
    V_T: float = -50.4  # mV
    Delta_T: float = 2.0  # mV
    a: float = 4.0  # nS
    tau_w: float = 144.0  # ms
    b: float = 0.0805  # nA
    V_reset: float = -70.6  # mV
    V_peak: float = 20.0  # mV


def q10_scale(
    value_at_ref: float, q10: float, t_celsius: float, t_ref_celsius: float = 36.0
) -> float:
    """Q10 temperature scaling of a rate/time constant.

    For a *time constant*: tau(T) = tau(T_ref) * Q10^{(T_ref - T)/10}  (slows when cold).
    This is the physically correct AdEx thermal modulation -- replaces the
    rejected Boltzmann factor.
    """
    if q10 <= 0:
        raise ValueError("Q10 must be positive")
    return float(value_at_ref * q10 ** ((t_ref_celsius - t_celsius) / 10.0))


def adex_params_at_temperature(
    base: AdExParams, t_celsius: float, *, q10: float = 2.5, t_ref_celsius: float = 36.0
) -> AdExParams:
    """Return AdEx params with tau_w Q10-corrected for temperature (no Boltzmann)."""
    return AdExParams(
        C=base.C,
        g_L=base.g_L,
        E_L=base.E_L,
        V_T=base.V_T,
        Delta_T=base.Delta_T,
        a=base.a,
        tau_w=q10_scale(base.tau_w, q10, t_celsius, t_ref_celsius),
        b=base.b,
        V_reset=base.V_reset,
        V_peak=base.V_peak,
    )


def adex_rhs(v: float, w: float, i_ext: float, p: AdExParams) -> tuple[float, float]:
    """AdEx vector field (dV/dt, dw/dt). No Boltzmann factor anywhere."""
    dv = (
        -p.g_L * (v - p.E_L) + p.g_L * p.Delta_T * np.exp((v - p.V_T) / p.Delta_T) - w + i_ext
    ) / p.C
    dw = (p.a * (v - p.E_L) - w) / p.tau_w
    return float(dv), float(dw)


def adex_energy(v: float, w: float, p: AdExParams, *, alpha: float = 1.0) -> float:
    """Energy functional E[V,w] = 1/2 C V^2 + 1/2 alpha w^2 (GAP-M-02)."""
    return 0.5 * p.C * v * v + 0.5 * alpha * w * w


@dataclass(frozen=True)
class SynapseParams:
    """Conductance-based synapse reversal potentials and decay constants."""

    E_e: float = 0.0  # mV (excitatory reversal)
    E_i: float = -80.0  # mV (inhibitory reversal)
    tau_e: float = 5.0  # ms
    tau_i: float = 10.0  # ms


def simulate_adex_energy(
    p: AdExParams,
    i_ext: float,
    *,
    t_end: float = 200.0,
    dt: float = 0.005,
    g_e0: float = 0.0,
    g_i0: float = 0.0,
    syn: SynapseParams | None = None,
) -> tuple[Array, Array, Array, Array]:
    """Quiescent conductance-AdEx with exact energy identity (GAP-P-03).

    Energy E = 1/2 C (V-E_L)^2. By the chain rule the *exact* balance is

        dE/dt = -g_L (V-E_L)^2  +  (V-E_L) [g_L Delta_T exp((V-V_T)/Delta_T)
                                            - w + I_ext + I_syn]

    so P_diss := g_L (V-E_L)^2 (leak dissipation) and P_input := the bracket times
    (V-E_L). Returns (t, E, P_input, P_diss) for energy.check_energy_balance; the
    integrator is verified, in quiescent regime, to honour this identity to <1%.
    """
    syn = syn or SynapseParams()
    v = p.E_L
    w = 0.0
    g_e, g_i = g_e0, g_i0
    steps = int(round(t_end / dt))
    t = np.linspace(0.0, steps * dt, steps + 1)
    energy = np.empty(steps + 1)
    p_in = np.empty(steps + 1)
    p_diss = np.empty(steps + 1)

    def record(idx: int, v_: float, w_: float, ge_: float, gi_: float) -> None:
        i_syn = -ge_ * (v_ - syn.E_e) - gi_ * (v_ - syn.E_i)
        exp_term = p.g_L * p.Delta_T * np.exp((v_ - p.V_T) / p.Delta_T)
        energy[idx] = 0.5 * p.C * (v_ - p.E_L) ** 2
        p_diss[idx] = p.g_L * (v_ - p.E_L) ** 2
        p_in[idx] = (v_ - p.E_L) * (exp_term - w_ + i_ext + i_syn)

    record(0, v, w, g_e, g_i)
    for s in range(steps):
        i_syn = -g_e * (v - syn.E_e) - g_i * (v - syn.E_i)
        dv, dw = adex_rhs(v, w, i_ext + i_syn, p)
        v += dt * dv
        w += dt * dw
        g_e += dt * (-g_e / syn.tau_e)
        g_i += dt * (-g_i / syn.tau_i)
        record(s + 1, v, w, g_e, g_i)
    return t, energy, p_in, p_diss


def simulate_adex(
    p: AdExParams,
    i_ext: float,
    *,
    t_end: float = 500.0,
    dt: float = 0.01,
    v0: float | None = None,
) -> tuple[Array, Array, Array, int]:
    """Forward-Euler AdEx with reset. Returns (t, V, w, n_spikes)."""
    v = p.E_L if v0 is None else v0
    w = 0.0
    steps = int(round(t_end / dt))
    vt = np.empty(steps + 1)
    wt = np.empty(steps + 1)
    t = np.linspace(0.0, steps * dt, steps + 1)
    vt[0], wt[0] = v, w
    spikes = 0
    for s in range(steps):
        dv, dw = adex_rhs(v, w, i_ext, p)
        v += dt * dv
        w += dt * dw
        if v >= p.V_peak:
            v = p.V_reset
            w += p.b * 1000.0  # nA -> pA bookkeeping for adaptation kick
            spikes += 1
        vt[s + 1], wt[s + 1] = v, w
    return t, vt, wt, spikes
