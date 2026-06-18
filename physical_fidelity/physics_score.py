"""NFI-PROMPT-002 Section 1 + 9: the physics scoring oracle.

Computes the 10-axis admissibility score S_total from live measurements and
artifact existence, reading weights/thresholds from ``metrics_schema.json``.

HONESTY CONTRACT (binding): every axis is measured from a real function call or a
real file check. No axis is hand-set. We do NOT tune inputs to land S in the
target band [88, 92]; the reported S is whatever the apparatus actually yields.
S is an ADMISSIBILITY score (does the protocol reproduce known physics and do its
deliverables exist + pass), never a validation of the live substrates.

Run: ``python -m physical_fidelity.physics_score``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .pf import (
    dimensional,
    dynamics,
    energy,
    hypotheses,
    interfaces,
    replication,
    spectral,
    stability,
    turing,
    uq,
)

ROOT = Path(__file__).parent
SCHEMA_PATH = ROOT / "metrics_schema.json"

# Governing equations traced to code + test (S10).
EQUATION_TRACE: list[dict[str, str]] = [
    {
        "equation": "graph Kuramoto dtheta/dt",
        "code_path": "pf/dynamics.py::kuramoto_rhs",
        "test": "tests/test_protocol.py::test_identical_frequencies_synchronize",
    },
    {
        "equation": "order parameter r=|<e^{i theta}>|",
        "code_path": "pf/dynamics.py::order_parameter",
        "test": "tests/test_protocol.py::test_order_parameter_bounded",
    },
    {
        "equation": "normalized discrete Ricci flow",
        "code_path": "pf/dynamics.py::ricci_flow",
        "test": "tests/test_protocol.py::test_ricci_flow_conserves_total_weight",
    },
    {
        "equation": "gamma_PSD = 2H + 1",
        "code_path": "pf/spectral.py::verify_gamma_2h1",
        "test": "tests/test_protocol.py::test_gamma_2h1_recovers_hurst",
    },
    {
        "equation": "AdEx (V,w) dynamics",
        "code_path": "pf/adex_q10.py::adex_rhs",
        "test": "tests/test_protocol.py::test_adex_spikes_under_strong_drive",
    },
    {
        "equation": "Q10 time-constant scaling",
        "code_path": "pf/adex_q10.py::q10_scale",
        "test": "tests/test_protocol.py::test_q10_slows_time_constant_when_cold",
    },
    {
        "equation": "open-system energy balance",
        "code_path": "pf/energy.py::check_energy_balance",
        "test": "tests/physics/test_invariants.py::test_adex_energy_balance_quiescent",
    },
    {
        "equation": "Schnakenberg Turing Jacobian",
        "code_path": "pf/turing.py::schnakenberg_jacobian",
        "test": "tests/test_protocol.py::test_schnakenberg_turing_unstable_in_known_region",
    },
    {
        "equation": "parabolic diffusion dt limit",
        "code_path": "pf/stability.py::diffusion_dt_parabolic",
        "test": "tests/test_protocol.py::test_parabolic_step_scales_as_dx_squared",
    },
    {
        "equation": "maximal Lyapunov exponent",
        "code_path": "pf/stability.py::max_lyapunov",
        "test": "tests/test_protocol.py::test_mle_sign_matches_regime",
    },
]

REQUIRED_DOCS = [
    "docs/physics/geosync_core.md",
    "docs/physics/bnsyn_core.md",
    "docs/physics/mfn_core.md",
    "docs/physics/interface_contracts.md",
]


# --------------------------------------------------------------------------- #
# Axis measurement functions (each returns a score in [0, 100])
# --------------------------------------------------------------------------- #
def score_math_object() -> float:
    checks: list[bool] = []
    # GeoSync: canonical object fixed (doc) + analytic Kc + gamma observable
    checks.append((ROOT / "docs/physics/geosync_core.md").exists())
    checks.append(np.isfinite(dynamics.mean_field_critical_coupling_lorentzian(0.5)))
    checks.append(spectral.verify_gamma_2h1(0.75, n_avg=8).passed)
    # BN-Syn: AdEx canonical + Q10 (no Boltzmann) doc
    checks.append((ROOT / "docs/physics/bnsyn_core.md").exists())
    # MFN: f,g + steady state + Jacobian
    checks.append((ROOT / "docs/physics/mfn_core.md").exists())
    checks.append(turing.analyze_schnakenberg(0.1, 0.9, 1.0, 40.0).is_turing_unstable)
    return float(100.0 * sum(bool(c) for c in checks) / len(checks))


def score_dimensional() -> float:
    reports = dimensional.all_checks()
    return float(100.0 * sum(bool(r.homogeneous) for r in reports) / len(reports))


def score_numerical_stability() -> float:
    rng = np.random.default_rng(0)
    n = 10
    om = rng.standard_normal(n)
    w = np.ones((n, n)) - np.eye(n)
    order = replication.convergence_order(om, w, 1.5, t_end=8.0).observed_order
    checks = [
        order >= 3.5,
        stability.diffusion_dt_parabolic(0.1, 0.01) / stability.diffusion_dt_parabolic(0.05, 0.01)
        > 3.9,
        stability.cfl_dt_hyperbolic(0.1, 1.0) / stability.cfl_dt_hyperbolic(0.05, 1.0) > 1.9,
    ]
    return float(100.0 * sum(bool(c) for c in checks) / len(checks))


def score_invariants() -> float:
    rng = np.random.default_rng(0)
    n = 32
    w = np.ones((n, n)) - np.eye(n)
    res = dynamics.integrate_kuramoto(rng.standard_normal(n), w, 1.0, t_end=20.0, dt=0.02)
    r_ok = bool(np.all((res.r_series >= 0) & (res.r_series <= 1 + 1e-9)))
    w0 = np.triu((rng.random((20, 20)) < 0.3).astype(float), 1)
    w0 = w0 + w0.T
    _, totals = dynamics.ricci_flow(w0, 30, 0.1)
    cons_ok = energy.graph_weight_conservation(totals).passed
    from .pf import adex_q10

    t, e, pin, pd = adex_q10.simulate_adex_energy(
        adex_q10.AdExParams(), i_ext=50.0, t_end=120.0, dt=0.005
    )
    energy_ok = energy.check_energy_balance(e, pin, pd, dt=0.005).passed
    checks = [r_ok, cons_ok, energy_ok]
    return float(100.0 * sum(bool(c) for c in checks) / len(checks))


def score_falsifiability() -> float:
    rng = np.random.default_rng(0)
    n = 128
    w = np.ones((n, n)) - np.eye(n)
    # K=0 incoherent null: KS vs U(0,1) should NOT strongly reject at single sample
    r0 = np.array(
        [
            dynamics.integrate_kuramoto(
                rng.standard_normal(n), w, 0.0, t_end=15.0, dt=0.02, seed=i
            ).r_final
            for i in range(15)
        ]
    )
    # synchronized regime: KS MUST reject incoherent null
    rs = np.array(
        [
            dynamics.integrate_kuramoto(np.zeros(n), w, 2.0, t_end=30.0, dt=0.02, seed=i).r_final
            for i in range(15)
        ]
    )
    sync_rejects = hypotheses.test_synchronization(rs).reject_h0
    # equal-diffusion MFN null: NOT Turing unstable
    null_turing = not turing.analyze_schnakenberg(0.1, 0.9, 1.0, 1.0).is_turing_unstable
    # incoherent scaling law holds
    ns = np.array([16, 32, 64, 128, 256])
    rsc = [
        dynamics.integrate_kuramoto(
            rng.standard_normal(m), np.ones((m, m)) - np.eye(m), 0.0, t_end=15.0, dt=0.02, seed=m
        ).r_mean_tail
        for m in ns
    ]
    scaling_ok = not hypotheses.test_scaling_exponent(ns, np.array(rsc)).reject_h0
    checks = [sync_rejects, null_turing, scaling_ok, bool(np.mean(r0) < 0.5)]
    return float(100.0 * sum(bool(c) for c in checks) / len(checks))


def score_baseline_models() -> float:
    checks = [
        abs(dynamics.mean_field_critical_coupling_lorentzian(0.5) - 1.0) < 1e-9,
        abs(turing.schnakenberg_steady_state(0.1, 0.9)[0] - 1.0) < 1e-9,
        spectral.verify_gamma_2h1(0.75, n_avg=8).passed,
        dynamics.fiedler_value(np.ones((6, 6)) - np.eye(6)) > 0,
    ]
    return float(100.0 * sum(bool(c) for c in checks) / len(checks))


def score_uq() -> float:
    # non-degenerate CI from a defined prior
    ci = uq.parametric_uq(lambda p: p["x"] ** 2, {"x": 2.0}, sigma=0.1, n=1000).ci95
    nondegenerate = ci[1] - ci[0] > 1e-6
    # Sobol validated on Ishigami (x1~0.314, x2~0.442, x3~0)
    a, b = 7.0, 0.1

    def ishi(p: Any) -> float:
        return float(
            np.sin(p["x1"]) + a * np.sin(p["x2"]) ** 2 + b * p["x3"] ** 4 * np.sin(p["x1"])
        )

    bnd = {k: (-np.pi, np.pi) for k in ("x1", "x2", "x3")}
    s = uq.sobol_from_matrices(
        ishi, uq.uniform_sample(bnd, 4000, seed=1), uq.uniform_sample(bnd, 4000, seed=2)
    )
    sobol_ok = abs(s.first_order["x1"] - 0.314) < 0.1 and abs(s.first_order["x2"] - 0.442) < 0.1
    return float(100.0 * sum([bool(nondegenerate), bool(sobol_ok)]) / 2)


def score_reproducibility() -> float:
    rep = replication.independent_replication()
    return 100.0 if rep.passed else max(0.0, 100.0 * (1e-4 / max(rep.rel_linf, 1e-12)))


def score_interfaces() -> float:
    v = interfaces.validate_geosync_output()
    doc = (ROOT / "docs/physics/interface_contracts.md").exists()
    checks = [v.r_in_range, v.theta_finite, v.gamma_finite, doc]
    return float(100.0 * sum(bool(c) for c in checks) / len(checks))


def score_traceability() -> float:
    present = 0
    for entry in EQUATION_TRACE:
        code_file = ROOT / entry["code_path"].split("::")[0]
        test_file = ROOT / entry["test"].split("::")[0]
        if code_file.exists() and test_file.exists():
            present += 1
    return 100.0 * present / len(EQUATION_TRACE)


SCORERS = {
    "S1_math_object": score_math_object,
    "S2_dimensional": score_dimensional,
    "S3_numerical_stability": score_numerical_stability,
    "S4_invariants": score_invariants,
    "S5_falsifiability": score_falsifiability,
    "S6_baseline_models": score_baseline_models,
    "S7_UQ": score_uq,
    "S8_reproducibility": score_reproducibility,
    "S9_interfaces": score_interfaces,
    "S10_traceability": score_traceability,
}


@dataclass
class AxisScore:
    """One scored axis."""

    axis_id: str
    value: float
    weight: float
    threshold: float
    target: float

    @property
    def passed(self) -> bool:
        return self.value >= self.threshold


def compute_score() -> dict[str, Any]:
    """Run all 10 axes and return the full scorecard dict."""
    schema = json.loads(SCHEMA_PATH.read_text())
    axes: list[AxisScore] = []
    for spec in schema["axes"]:
        aid = spec["id"]
        value = float(SCORERS[aid]())
        axes.append(AxisScore(aid, value, spec["weight"], spec["pass_threshold"], spec["target"]))
    wsum = sum(a.weight for a in axes)
    s_total = sum(a.value * a.weight for a in axes) / wsum
    return {
        "classification": schema["classification"],
        "target_band": schema["target_band"],
        "S_total": round(s_total, 2),
        "in_target_band": schema["target_band"][0] <= s_total <= schema["target_band"][1],
        "axes": [
            {
                "id": a.axis_id,
                "value": round(a.value, 2),
                "weight": a.weight,
                "threshold": a.threshold,
                "passed": a.passed,
            }
            for a in axes
        ],
    }


def main() -> None:
    result = compute_score()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
