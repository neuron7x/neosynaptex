"""Invariant tests (NFI-PROMPT-002 Section 5 C)."""

from __future__ import annotations

import numpy as np

from physical_fidelity.pf import adex_q10, dynamics, energy


def test_order_parameter_in_unit_interval():
    rng = np.random.default_rng(0)
    n = 40
    w = np.ones((n, n)) - np.eye(n)
    res = dynamics.integrate_kuramoto(rng.standard_normal(n), w, 1.0, t_end=20.0, dt=0.02)
    assert np.all((res.r_series >= 0.0) & (res.r_series <= 1.0 + 1e-9))
    assert np.all(np.isfinite(res.theta_final))


def test_ricci_weight_conserved():
    rng = np.random.default_rng(1)
    w = np.triu((rng.random((24, 24)) < 0.3).astype(float), 1)
    w = w + w.T
    _, totals = dynamics.ricci_flow(w, 50, 0.12)
    assert energy.graph_weight_conservation(totals).passed


def test_adex_energy_balance_quiescent():
    p = adex_q10.AdExParams()
    t, e, pin, pd = adex_q10.simulate_adex_energy(p, i_ext=50.0, t_end=150.0, dt=0.005)
    verdict = energy.check_energy_balance(e, pin, pd, dt=0.005, rel_tol=1e-2)
    assert verdict.passed, f"rel_residual={verdict.rel_residual}"


def test_adex_voltage_in_physical_range():
    p = adex_q10.AdExParams()
    _, vt, _, _ = adex_q10.simulate_adex(p, i_ext=400.0, t_end=200.0, dt=0.01)
    # between reset and peak threshold (mV)
    assert np.all(vt >= p.V_reset - 1.0)
    assert np.all(vt <= p.V_peak + 1.0)
