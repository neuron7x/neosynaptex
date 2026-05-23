"""Deterministic tests for the telemetry event-schema validator.

Pins the contract in ``docs/protocols/telemetry_spine_spec.md`` §5/§6
against the canonical golden fixture plus per-failure-mode negatives.
"""

from __future__ import annotations

import json

import pytest

from tools.telemetry.schema import (
    CANONICAL_EVENT_TYPE_PATTERNS,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    VALID_OUTCOMES,
    ValidationError,
    ValidationReport,
    validate_event,
    validate_events,
    validate_jsonl_text,
)

# ---------------------------------------------------------------------------
# Golden fixture — the canonical v1 event every emitter must produce
# ---------------------------------------------------------------------------


_GOLDEN_EVENT: dict = {
    "schema_version": "v1",
    "trace_id": "a" * 32,
    "span_id": "b" * 16,
    "parent_span_id": None,
    "timestamp_utc": "2026-04-14T12:00:00.123Z",
    "event_type": "audit.claim_status.run.end",
    "substrate": "audit.claim_status",
    "commit_sha": "0" * 40,
    "outcome": "ok",
    "duration_ms": 42.5,
    "payload": {"verdict": "at_risk", "redactions": []},
    "links": [],
}


def test_golden_event_validates():
    assert validate_event(_GOLDEN_EVENT) == ()


def test_required_fields_constant_has_exactly_eight():
    """Schema v1 locks 8 required fields per spec §5."""

    assert len(REQUIRED_FIELDS) == 8
    assert set(REQUIRED_FIELDS) == {
        "schema_version",
        "trace_id",
        "span_id",
        "parent_span_id",
        "timestamp_utc",
        "event_type",
        "substrate",
        "commit_sha",
    }


def test_optional_fields_constant_has_exactly_four():
    assert len(OPTIONAL_FIELDS) == 4
    assert set(OPTIONAL_FIELDS) == {"outcome", "duration_ms", "payload", "links"}


def test_schema_version_is_v1():
    assert SCHEMA_VERSION == "v1"


def test_valid_outcomes_are_exactly_four():
    assert {"ok", "fail", "partial", "skip"} == VALID_OUTCOMES


# ---------------------------------------------------------------------------
# Non-dict root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "a string", 42, [1, 2, 3], 3.14])
def test_non_object_root_is_invalid(bad):
    errors = validate_event(bad)
    assert len(errors) == 1
    assert errors[0].field == "<root>"


# ---------------------------------------------------------------------------
# Required field presence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", list(REQUIRED_FIELDS))
def test_missing_required_field_is_flagged(missing):
    event = dict(_GOLDEN_EVENT)
    event.pop(missing)
    errors = validate_event(event)
    fields = {e.field for e in errors}
    assert missing in fields


def test_missing_multiple_required_fields_reports_each():
    event = {}
    errors = validate_event(event)
    flagged = {e.field for e in errors}
    for required in REQUIRED_FIELDS:
        assert required in flagged


# ---------------------------------------------------------------------------
# schema_version
# ---------------------------------------------------------------------------


def test_wrong_schema_version_fails():
    event = dict(_GOLDEN_EVENT)
    event["schema_version"] = "v2"
    errors = validate_event(event)
    assert any(e.field == "schema_version" and "v1" in e.reason for e in errors)


def test_non_string_schema_version_fails():
    event = dict(_GOLDEN_EVENT)
    event["schema_version"] = 1
    errors = validate_event(event)
    assert any(e.field == "schema_version" for e in errors)


# ---------------------------------------------------------------------------
# trace_id / span_id shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["trace_id", "span_id"],
)
def test_hex_id_accepts_32_hex(field):
    event = dict(_GOLDEN_EVENT)
    event[field] = "1234567890abcdef" * 2  # 32 hex
    assert not [e for e in validate_event(event) if e.field == field]


@pytest.mark.parametrize(
    "field",
    ["trace_id", "span_id"],
)
def test_hex_id_accepts_uuid_with_dashes(field):
    event = dict(_GOLDEN_EVENT)
    event[field] = "00000000-0000-4000-8000-000000000000"
    assert not [e for e in validate_event(event) if e.field == field]


@pytest.mark.parametrize("field", ["trace_id", "span_id"])
def test_hex_id_rejects_non_hex(field):
    event = dict(_GOLDEN_EVENT)
    event[field] = "not-a-hex-id-at-all-really-really"
    errors = validate_event(event)
    assert any(e.field == field for e in errors)


@pytest.mark.parametrize("field", ["trace_id", "span_id"])
def test_hex_id_rejects_too_short(field):
    event = dict(_GOLDEN_EVENT)
    event[field] = "abc"
    errors = validate_event(event)
    assert any(e.field == field for e in errors)


