"""Solver integrity (NFI v3.0 tool 7C/E): finite output, no silent NaN."""

from __future__ import annotations

import numpy as np

from physical_fidelity.pf import adex_q10, dynamics


def test_kuramoto_output_finite_and_bounded():
    rng = np.random.default_rng(0)
    n = 30
    w = np.ones((n, n)) - np.eye(n)
    res = dynamics.integrate_kuramoto(rng.standard_normal(n), w, 1.5, t_end=30.0, dt=0.02)
    assert np.all(np.isfinite(res.theta_final))
    assert np.all(np.isfinite(res.r_series))
    assert np.all((res.r_series >= 0) & (res.r_series <= 1 + 1e-9))


def test_adex_output_no_nan():
    p = adex_q10.AdExParams()
    _, vt, wt, _ = adex_q10.simulate_adex(p, i_ext=500.0, t_end=200.0, dt=0.01)
    assert np.all(np.isfinite(vt)) and np.all(np.isfinite(wt))
