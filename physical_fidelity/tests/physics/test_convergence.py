"""Convergence + independent replication (NFI-PROMPT-002 Section 5 A/D)."""

from __future__ import annotations

import numpy as np

from physical_fidelity.pf import replication


def test_rk4_convergence_order():
    rng = np.random.default_rng(0)
    n = 10
    om = rng.standard_normal(n)
    w = np.ones((n, n)) - np.eye(n)
    res = replication.convergence_order(om, w, 1.5, t_end=8.0)
    assert res.observed_order >= 3.5, f"order={res.observed_order}"


def test_independent_replication_linf():
    rep = replication.independent_replication(n=10, t_end=100.0, tol=1e-4)
    assert rep.passed, f"rel_linf={rep.rel_linf}"