def test_parent_span_id_null_is_valid():
    event = dict(_GOLDEN_EVENT)
    event["parent_span_id"] = None
    assert not [e for e in validate_event(event) if e.field == "parent_span_id"]


def test_parent_span_id_hex_is_valid():
    event = dict(_GOLDEN_EVENT)
    event["parent_span_id"] = "f" * 16
    assert not [e for e in validate_event(event) if e.field == "parent_span_id"]


def test_parent_span_id_bad_value_is_flagged():
    event = dict(_GOLDEN_EVENT)
    event["parent_span_id"] = "???"
    errors = validate_event(event)
    assert any(e.field == "parent_span_id" for e in errors)


# ---------------------------------------------------------------------------
# timestamp_utc
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ts",
    [
        "2026-04-14T00:00:00.000Z",
        "2026-04-14T00:00:00.123Z",
        "2026-04-14T00:00:00.123456Z",  # microsecond precision allowed
        "2026-04-14T00:00:00.123+00:00",
    ],
)
def test_timestamp_accepts_rfc3339_utc_ms_or_finer(ts):
    event = dict(_GOLDEN_EVENT)
    event["timestamp_utc"] = ts
    assert not [e for e in validate_event(event) if e.field == "timestamp_utc"]


@pytest.mark.parametrize(
    "bad",
    [
        "2026-04-14T00:00:00Z",  # no fractional seconds
        "2026-04-14T00:00:00.12Z",  # only 2-digit fractional
        "2026-04-14 00:00:00.123Z",  # space instead of T
        "2026-04-14T00:00:00.123",  # no timezone
        "2026-04-14T00:00:00.123+05:00",  # non-UTC offset
    ],
)
def test_timestamp_rejects_non_canonical(bad):
    event = dict(_GOLDEN_EVENT)
    event["timestamp_utc"] = bad
    errors = validate_event(event)
    assert any(e.field == "timestamp_utc" for e in errors)


# ---------------------------------------------------------------------------
# event_type namespace coverage (spec §6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [
        "substrate.bn_syn.run.start",
        "substrate.bn_syn.run.end",
        "substrate.mfn_plus.regime.compressed.cell",
        "audit.claim_status.run.start",
        "audit.claim_status.run.end",
        "audit.claim_status.verdict",
        "ci.claim_status_check.job.check.start",
        "ci.claim_status_check.job.check.end",
        "pr_lifecycle.opened",
        "pr_lifecycle.edited",
        "pr_lifecycle.synchronized",
        "pr_lifecycle.reopened",
        "pr_lifecycle.closed",
        "pr_lifecycle.merged",
        "evidence.levin_bridge.append",
        "canon.SYSTEM_PROTOCOL.change",
    ],
)
def test_canonical_event_types_are_accepted(event_type):
    event = dict(_GOLDEN_EVENT)
    event["event_type"] = event_type
    assert not [e for e in validate_event(event) if e.field == "event_type"]


@pytest.mark.parametrize(
    "event_type",
    [
        "random.thing",
        "substrate.bn_syn.run.unknown",
        "pr_lifecycle.deleted",  # not in the enumerated action list
        "audit..verdict",  # empty segment
        "canon",  # no dotted structure
        "",  # empty
    ],
)
def test_non_canonical_event_types_are_rejected(event_type):
    event = dict(_GOLDEN_EVENT)
    event["event_type"] = event_type
    errors = validate_event(event)
    assert any(e.field == "event_type" for e in errors)


def test_canonical_patterns_list_is_non_empty():
    assert len(CANONICAL_EVENT_TYPE_PATTERNS) >= 6


# ---------------------------------------------------------------------------
# commit_sha
# ---------------------------------------------------------------------------


def test_commit_sha_40_hex_valid():
    event = dict(_GOLDEN_EVENT)
    event["commit_sha"] = "a" * 40
    assert not [e for e in validate_event(event) if e.field == "commit_sha"]


def test_commit_sha_unstamped_sentinel_valid():
    event = dict(_GOLDEN_EVENT)
    event["commit_sha"] = "UNSTAMPED:abc123def456"
    assert not [e for e in validate_event(event) if e.field == "commit_sha"]


@pytest.mark.parametrize(
    "bad",
    [
        "a" * 39,  # one short
        "a" * 41,  # one too many
        "UNSTAMPED:",  # missing sentinel payload
        "UNSTAMPED:abc",  # wrong sentinel length
        "",
        "not-hex-at-all-at-all-at-all-at-all-at",
    ],
)
def test_commit_sha_invalid_shapes(bad):
    event = dict(_GOLDEN_EVENT)
    event["commit_sha"] = bad
    errors = validate_event(event)
    assert any(e.field == "commit_sha" for e in errors)


