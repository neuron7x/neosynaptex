"""Tests for the publication-grade run report (Task 10)."""

from __future__ import annotations

import json
from pathlib import Path

from tools.hrv.full_report import build_full_report

_REPO = Path(__file__).parent.parent


def test_report_has_all_required_sections() -> None:
    r = build_full_report()
    for key in (
        "schema_version",
        "run_utc",
        "git_sha",
        "software",
        "canonical_stack_version",
        "cohort_manifests",
        "analysis_split",
        "thresholds_frozen",
        "branch_registry",
        "baseline_panel_summary",
        "null_suite_summary",
        "outlier_protocol_summary",
        "blind_validation_report",
        "evidence_branches_roll_up",
        "state_contrast_summary",
    ):
        assert key in r, f"missing section: {key}"


def test_four_cohorts_in_manifests() -> None:
    r = build_full_report()
    assert set(r["cohort_manifests"]) == {"nsr2db", "chfdb", "chf2db", "nsrdb"}
    for block in r["cohort_manifests"].values():
        assert block["sha256"]
        assert block["data"]["expected_n_subjects"] == block["data"]["actual_n_subjects"]


def test_committed_run_report_exists_under_reports_runs() -> None:
    runs_dir = _REPO / "reports" / "runs"
    assert runs_dir.exists()
    runs = sorted(runs_dir.iterdir())
    assert runs, "at least one committed run report expected"
    latest = runs[-1]
    report_path = latest / "full_report.json"
    assert report_path.exists()
    r = json.loads(report_path.read_text("utf-8"))
    assert set(r["cohort_manifests"]) == {"nsr2db", "chfdb", "chf2db", "nsrdb"}


def test_git_sha_is_40char_hex_or_unknown() -> None:
    r = build_full_report()
    sha = r["git_sha"]
    assert sha == "unknown" or (len(sha) == 40 and all(c in "0123456789abcdef" for c in sha))


def test_software_versions_has_python() -> None:
    r = build_full_report()
    assert "python" in r["software"]
