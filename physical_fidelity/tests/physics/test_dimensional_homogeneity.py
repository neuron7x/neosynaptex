"""Dimensional homogeneity (NFI v3.0 tool 3, GAP-P-01)."""

from __future__ import annotations

from physical_fidelity.pf import dimensional


def test_all_governing_equations_homogeneous():
    for report in dimensional.all_checks():
        assert report.homogeneous, f"{report.equation}: {report.term_dims}"


def test_kuramoto_terms_are_rates():
    r = dimensional.check_kuramoto()
    assert r.homogeneous and r.target == dimensional.DIMENSIONLESS / dimensional.S
