"""Tests for the EAI false-promotion benchmark v1.

Each test pins one operational invariant of the benchmark:
- dataset composition (counts + completeness)
- report schema completeness
- false-promotion rate threshold
- boundary-violation hard floor
- adversarial-trap detection
- ambiguous-claim quarantine basin
- universal-claim rejection
- software-without-execution rejection
- deterministic replay across two runs
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.eai.run_false_promotion_benchmark import run_benchmark

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATASET = _REPO_ROOT / "data" / "eai_calibration" / "false_promotion_benchmark_v1.jsonl"


def _load_dataset() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in _DATASET.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def test_dataset_has_required_counts() -> None:
    rows = _load_dataset()
    assert len(rows) == 120, f"dataset must have 120 rows, got {len(rows)}"

    by_status = {"EVIDENCE": 0, "KILLED": 0, "QUARANTINED": 0}
    by_trap_nonzero = 0
    for r in rows:
        by_status[r["expected_status"]] += 1  # type: ignore[index]
        if r["trap_type"] != "none":
            by_trap_nonzero += 1

    assert by_status["EVIDENCE"] == 40
    # 40 false claims + 20 adversarial overclaim traps all map to KILLED.
    assert by_status["KILLED"] == 60
    assert by_status["QUARANTINED"] == 20
    assert by_trap_nonzero == 20


def test_dataset_has_expected_status_for_every_claim() -> None:
    rows = _load_dataset()
    for r in rows:
        assert "claim_id" in r and r["claim_id"]
        assert r["expected_status"] in {"EVIDENCE", "KILLED", "QUARANTINED"}
        assert isinstance(r["required_boundary"], list) and r["required_boundary"]
        assert isinstance(r["required_falsifiers"], list)
        assert isinstance(r["claim_text"], str) and r["claim_text"]


def test_benchmark_output_schema() -> None:
    report = run_benchmark(_DATASET)
    required_keys = {
        "schema_version",
        "dataset",
        "total",
        "true_positive_evidence",
        "false_promotion_count",
        "false_kill_count",
        "quarantine_accuracy",
        "boundary_violation_count",
        "trap_detection_rate",
        "false_promotion_rate",
        "thresholds",
        "decision",
    }
    missing = required_keys - set(report.keys())
    assert not missing, f"missing keys: {missing}"
    assert report["schema_version"] == "EAI-FP-BENCH-v1"
    assert set(report["thresholds"]) == {
        "max_false_promotion_rate",
        "max_boundary_violation_count",
    }
    assert report["decision"] in {"PASS", "FAIL"}


def test_false_promotion_rate_below_threshold() -> None:
    report = run_benchmark(_DATASET)
    assert report["false_promotion_rate"] <= report["thresholds"]["max_false_promotion_rate"], (
        f"false_promotion_rate={report['false_promotion_rate']} exceeds threshold "
        f"{report['thresholds']['max_false_promotion_rate']}"
    )


def test_boundary_violation_count_zero() -> None:
    report = run_benchmark(_DATASET)
    assert report["boundary_violation_count"] == 0, (
        f"boundary_violation_count must be 0; got {report['boundary_violation_count']}; "
        f"violators={[r for r in report['per_row'] if r['boundary_violated']]}"
    )


def test_adversarial_traps_detected() -> None:
    report = run_benchmark(_DATASET)
    # Every adversarial trap row must NOT be promoted to EVIDENCE; the
    # gate may KILL or QUARANTINE, but never promote.
    trap_outcomes = [r for r in report["per_row"] if r["trap_type"] != "none"]
    assert len(trap_outcomes) == 20
    leakers = [r for r in trap_outcomes if r["actual_status"] == "EVIDENCE"]
    assert not leakers, f"adversarial traps leaked to EVIDENCE: {leakers}"
    assert report["trap_detection_rate"] == 1.0


def test_ambiguous_claims_quarantined() -> None:
    report = run_benchmark(_DATASET)
    quarantine_rows = [r for r in report["per_row"] if r["expected_status"] == "QUARANTINED"]
    assert len(quarantine_rows) == 20
    promoted = [r for r in quarantine_rows if r["actual_status"] == "EVIDENCE"]
    killed = [r for r in quarantine_rows if r["actual_status"] == "KILLED"]
    assert not promoted, f"ambiguous claims must not be promoted: {promoted}"
    msg = f"ambiguous claims must not be killed (gate must withhold, not reject): {killed}"
    assert not killed, msg


def test_universal_claims_not_promoted() -> None:
    report = run_benchmark(_DATASET)
    universal_rows = [r for r in report["per_row"] if r["trap_type"] == "universal_claim"]
    assert universal_rows, "dataset must contain at least one universal_claim trap"
    leakers = [r for r in universal_rows if r["actual_status"] == "EVIDENCE"]
    assert not leakers, f"universal claims leaked: {leakers}"


def test_software_claim_without_execution_not_promoted() -> None:
    report = run_benchmark(_DATASET)
    sw_rows = [r for r in report["per_row"] if r["trap_type"] == "software_claim_without_execution"]
    assert sw_rows, "dataset must contain software_claim_without_execution traps"
    leakers = [r for r in sw_rows if r["actual_status"] == "EVIDENCE"]
    assert not leakers, f"software-without-execution claims leaked: {leakers}"


def test_report_is_deterministic_across_two_runs() -> None:
    a = run_benchmark(_DATASET)
    b = run_benchmark(_DATASET)
    # Compare deterministic-relevant fields; the report carries no
    # wall-clock timestamps (the ledger uses a frozen clock).
    for k in (
        "schema_version",
        "dataset_sha256",
        "total",
        "expected_counts",
        "actual_counts",
        "true_positive_evidence",
        "false_promotion_count",
        "false_kill_count",
        "quarantine_accuracy",
        "boundary_violation_count",
        "trap_detection_rate",
        "false_promotion_rate",
        "decision",
        "per_row",
    ):
        assert a[k] == b[k], f"non-deterministic field: {k}"
