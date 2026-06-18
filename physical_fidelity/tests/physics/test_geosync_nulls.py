"""GeoSync null models (NFI-PROMPT-002 Section 4).

A positive physics demonstration is invalid unless the matched null behaves as
required. Nulls must FAIL to synchronize / show no structure.
"""

from __future__ import annotations

import numpy as np
import pytest

from physical_fidelity.pf import dynamics, hypotheses, spectral


def test_null_k0_incoherent():
    # K=0: r stays at the O(1/sqrt N) floor, no macroscopic synchronization.
    n = 256
    w = np.ones((n, n)) - np.eye(n)
    rng = np.random.default_rng(0)
    res = dynamics.integrate_kuramoto(rng.standard_normal(n), w, k=0.0, t_end=20.0, dt=0.02, seed=0)
    assert res.r_mean_tail < 3.0 * dynamics.incoherent_order_parameter_scale(n)


def test_null_random_phase_flat_spectrum():
    # Shuffled phases -> order-parameter series has no 1/f reddening (beta ~ 0).
    rng = np.random.default_rng(1)
    white = rng.standard_normal(1 << 13)
    beta = spectral.psd_slope(white).beta
    assert abs(beta) < 0.3


def test_null_erdos_renyi_shifts_kc():
    # A sparser Erdos-Renyi graph has a smaller Fiedler value -> larger sync bound.
    n = 60
    rng = np.random.default_rng(2)
    complete = np.ones((n, n)) - np.eye(n)
    er = (rng.random((n, n)) < 0.2).astype(float)
    er = np.triu(er, 1)
    er = er + er.T
    omega = rng.standard_normal(n)
    kc_complete = dynamics.dorfler_bullo_sync_bound(omega, complete)
    kc_er = dynamics.dorfler_bullo_sync_bound(omega, er)
    assert kc_er > kc_complete  # sparser graph is harder to synchronize


def test_null_constant_phase_locked():
    # Identical phases -> r == 1 exactly (degenerate locked null).
    theta = np.full(50, 0.7)
    r, _ = dynamics.order_parameter(theta)
    assert r == pytest.approx(1.0, abs=1e-12)


def test_positive_requires_rejected_incoherent_null():
    # The licensing test: synchronized regime MUST reject r ~ U(0,1).
    n = 128
    w = np.ones((n, n)) - np.eye(n)
    rs = np.array(
        [
            dynamics.integrate_kuramoto(np.zeros(n), w, 2.0, t_end=30.0, dt=0.02, seed=i).r_final
            for i in range(15)
        ]
    )
    assert hypotheses.test_synchronization(rs).reject_h0
