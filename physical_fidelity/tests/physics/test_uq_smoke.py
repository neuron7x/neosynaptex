"""UQ smoke (NFI v3.0 tool 10): no MC without a stochastic source; Sobol valid."""

from __future__ import annotations

import numpy as np

from physical_fidelity.pf import uq


def test_uq_requires_stochastic_source():
    # sigma=0 -> degenerate CI (the forbidden 'MC on deterministic model').
    assert (
        uq.parametric_uq(lambda p: p["x"] ** 2, {"x": 2.0}, sigma=0.0, n=200).ci95[1]
        - uq.parametric_uq(lambda p: p["x"] ** 2, {"x": 2.0}, sigma=0.0, n=200).ci95[0]
        < 1e-9
    )
    nd = uq.parametric_uq(lambda p: p["x"] ** 2, {"x": 2.0}, sigma=0.1, n=500)
    assert nd.ci95[1] - nd.ci95[0] > 1e-6


def test_sobol_matches_ishigami():
    a, b = 7.0, 0.1

    def ishi(p):
        return float(
            np.sin(p["x1"]) + a * np.sin(p["x2"]) ** 2 + b * p["x3"] ** 4 * np.sin(p["x1"])
        )

    bnd = {k: (-np.pi, np.pi) for k in ("x1", "x2", "x3")}
    s = uq.sobol_from_matrices(
        ishi, uq.uniform_sample(bnd, 6000, seed=1), uq.uniform_sample(bnd, 6000, seed=2)
    )
    assert abs(s.first_order["x1"] - 0.314) < 0.08
    assert abs(s.first_order["x2"] - 0.442) < 0.08
