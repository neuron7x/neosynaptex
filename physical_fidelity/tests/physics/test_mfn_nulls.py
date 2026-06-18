"""MFN null models (NFI-PROMPT-002 Section 4)."""

from __future__ import annotations

import numpy as np

from physical_fidelity.pf import turing


def test_null_equal_diffusion_no_turing():
    v = turing.analyze_schnakenberg(a=0.1, b=0.9, d_u=1.0, d_v=1.0)
    assert not v.is_turing_unstable
    assert v.max_growth_rate <= 1e-9


def test_null_no_reaction_decays():
    # f=g=0 -> pure diffusion -> Jacobian zero -> no instability.
    jac = np.zeros((2, 2))
    v = turing.analyze_turing(jac, d_u=1.0, d_v=40.0)
    assert not v.is_turing_unstable


def test_null_random_field_no_kc():
    # A flat (white) spatial spectrum has no dominant wavenumber.
    rng = np.random.default_rng(0)
    field = rng.standard_normal(512)
    spec = np.abs(np.fft.rfft(field)) ** 2
    # no single bin dominates: peak / median ratio stays modest for white noise
    assert spec.max() / np.median(spec) < 60.0


def test_positive_turing_in_known_region():
    v = turing.analyze_schnakenberg(a=0.1, b=0.9, d_u=1.0, d_v=40.0)
    assert v.is_turing_unstable
    assert v.k_critical_sq > 0
