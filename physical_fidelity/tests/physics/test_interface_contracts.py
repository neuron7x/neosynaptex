"""Interface contract tests (NFI-PROMPT-002 Section 3, GAP-O-03)."""

from __future__ import annotations

from physical_fidelity.pf import interfaces


def test_geosync_output_contract():
    v = interfaces.validate_geosync_output(n=16, seed=0)
    assert v.r_in_range
    assert v.theta_finite
    assert v.gamma_finite
    assert v.passed


def test_contract_metadata_present():
    c = interfaces.GEOSYNC_OUTPUT
    assert c.valid_range == (0.0, 1.0)
    assert "radians" in c.units
    assert c.test_ref.endswith("test_geosync_output_contract")
