"""Deterministic tests for the PR-body claim_status validator."""

from __future__ import annotations

import pytest

from tools.audit.claim_status_applied import CANONICAL_LABELS
from tools.audit.pr_body_check import validate


@pytest.mark.parametrize("label", CANONICAL_LABELS)
def test_every_canonical_label_passes(label):
    ok, reason = validate(f"claim_status: {label}\n")
    assert ok, f"{label} failed: {reason}"
    assert label in reason


def test_case_insensitive_label_passes():
    ok, _ = validate("claim_status: MEASURED\n")
    assert ok


def test_underscore_or_space_in_key_passes():
    ok, _ = validate("claim status: derived\n")
    assert ok


def test_claim_status_with_backticks_passes():
    ok, _ = validate("claim_status: `hypothesized`\n")
    assert ok


def test_entire_claim_status_line_wrapped_in_backticks_passes():
    ok, _ = validate("`claim_status: derived`\n")
    assert ok


def test_claim_status_with_quotes_passes():
    ok, _ = validate('claim_status: "falsified"\n')
    assert ok


def test_multiword_label_unverified_analogy_passes():
    ok, _ = validate("claim_status: unverified analogy\n")
    assert ok


def test_claim_status_inside_longer_pr_body_passes():
    body = """## Summary

Does some thing.

## Test plan

Tested.

claim_status: measured

(instrumentation landed; see tests.)
"""
    ok, _ = validate(body)
    assert ok


def test_empty_body_fails_with_missing_message():
    ok, reason = validate("")
    assert not ok
    assert "missing" in reason.lower()
    assert "SYSTEM_PROTOCOL.md" in reason


def test_body_without_claim_status_line_fails():
    body = "## Summary\n\nSome change.\n\n## Test plan\n\n- [x] ran tests\n"
    ok, reason = validate(body)
    assert not ok
    assert "missing" in reason.lower()


def test_prose_mention_does_not_count():
    body = "We measured the gamma exponent across four substrates.\n"
    ok, reason = validate(body)
    assert not ok
    assert "missing" in reason.lower()


def test_label_word_alone_without_claim_status_prefix_does_not_count():
    body = "measured\nderived\nhypothesized\n"
    ok, reason = validate(body)
    assert not ok
    assert "missing" in reason.lower()


def test_unknown_label_fails_with_unknown_message():
    ok, reason = validate("claim_status: confirmed\n")
    assert not ok
    assert "outside the canonical taxonomy" in reason
    assert "'confirmed'" in reason


def test_unknown_label_keeps_pointer_to_valid_set():
    ok, reason = validate("claim_status: proven\n")
    assert not ok
    for label in CANONICAL_LABELS:
        assert label in reason, f"missing hint for {label!r}"


def test_mixed_unknown_and_canonical_passes_on_canonical():
    body = "claim_status: confirmed\nclaim_status: measured\n"
    ok, _ = validate(body)
    assert ok


def test_leading_whitespace_allowed():
    ok, _ = validate("    claim_status: derived\n")
    assert ok


def test_trailing_whitespace_allowed():
    ok, _ = validate("claim_status: derived     \n")
    assert ok


def test_crlf_line_endings_allowed():
    ok, _ = validate("claim_status: measured\r\n")
    assert ok


def test_label_with_internal_extra_space_not_counted():
    ok, reason = validate("claim_status: unverified  analogy\n")
    assert not ok
    assert "outside the canonical taxonomy" in reason
