"""Independent replication (NFI v3.0 tool 11): dual-solver rel Linf <= 1e-4."""

from __future__ import annotations

from physical_fidelity.pf import replication


def test_dual_solver_agreement():
    rep = replication.independent_replication(n=10, t_end=100.0, tol=1e-4)
    assert rep.passed, f"rel_linf={rep.rel_linf}"
