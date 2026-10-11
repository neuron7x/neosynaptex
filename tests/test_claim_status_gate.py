"""Tests for the Task 12 claim-status gate."""

from __future__ import annotations

from tools.audit.claim_status_gate import scoreboard


def test_scoreboard_returns_11_flags() -> None:
    s = scoreboard()
    assert set(s) == {
        "full_cohort_complete",
        "split_frozen",
        "baseline_panel_complete",
        "five_null_suite_complete",
        "blind_external_validation",
        "canonical_stack_frozen",
        "evidence_branches_split",
        "outlier_protocol_complete",
        "state_contrast_done",
        "stack_frozen",
        "full_report_present",
    }


def test_every_flag_has_bool_and_reason() -> None:
    for name, (ok, why) in scoreboard().items():
        assert isinstance(ok, bool), name
        assert isinstance(why, str) and why, name


def test_gate_passes_on_current_repo() -> None:
    s = scoreboard()
    failed = [k for k, (ok, _) in s.items() if not ok]
    assert not failed, f"failing flags on current repo: {failed}"
