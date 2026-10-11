"""Tests for evidence-branch split (Task 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.hrv.evidence_branches import (
    BranchRegistry,
    branch_for_metric,
    emit_branch_roll_up,
    load_branch_registry,
    roll_up_from_baseline,
    roll_up_from_blind_validation,
)

_REPO = Path(__file__).parent.parent


def test_every_baseline_metric_has_a_branch() -> None:
    metrics = [
        "sdnn_ms",
        "rmssd_ms",
        "total_power_ms2",
        "lf_power_ms2",
        "hf_power_ms2",
        "lf_hf_ratio",
        "dfa_alpha1",
        "dfa_alpha2",
        "poincare_sd1_ms",
        "poincare_sd2_ms",
        "sample_entropy",
    ]
    for m in metrics:
        b = branch_for_metric(m)
        assert b in ("branch_a_spectral", "branch_b_nonlinear")


def test_unknown_metric_raises() -> None:
    with pytest.raises(KeyError):
        branch_for_metric("fake_metric_not_registered")


def test_registry_loads_with_two_branches() -> None:
    reg = load_branch_registry()
    assert isinstance(reg, BranchRegistry)
    assert set(reg.branches) == {"branch_a_spectral", "branch_b_nonlinear"}


def test_registry_metric_assignment_matches_code_map() -> None:
    reg = load_branch_registry()
    for name, br in reg.branches.items():
        for m in br.metrics:
            assert branch_for_metric(m) == name


def test_claim_status_on_both_branches_bounded() -> None:
    reg = load_branch_registry()
    for br in reg.branches.values():
        assert br.claim_status in {"measured_but_bounded", "hypothesized", "measured"}


def test_no_metric_on_both_branches() -> None:
    reg = load_branch_registry()
    a = set(reg.branches["branch_a_spectral"].metrics)
    b = set(reg.branches["branch_b_nonlinear"].metrics)
    assert a.isdisjoint(b)


def test_roll_up_from_baseline_non_empty() -> None:
    reg = load_branch_registry()
    summary = json.loads(
        (_REPO / "results" / "hrv_baseline" / "panel_summary.json").read_text("utf-8")
    )
    out = roll_up_from_baseline(summary, reg)
    assert set(out) == {"branch_a_spectral", "branch_b_nonlinear"}
    for br in out.values():
        assert br["metrics"], "branch should carry its metric list"
        assert set(br["per_cohort"]) == {"nsr2db", "chfdb", "chf2db", "nsrdb"}


def test_roll_up_from_blind_validation_has_per_branch_aggregates() -> None:
    reg = load_branch_registry()
    rep = json.loads((_REPO / "reports" / "blind_validation" / "report.json").read_text("utf-8"))
    out = roll_up_from_blind_validation(rep, reg)
    for name, block in out.items():
        assert "median_dev_auc" in block
        assert "median_ext_auc" in block
        assert 0.5 <= block["median_dev_auc"] <= 1.0
        assert 0.5 <= block["median_ext_auc"] <= 1.0


def test_branch_roll_up_report_committed() -> None:
    p = _REPO / "reports" / "gamma_branches" / "roll_up.json"
    assert p.exists()
    rep = json.loads(p.read_text("utf-8"))
    assert "branches_from_baseline" in rep
    assert "branches_from_blind_validation" in rep
    # both branches present in both views
    for view in ("branches_from_baseline", "branches_from_blind_validation"):
        assert set(rep[view]) == {"branch_a_spectral", "branch_b_nonlinear"}


def test_emit_branch_roll_up_deterministic(tmp_path: Path) -> None:
    out = tmp_path / "roll_up.json"
    r1 = emit_branch_roll_up(
        out,
        _REPO / "results" / "hrv_baseline" / "panel_summary.json",
        _REPO / "reports" / "blind_validation" / "report.json",
    )
    r2 = emit_branch_roll_up(
        out,
        _REPO / "results" / "hrv_baseline" / "panel_summary.json",
        _REPO / "reports" / "blind_validation" / "report.json",
    )
    assert r1 == r2
