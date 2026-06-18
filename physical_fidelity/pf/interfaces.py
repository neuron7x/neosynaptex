"""Inter-layer interface contracts (GAP-O-03 / NFI-PROMPT-002 Section 3).

Vertical hierarchy: Layer0 -> GeoSync -> BN-Syn -> MFN+ -> conclusion. Each
boundary carries a typed contract; no subsystem may consume another's output
without the boundary passing its contract test.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .dynamics import integrate_kuramoto, order_parameter
from .spectral import psd_slope

Array = NDArray[np.float64]


@dataclass(frozen=True)
class InterfaceContract:
    """A formal boundary contract between two NFI layers."""

    name: str
    output_type: str
    units: str
    valid_range: tuple[float, float]
    sampling_dt: float
    failure_mode: str
    test_ref: str


# Canonical contracts (single source of truth for the boundaries we verify).
GEOSYNC_OUTPUT = InterfaceContract(
    name="geosync->bnsyn",
    output_type="dict(theta:(N,T) rad, R:scalar_per_t in[0,1], gamma_PSD:float)",
    units="theta=radians, R=dimensionless, gamma=dimensionless",
    valid_range=(0.0, 1.0),  # on R
    sampling_dt=0.02,
    failure_mode="R outside [0,1] or non-finite theta -> halt, do not propagate",
    test_ref="tests/physics/test_interface_contracts.py::test_geosync_output_contract",
)


@dataclass(frozen=True)
class ContractVerdict:
    """Result of validating an actual signal against a contract."""

    contract: str
    r_in_range: bool
    theta_finite: bool
    gamma_finite: bool
    passed: bool


def validate_geosync_output(*, n: int = 16, seed: int = 0) -> ContractVerdict:
    """Run GeoSync and verify its emitted signal honours GEOSYNC_OUTPUT."""
    rng = np.random.default_rng(seed)
    omega = rng.standard_normal(n)
    w = np.ones((n, n)) - np.eye(n)
    res = integrate_kuramoto(omega, w, k=1.5, t_end=40.0, dt=GEOSYNC_OUTPUT.sampling_dt, seed=seed)
    lo, hi = GEOSYNC_OUTPUT.valid_range
    r_ok = bool(np.all((res.r_series >= lo - 1e-9) & (res.r_series <= hi + 1e-9)))
    theta_ok = bool(np.all(np.isfinite(res.theta_final)))
    gamma = psd_slope(res.r_series).beta
    gamma_ok = bool(np.isfinite(gamma))
    # exercise the order_parameter contract producer too
    _ = order_parameter(res.theta_final)
    return ContractVerdict(
        contract=GEOSYNC_OUTPUT.name,
        r_in_range=r_ok,
        theta_finite=theta_ok,
        gamma_finite=gamma_ok,
        passed=bool(r_ok and theta_ok and gamma_ok),
    )