# ---------------------------------------------------------------------------
# Optional fields — outcome
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("val", sorted(VALID_OUTCOMES))
def test_valid_outcome_accepted(val):
    event = dict(_GOLDEN_EVENT)
    event["outcome"] = val
    assert not [e for e in validate_event(event) if e.field == "outcome"]


@pytest.mark.parametrize("bad", ["success", "FAIL", 1, True, ""])
def test_invalid_outcome_rejected(bad):
    event = dict(_GOLDEN_EVENT)
    event["outcome"] = bad
    errors = validate_event(event)
    assert any(e.field == "outcome" for e in errors)


def test_missing_outcome_is_fine():
    event = dict(_GOLDEN_EVENT)
    event.pop("outcome")
    assert not [e for e in validate_event(event) if e.field == "outcome"]


# ---------------------------------------------------------------------------
# Optional fields — duration_ms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("val", [0, 0.0, 42, 42.5, 1e6])
def test_non_negative_duration_accepted(val):
    event = dict(_GOLDEN_EVENT)
    event["duration_ms"] = val
    assert not [e for e in validate_event(event) if e.field == "duration_ms"]


@pytest.mark.parametrize("bad", [-1, -0.001, "42", None, True])
def test_bad_duration_rejected(bad):
    event = dict(_GOLDEN_EVENT)
    event["duration_ms"] = bad
    errors = validate_event(event)
    assert any(e.field == "duration_ms" for e in errors)


# ---------------------------------------------------------------------------
# Optional fields — payload + redactions
# ---------------------------------------------------------------------------


def test_payload_must_be_object():
    event = dict(_GOLDEN_EVENT)
    event["payload"] = "a string"
    errors = validate_event(event)
    assert any(e.field == "payload" for e in errors)


def test_payload_redactions_must_be_list():
    event = dict(_GOLDEN_EVENT)
    event["payload"] = {"redactions": "not a list"}
    errors = validate_event(event)
    assert any(e.field == "payload.redactions" for e in errors)


def test_payload_redactions_list_is_valid():
    event = dict(_GOLDEN_EVENT)
    event["payload"] = {"redactions": [{"rule": "sha256-pii"}]}
    assert not validate_event(event)


# ---------------------------------------------------------------------------
# Optional fields — links
# ---------------------------------------------------------------------------


def test_links_must_be_array():
    event = dict(_GOLDEN_EVENT)
    event["links"] = {"not": "array"}
    errors = validate_event(event)
    assert any(e.field == "links" for e in errors)


def test_link_missing_required_sub_field_flagged():
    event = dict(_GOLDEN_EVENT)
    event["links"] = [{"trace_id": "a" * 32}]  # missing span_id, relation
    errors = validate_event(event)
    flagged = {e.field for e in errors}
    assert "links[0].span_id" in flagged
    assert "links[0].relation" in flagged


def test_valid_link_passes():
    event = dict(_GOLDEN_EVENT)
    event["links"] = [
        {"trace_id": "a" * 32, "span_id": "b" * 16, "relation": "follows"},
    ]
    assert not validate_event(event)


# ---------------------------------------------------------------------------
# Extension rule — unknown top-level keys rejected
# ---------------------------------------------------------------------------


def test_unknown_top_level_key_rejected():
    event = dict(_GOLDEN_EVENT)
    event["custom_field"] = "whatever"
    errors = validate_event(event)
    assert any(e.field == "custom_field" for e in errors)


# ---------------------------------------------------------------------------
# Batch + JSONL
# ---------------------------------------------------------------------------


def test_validate_events_counts_valid_and_invalid():
    events = [
        _GOLDEN_EVENT,
        {**_GOLDEN_EVENT, "schema_version": "v2"},  # invalid
        _GOLDEN_EVENT,
    ]
    report = validate_events(events)
    assert isinstance(report, ValidationReport)
    assert report.total == 3
    assert report.valid == 2
    assert report.invalid == 1
    assert 1 in report.errors_by_index


def test_validate_jsonl_text_skips_blank_lines():
    text = json.dumps(_GOLDEN_EVENT) + "\n\n" + json.dumps(_GOLDEN_EVENT) + "\n"
    report = validate_jsonl_text(text)
    assert report.total == 2
    assert report.valid == 2
    assert report.ok


def test_validate_jsonl_text_handles_malformed_json():
    text = "{this is not json\n" + json.dumps(_GOLDEN_EVENT) + "\n"
    report = validate_jsonl_text(text)
    assert report.total == 2
    # First line is a parse error; second is valid.
    assert report.valid == 1
    assert 0 in report.errors_by_index


def test_validation_error_as_str_has_field_and_reason():
    err = ValidationError(field="foo", reason="bar")
    s = err.as_str()
    assert "foo" in s
    assert "bar" in s


def test_report_ok_property():
    good = validate_events([_GOLDEN_EVENT])
    assert good.ok
    bad = validate_events([_GOLDEN_EVENT, {}])
    assert not bad.ok
