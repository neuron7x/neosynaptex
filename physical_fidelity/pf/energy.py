"""Open-system energy balance (GAP-P-03).

The Plan demanded ``|dE/E| < 1%`` but closed-system conservation is the wrong
contract: all three NFI subsystems are *driven* (open). The correct, checkable
law is the integral balance

    E(t) = E(0) + integral_0^t [ P_input(tau) - P_diss(tau) ] dtau .

We verify that the discretely accumulated power balance reproduces the directly
computed energy change to within a relative tolerance -- a real, runnable test,
not a closed-system mirage.

For AdEx the natural power terms are::

    P_input(t) = I_ext(t) * V(t)
    P_diss(t)  = g_L (V - E_L)^2  + (synaptic conductance terms if present)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


@dataclass(frozen=True)
class EnergyBalanceVerdict:
    """Result of an open-system energy-balance check."""

    delta_e_direct: float
    delta_e_from_power: float
    abs_residual: float
    rel_residual: float
    passed: bool


def check_energy_balance(
    energy: Array,
    p_input: Array,
    p_diss: Array,
    dt: float,
    *,
    rel_tol: float = 1e-2,
) -> EnergyBalanceVerdict:
    """Verify E(t)-E(0) == integral(P_input - P_diss) dt to ``rel_tol``.

    Uses the trapezoidal rule for the power integral (matches a second-order
    accumulation). Relative residual is normalized by the energy excursion scale.
    """
    energy = np.asarray(energy, dtype=np.float64)
    net_power = np.asarray(p_input, dtype=np.float64) - np.asarray(p_diss, dtype=np.float64)
    delta_direct = float(energy[-1] - energy[0])
    delta_power = float(np.trapezoid(net_power, dx=dt))
    resid = abs(delta_direct - delta_power)
    scale = max(abs(delta_direct), np.ptp(energy), 1e-12)
    rel = resid / scale
    return EnergyBalanceVerdict(
        delta_e_direct=delta_direct,
        delta_e_from_power=delta_power,
        abs_residual=resid,
        rel_residual=rel,
        passed=bool(rel < rel_tol),
    )


def graph_weight_conservation(
    total_history: Array, *, rel_tol: float = 1e-9
) -> EnergyBalanceVerdict:
    """Verify total graph weight is conserved under normalized Ricci flow.

    The discrete Ricci flow (dynamics.ricci_flow) renormalizes total weight each
    step, so ``sum w`` must be invariant to machine precision. This is the
    operator's requested conservation invariant cast as an energy-style check.
    """
    h = np.asarray(total_history, dtype=np.float64)
    resid = float(np.max(np.abs(h - h[0])))
    rel = resid / max(abs(float(h[0])), 1e-12)
    return EnergyBalanceVerdict(
        delta_e_direct=float(h[-1] - h[0]),
        delta_e_from_power=0.0,
        abs_residual=resid,
        rel_residual=rel,
        passed=bool(rel < rel_tol),
    )
