"""Falsifiable + adversarial tests for the physical-fidelity protocol.

Each test asserts a known physical fact. Adversarial tests feed inputs that MUST
fail the verifier (white noise is not fBm; equal diffusion is not Turing; below
K_c there is no synchronization) -- a verifier that "passes" them is broken.
"""

from __future__ import annotations

import numpy as np
import pytest

from physical_fidelity.pf import (
    adex_q10,
    dynamics,
    energy,
    hypotheses,
    spectral,
    stability,
    turing,
    uq,
)


# --------------------------------------------------------------------------- #
# GeoSync / Kuramoto
# --------------------------------------------------------------------------- #
def test_order_parameter_bounded():
    rng = np.random.default_rng(0)
    for _ in range(50):
        theta = rng.uniform(-10, 10, size=rng.integers(2, 200))
        r, _ = dynamics.order_parameter(theta)
        assert 0.0 <= r <= 1.0 + 1e-12


def test_identical_frequencies_synchronize():
    n = 50
    w = np.ones((n, n)) - np.eye(n)
    res = dynamics.integrate_kuramoto(np.zeros(n), w, k=3.0, t_end=40.0, dt=0.02, seed=1)
    assert res.r_mean_tail > 0.99


def test_below_critical_no_sync_adversarial():
    # K well below mean-field K_c for spread frequencies -> r must stay low.
    n = 200
    w = np.ones((n, n)) - np.eye(n)
    rng = np.random.default_rng(2)
    omega = rng.standard_normal(n)  # ~ Gaussian spread, K_c ~ O(1)
    res = dynamics.integrate_kuramoto(omega, w, k=0.05, t_end=40.0, dt=0.02, seed=2)
    assert res.r_mean_tail < 0.4  # no macroscopic synchronization


def test_incoherent_scaling_is_half_power():
    ns = np.array([16, 32, 64, 128, 256, 512])
    rs = []
    for nn in ns:
        w = np.ones((nn, nn)) - np.eye(nn)
        rng = np.random.default_rng(100 + nn)
        r = dynamics.integrate_kuramoto(
            rng.standard_normal(nn), w, k=0.0, t_end=20.0, dt=0.02, seed=nn
        )
        rs.append(r.r_mean_tail)
    res = hypotheses.test_scaling_exponent(ns, np.array(rs))
    assert not res.reject_h0  # slope ~ -0.5 within tolerance


def test_mean_field_kc_lorentzian():
    assert dynamics.mean_field_critical_coupling_lorentzian(0.5) == pytest.approx(1.0)


def test_fiedler_value_positive_on_connected_graph():
    n = 10
    w = np.ones((n, n)) - np.eye(n)
    assert dynamics.fiedler_value(w) > 0


# --------------------------------------------------------------------------- #
# Discrete Ricci flow conservation
# --------------------------------------------------------------------------- #
def test_ricci_flow_conserves_total_weight():
    rng = np.random.default_rng(3)
    w = (rng.random((30, 30)) < 0.3).astype(float)
    w = np.triu(w, 1)
    w = w + w.T
    _, totals = dynamics.ricci_flow(w, steps=60, eps=0.15)
    assert energy.graph_weight_conservation(totals).passed
    assert np.max(np.abs(totals - totals[0])) < 1e-8


# --------------------------------------------------------------------------- #
# NFI canonical contract gamma = 2H + 1
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("h", [0.5, 0.65, 0.75, 0.85])
def test_gamma_2h1_recovers_hurst(h):
    v = spectral.verify_gamma_2h1(h, seed=7)
    assert v.passed, f"H={h}: recovered {v.h_recovered:.3f}"


def test_white_noise_is_not_fbm_adversarial():
    # White noise has flat PSD (beta ~ 0 => H ~ -0.5), NOT the 1/f^2.5 of H=0.75.
    rng = np.random.default_rng(11)
    white = rng.standard_normal(1 << 14)
    beta = spectral.psd_slope(white).beta
    assert abs(beta) < 0.3  # essentially flat
    h_rec = spectral.hurst_from_gamma(beta)
    assert h_rec < 0.0  # would be flagged as out-of-range, not H=0.75


