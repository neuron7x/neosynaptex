"""Tests for M2.2 HWI scale-dependence diagnostic harness."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_PATH = REPO_ROOT / "experiments" / "m_invariant_scale_diagnostics" / "run.py"
EVIDENCE_PATH = REPO_ROOT / "results" / "m_invariant_scale_diagnostics" / "run_v1.json"


def _load_run_module():
    if "m_inv_scale_diag_run" in sys.modules:
        return sys.modules["m_inv_scale_diag_run"]
    spec = importlib.util.spec_from_file_location("m_inv_scale_diag_run", RUN_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["m_inv_scale_diag_run"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_run_module_imports() -> None:
    mod = _load_run_module()
    for sym in (
        "hwi_components",
        "sweep_case",
        "decide",
        "CASES",
        "SCALES",
        "EPSILON_M_CHANGE",
    ):
        assert hasattr(mod, sym), f"run.py missing public symbol: {sym}"


def test_evaluation_grid_resolution_matches_pre_registered() -> None:
    mod = _load_run_module()
    assert mod.EVAL_POINTS == 256


def test_seed_is_pre_registered() -> None:
    mod = _load_run_module()
    assert mod.SEED == 20260501  # do not change after observing outputs


def test_full_run_produces_json_with_required_keys(tmp_path: pathlib.Path) -> None:
    rc = subprocess.run(
        [sys.executable, str(RUN_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0
    payload = json.loads(EVIDENCE_PATH.read_text())
    for key in (
        "schema",
        "source_sha256",
        "claim_status",
        "scope",
        "config",
        "cases",
        "results",
        "scale_dependence_verdict",
        "scale_dependence_reason",
        "compute_seconds",
    ):
        assert key in payload, f"evidence JSON missing key: {key}"
    assert payload["schema"] == "m_invariant_scale_diagnostics_v1"
    assert payload["claim_status"] == "derived"
    assert payload["scale_dependence_verdict"] in {
        "SCALE_DEPENDENT",
        "SCALE_STABLE",
        "INVALID_OPERATOR",
    }
    _ = tmp_path  # unused; the run writes to repo path


def test_at_least_one_case_is_scale_sensitive() -> None:
    payload = json.loads(EVIDENCE_PATH.read_text())
    sensitive = [r for r in payload["results"] if r["scale_sensitive"]]
    assert sensitive, (
        "expected at least one case to show M change > eps under coordinate "
        "rescaling; if none, PR #171's interpretation would be refuted"
    )


def test_clamp_saturation_is_detected_at_least_once() -> None:
    payload = json.loads(EVIDENCE_PATH.read_text())
    saturated = [r for r in payload["results"] if r["saturation_observed"]]
    assert saturated, (
        "expected at least one case to show clamp saturation across the scale "
        "sweep; if none, the M=1 ceiling artefact would not be reproducible"
    )


def test_gaussian_shift_violates_hwi_under_jsd_proxy() -> None:
    """Pure translation N(0,1)->N(2,1) at unit scale: KL ~2, W2 ~2,
    JSD ~0.33. Otto-Villani HWI requires H <= W2*sqrt(I) with I being
    relative Fisher information, not JSD. The MFN-style operator
    substitutes JSD as a 'bounded Fisher proxy', so W2*sqrt(JSD) ~1.15
    falls below H ~2 and HWI is violated. This is the central
    INVALID_OPERATOR finding of M2.2 and must be reproducible
    deterministically."""
    mod = _load_run_module()
    rng = np.random.default_rng(mod.SEED)
    case = next(c for c in mod.CASES if c.name == "gaussian_shift")
    p, q = mod._samples_for(case.name, rng)
    c = mod.hwi_components(p, q, case.range_unit)
    # H is order 2, W2 is order 2, JSD-based I bounds the ratio above 1.
    assert c.H > 1.0, f"expected H~2 for N(0,1)->N(2,1); got {c.H}"
    assert c.W2 > 1.0, f"expected W2~2 for N(0,1)->N(2,1); got {c.W2}"
    assert not c.hwi_holds, (
        "diagnostic finding: HWI bound is violated for smooth Gaussian shift "
        "because MFN's JSD substitution underestimates Fisher information; "
        "this is the central output of M2.2. If this assertion ever passes, "
        "the operator semantics changed and the verdict logic needs revisiting."
    )


@pytest.mark.parametrize("case_name", ["gaussian_shift", "gaussian_variance", "bimodal_shift"])
def test_unit_scale_smooth_controls_violate_hwi_under_jsd(case_name: str) -> None:
    """All three smooth analytic controls fail HWI at unit scale because
    JSD-as-I underestimates the true Fisher information bound. This is
    the structural INVALID_OPERATOR finding."""
    mod = _load_run_module()
    rng = np.random.default_rng(mod.SEED)
    case = next(c for c in mod.CASES if c.name == case_name)
    p, q = mod._samples_for(case.name, rng)
    c = mod.hwi_components(p, q, case.range_unit)
    assert not c.hwi_holds, (
        f"{case_name}: HWI must fail at unit scale under JSD proxy — "
        f"this is the operator's structural failing"
    )


def test_verdict_reflects_invalid_operator() -> None:
    """Given current pre-registered cases and seed, the verdict must be
    INVALID_OPERATOR (the structural failing of the JSD-based operator)."""
    payload = json.loads(EVIDENCE_PATH.read_text())
    assert payload["scale_dependence_verdict"] == "INVALID_OPERATOR", (
        f"expected INVALID_OPERATOR (smooth controls violate HWI at unit scale); "
        f"got {payload['scale_dependence_verdict']!r}: {payload['scale_dependence_reason']!r}"
    )


def test_evidence_json_contains_no_substrate_claim() -> None:
    payload = json.loads(EVIDENCE_PATH.read_text())
    blob = json.dumps(payload).lower()
    forbidden_substrings = (
        "bn-syn measurement",
        "mfn measurement",
        "bridge confirmed",
        "turing gap closed",
    )
    for s in forbidden_substrings:
        assert s not in blob, f"diagnostic evidence must not contain substrate claim text: {s!r}"
