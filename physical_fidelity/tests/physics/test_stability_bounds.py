"""Numerical stability bounds (NFI-PROMPT-002 Section 5 B, GAP-M-04)."""

from __future__ import annotations

import pytest

from physical_fidelity.pf import stability


def test_parabolic_diffusion_bound_scales_dx2():
    assert stability.diffusion_dt_parabolic(0.1, 0.01) / stability.diffusion_dt_parabolic(
        0.05, 0.01
    ) == pytest.approx(4.0, rel=1e-9)


def test_hyperbolic_cfl_bound_scales_dx():
    assert stability.cfl_dt_hyperbolic(0.1, 1.0) / stability.cfl_dt_hyperbolic(
        0.05, 1.0
    ) == pytest.approx(2.0, rel=1e-9)


def test_parabolic_and_hyperbolic_differ_by_dx_factor():
    # Their ratio is linear in dx (the whole point of GAP-M-04).
    r1 = stability.compare_cfl_vs_diffusion(0.1, 1.0, 0.01).ratio
    r2 = stability.compare_cfl_vs_diffusion(0.05, 1.0, 0.01).ratio
    assert r1 / r2 == pytest.approx(2.0, rel=1e-9)