# --------------------------------------------------------------------------- #
# MFN / Turing
# --------------------------------------------------------------------------- #
def test_schnakenberg_turing_unstable_in_known_region():
    v = turing.analyze_schnakenberg(a=0.1, b=0.9, d_u=1.0, d_v=40.0)
    assert v.is_turing_unstable
    assert v.cond_t1_trace_neg and v.cond_t2_det_pos
    assert v.max_growth_rate > 0


def test_equal_diffusion_no_turing_adversarial():
    # Turing instability is impossible when D_u == D_v -> verifier must say False.
    v = turing.analyze_schnakenberg(a=0.1, b=0.9, d_u=1.0, d_v=1.0)
    assert not v.is_turing_unstable
    assert v.max_growth_rate <= 1e-9


def test_critical_diffusion_ratio_above_one():
    jac = turing.schnakenberg_jacobian(0.1, 0.9)
    dc = turing.critical_diffusion_ratio(jac)
    assert dc > 1.0  # activator must diffuse slower than inhibitor


# --------------------------------------------------------------------------- #
# Stability (GAP-M-04 / M-05)
# --------------------------------------------------------------------------- #
def test_parabolic_step_scales_as_dx_squared():
    dt1 = stability.diffusion_dt_parabolic(0.1, 0.01)
    dt2 = stability.diffusion_dt_parabolic(0.05, 0.01)
    assert dt1 / dt2 == pytest.approx(4.0, rel=1e-9)  # (0.1/0.05)^2


def test_hyperbolic_step_scales_linearly():
    dt1 = stability.cfl_dt_hyperbolic(0.1, 1.0)
    dt2 = stability.cfl_dt_hyperbolic(0.05, 1.0)
    assert dt1 / dt2 == pytest.approx(2.0, rel=1e-9)


def test_mle_sign_matches_regime():
    n = 12
    w = np.ones((n, n)) - np.eye(n)
    rng = np.random.default_rng(5)

    def rhs_lock(theta):
        return dynamics.kuramoto_rhs(theta, np.zeros(n), 5.0, w, 0.0)

    mle = stability.max_lyapunov(
        rhs_lock, rng.uniform(-np.pi, np.pi, n), n_steps=4000, n_transient=1000
    )
    assert mle < 0.05  # locked state is non-expanding


# --------------------------------------------------------------------------- #
# AdEx Q10 (GAP-M-01) -- NO Boltzmann factor
# --------------------------------------------------------------------------- #
def test_q10_slows_time_constant_when_cold():
    base = adex_q10.AdExParams()
    cold = adex_q10.adex_params_at_temperature(base, 26.0, q10=2.5)
    assert cold.tau_w > base.tau_w  # colder -> slower


def test_adex_spikes_under_strong_drive():
    p = adex_q10.AdExParams()
    _, _, _, spikes = adex_q10.simulate_adex(p, i_ext=800.0, t_end=300.0, dt=0.01)
    assert spikes > 0


def test_adex_quiescent_no_spikes():
    p = adex_q10.AdExParams()
    _, _, _, spikes = adex_q10.simulate_adex(p, i_ext=0.0, t_end=300.0, dt=0.01)
    assert spikes == 0


# --------------------------------------------------------------------------- #
# UQ (GAP-E-01)
# --------------------------------------------------------------------------- #
def test_parametric_uq_has_nonzero_width():
    # Deterministic map + parameter prior MUST yield a non-degenerate CI.
    res = uq.parametric_uq(lambda p: p["x"] ** 2, {"x": 2.0}, sigma=0.1, n=2000)
    lo, hi = res.ci95
    assert hi > lo
    assert lo <= 4.0 <= hi  # nominal x^2=4 inside the CI


def test_deterministic_uq_without_prior_is_degenerate_adversarial():
    # sigma=0 -> no stochasticity -> zero-width CI (the Plan's hidden error).
    res = uq.parametric_uq(lambda p: p["x"] ** 2, {"x": 2.0}, sigma=0.0, n=500)
    lo, hi = res.ci95
    assert hi - lo < 1e-9
