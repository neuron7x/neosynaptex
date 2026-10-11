"""End-to-end tests: audit tools emit T2 telemetry via their ``main`` CLIs.

Each existing audit tool invoked via ``main`` produces three canonical
events per run: ``.run.start``, ``.verdict``, ``.run.end`` — per
``docs/protocols/telemetry_spine_spec.md §6``. These tests exercise
both tools live: a real ``run_audit`` sweep for
``claim_status_applied`` and a real ``validate`` call for
``pr_body_check``. The shared ``conftest.py`` autouse fixture routes
the telemetry sink into ``tmp_path``, so the tests never touch the
repo root.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

from tools.audit import claim_status_applied, pr_body_check
from tools.telemetry.schema import validate_events


def _read_sink() -> list[dict]:
    sink = pathlib.Path(os.environ["NEOSYNAPTEX_TELEMETRY_SINK"])
    if not sink.exists():
        return []
    return [json.loads(line) for line in sink.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# pr_body_check — canonical label present → ok
# ---------------------------------------------------------------------------


def test_pr_body_check_emits_start_end_and_verdict_on_canonical_label(tmp_path):
    body = tmp_path / "body.txt"
    body.write_text(
        "## Summary\n\nSome description.\n\nclaim_status: measured\n",
        encoding="utf-8",
    )
    rc = pr_body_check.main([str(body)])
    assert rc == 0

    events = _read_sink()
    types = [e["event_type"] for e in events]
    assert "audit.pr_body_check.run.start" in types
    assert "audit.pr_body_check.verdict" in types
    assert "audit.pr_body_check.run.end" in types

    verdict = next(e for e in events if e["event_type"].endswith(".verdict"))
    assert verdict["substrate"] == "audit.pr_body_check"
    assert verdict["outcome"] == "ok"
    assert verdict["payload"]["reason_head"].startswith("claim_status present")

    end = next(e for e in events if e["event_type"].endswith(".run.end"))
    assert end["outcome"] == "ok"
    assert end["duration_ms"] >= 0.0

    assert validate_events(events).ok


def test_pr_body_check_emits_fail_verdict_on_missing_label(tmp_path):
    body = tmp_path / "body.txt"
    body.write_text("## Summary\n\nno claim_status here\n", encoding="utf-8")
    rc = pr_body_check.main([str(body)])
    assert rc == 2

    events = _read_sink()
    verdict = next(e for e in events if e["event_type"].endswith(".verdict"))
    assert verdict["outcome"] == "fail"
    assert "missing a claim_status" in verdict["payload"]["reason_head"]

    end = next(e for e in events if e["event_type"].endswith(".run.end"))
    # The span completed normally (the CLI returned 2; it did not raise),
    # so the span end outcome is "ok" — the VERDICT event, not the span
    # end, carries the semantic failure. This is the correct separation.
    assert end["outcome"] == "ok"

    assert validate_events(events).ok


def test_pr_body_check_emits_fail_verdict_on_unknown_label(tmp_path):
    body = tmp_path / "body.txt"
    body.write_text("claim_status: maybe\n", encoding="utf-8")
    rc = pr_body_check.main([str(body)])
    assert rc == 2

    events = _read_sink()
    verdict = next(e for e in events if e["event_type"].endswith(".verdict"))
    assert verdict["outcome"] == "fail"
    assert "outside the\ncanonical" in verdict["payload"]["reason_head"] or (
        "outside the" in verdict["payload"]["reason_head"]
    )


def test_pr_body_check_verdict_events_share_single_trace(tmp_path):
    body = tmp_path / "body.txt"
    body.write_text("claim_status: measured\n", encoding="utf-8")
    pr_body_check.main([str(body)])
    events = _read_sink()
    traces = {e["trace_id"] for e in events}
    assert len(traces) == 1, "all three events from one CLI run share one trace"


# ---------------------------------------------------------------------------
# claim_status_applied — real git-log sweep (deterministic on this repo)
# ---------------------------------------------------------------------------


def test_claim_status_applied_emits_three_events_and_maps_verdict_outcome(
    capsys: pytest.CaptureFixture[str],
):
    # Real run against the repo's own git log. Verdict is whatever the
    # live repo produces — we do not assert its name, only shape.
    rc = claim_status_applied.main(["--window-days", "30", "--n-windows", "3"])
    assert rc == 0  # non-strict mode; always 0 regardless of verdict

    events = _read_sink()
    types = [e["event_type"] for e in events]
    assert "audit.claim_status.run.start" in types
    assert "audit.claim_status.run.end" in types
    assert "audit.claim_status.verdict" in types

    verdict = next(e for e in events if e["event_type"].endswith(".verdict"))
    assert verdict["substrate"] == "audit.claim_status"
    # Outcome must be one of the canonical schema values, mapped from
    # the audit's own verdict vocabulary.
    assert verdict["outcome"] in {"ok", "partial", "fail", "skip"}
    # Payload contains the verdict name and the window width.
    assert verdict["payload"]["n_windows"] == 3
    assert verdict["payload"]["window_days"] == 30
    # ``no_signal`` is a legitimate verdict of decide_verdict (latest
    # window has zero commits); a quiet month must not fail this test.
    assert verdict["payload"]["verdict"] in {"applied", "at_risk", "stopped", "no_signal"}

    assert validate_events(events).ok


def test_claim_status_applied_verdict_outcome_mapping_is_exhaustive():
    """Every canonical verdict name MUST map to a canonical outcome.

    Guards against future verdict names slipping past the mapping and
    being silently relabelled as ``skip`` (which the fallback uses as
    last-resort, not as a design choice).
    """

    # Current canonical verdict names, per decide_verdict implementation.
    canonical_verdicts = {"applied", "at_risk", "stopped"}
    mapping = claim_status_applied._VERDICT_OUTCOME
    assert canonical_verdicts.issubset(mapping.keys())
    assert set(mapping.values()) <= {"ok", "partial", "fail"}


# ---------------------------------------------------------------------------
# Silent-degradation contract: audit verdict does NOT depend on telemetry
# ---------------------------------------------------------------------------


def test_pr_body_check_result_unchanged_when_telemetry_sink_unwritable(tmp_path, monkeypatch):
    """Spec §8: observability is a side channel. A broken sink must
    never change the audit outcome.
    """

    broken_parent = tmp_path / "not_a_dir"
    broken_parent.write_text("stub\n")
    monkeypatch.setenv("NEOSYNAPTEX_TELEMETRY_SINK", str(broken_parent / "events.jsonl"))
    body = tmp_path / "body.txt"
    body.write_text("claim_status: measured\n", encoding="utf-8")
    assert pr_body_check.main([str(body)]) == 0  # unchanged
