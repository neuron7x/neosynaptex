"""Falsification engine (NFI v3.0 tool 6)."""

from __future__ import annotations

import numpy as np

from physical_fidelity.pf import dynamics


def test_below_kc_no_synchronization():
    # H0: K<K_c behaves incoherent. Strong sync below K_c would be an artifact.
    n = 200
    w = np.ones((n, n)) - np.eye(n)
    rng = np.random.default_rng(0)
    res = dynamics.integrate_kuramoto(
        rng.standard_normal(n), w, k=0.05, t_end=40.0, dt=0.02, seed=0
    )
    assert res.r_mean_tail < 0.4


def test_above_kc_synchronizes():
    n = 200
    w = np.ones((n, n)) - np.eye(n)
    rng = np.random.default_rng(1)
    res = dynamics.integrate_kuramoto(
        0.2 * rng.standard_normal(n), w, k=5.0, t_end=40.0, dt=0.02, seed=1
    )
    assert res.r_mean_tail > 0.8
