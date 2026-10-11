"""γ specificity probe: committed evidence is reproducible and says what it says."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN_PATH = REPO_ROOT / "experiments" / "gamma_specificity" / "run.py"
EVIDENCE_PATH = REPO_ROOT / "results" / "gamma_specificity" / "run_v1.json"


def _committed() -> dict:
    return json.loads(EVIDENCE_PATH.read_text())


def test_evidence_is_bound_to_the_harness_source() -> None:
    assert _committed()["source_sha256"] == hashlib.sha256(RUN_PATH.read_bytes()).hexdigest()


def test_fresh_run_reproduces_committed_evidence(tmp_path: pathlib.Path) -> None:
    before = EVIDENCE_PATH.read_bytes()
    out = tmp_path / "run.json"
    proc = subprocess.run(
        [sys.executable, str(RUN_PATH), "--out", str(out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert EVIDENCE_PATH.read_bytes() == before, "run must not rewrite committed evidence"
    assert json.loads(out.read_text()) == _committed()


def test_every_case_is_declared_non_critical() -> None:
    ev = _committed()
    cases = ev["spectral_cases"] + ev["pair_cases"]
    assert cases, "an empty case list would make the verdict vacuous"
    assert all(c["critical_by_construction"] is False for c in cases)


def test_verdict_follows_from_the_cases() -> None:
    ev = _committed()
    hits = [
        c["name"]
        for c in ev["spectral_cases"] + ev["pair_cases"]
        if c["mean_in_metastable_band"]
    ]
    assert (ev["specificity_verdict"] == "NOT_SPECIFIC") == bool(hits)
    for name in hits:
        assert name in ev["specificity_reason"]


def test_band_membership_is_recomputed_not_trusted() -> None:
    ev = _committed()
    half = ev["config"]["BAND_HALF_WIDTH"]
    for c in ev["spectral_cases"]:
        assert c["mean_in_metastable_band"] == (abs(c["gamma_mean"] - 1.0) < half)
        assert c["n_seeds_in_band"] == sum(abs(g - 1.0) < half for g in c["gammas"])


def test_controls_behave_as_controls() -> None:
    """The probe must be able to say 'not in band': white-like inputs stay out."""
    by_name = {c["name"]: c for c in _committed()["spectral_cases"]}
    assert not by_name["powerlaw_beta_0.0"]["mean_in_metastable_band"]
    assert not by_name["ar1_phi_0.5"]["mean_in_metastable_band"]
    pairs = {c["name"]: c for c in _committed()["pair_cases"]}
    assert pairs["independent_lognormal"]["verdict"] != "METASTABLE"
