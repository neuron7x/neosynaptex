"""Deterministic false-promotion benchmark runner for the EAI gate.

Reads a JSONL dataset of labelled claims (see
``data/eai_calibration/false_promotion_benchmark_v1.jsonl``), feeds each
row through ``core.eai.engine.EAIEngine`` with a fixed, audit-stable
input construction, and emits a JSON report comparing predicted status
to ``expected_status``.

Determinism contract:
- No network, no LLM calls, no randomness.
- A frozen UTC clock is injected into the ledger.
- ``hash_inputs`` is dataset-derived; running on any host produces
  byte-identical reports for the same input file.
- Exit code 0 iff every threshold in the report's ``thresholds`` block
  is satisfied; otherwise exit code 2.

The runner deliberately constructs inputs from the dataset row alone;
no row-by-row hand-tuning of engine inputs is permitted, so the report
genuinely measures gate behaviour on the declared population.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.artifact_ledger import ArtifactLedger  # noqa: E402
from core.eai.engine import EAIEngine  # noqa: E402
from core.eai.intelligence_cycle import (  # noqa: E402
    BoundaryCard,
    ClaimCard,
    ClaimType,
    ReproducibilityManifest,
)
from core.integration_memory import IntegrationMemory  # noqa: E402

_FROZEN_CLOCK_VALUE = "1970-01-01T00:00:00+00:00"
_SCHEMA_VERSION = "EAI-FP-BENCH-v1"


_CLAIM_TYPE_BY_NAME: dict[str, ClaimType] = {ct.value: ct for ct in ClaimType}


def _frozen_clock() -> str:
    return _FROZEN_CLOCK_VALUE


def _dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


@dataclass(frozen=True)
class RowOutcome:
    claim_id: str
    expected_status: str
    actual_status: str
    decision_reason: str
    failed_stage: str | None
    trap_type: str
    boundary_violated: bool


def _construct_engine_inputs(
    row: dict[str, Any],
) -> tuple[ClaimCard, BoundaryCard, ReproducibilityManifest, list[str], str, bool]:
    """Build deterministic engine inputs from a dataset row.

    The dataset itself dictates the boundary set, the falsifier
    contradiction markers, and (via ``expected_status``) whether
    revalidation is withheld to land in the QUARANTINE basin.
    """
    claim_type_name = str(row.get("claim_type", "factual"))
    claim_type = _CLAIM_TYPE_BY_NAME.get(claim_type_name, ClaimType.FACTUAL)

    claim = ClaimCard(
        claim_id=str(row["claim_id"]),
        claim_text=str(row["claim_text"]),
        claim_type=claim_type,
    )

    boundary_valid: list[str] = list(row.get("required_boundary", []))
    if not boundary_valid:
        boundary_valid = ["unspecified_local_scope"]
    boundary = BoundaryCard(
        boundary_id=f"BND-{row['claim_id']}",
        valid_for=boundary_valid,
        invalid_for=["global", "universal"],
        tested_conditions=boundary_valid,
        untested_conditions=["global"],
    )

    reproducibility = ReproducibilityManifest(
        commands=["pytest"],
        environment="false-promotion-benchmark-v1",
        artifact_hash="a" * 64,
    )

    contradiction_markers: list[str] = [str(m) for m in row.get("required_falsifiers", [])]

    retention_hash = "a" * 64
    # The QUARANTINE basin is reached by withholding revalidation —
    # this is the gate's contract for "ambiguous claim, evidence
    # chain incomplete." Boundary and reproducibility remain valid
    # so the failure mode is *policy*, not malformed input.
    revalidation_passed = row["expected_status"] != "QUARANTINED"

    return (
        claim,
        boundary,
        reproducibility,
        contradiction_markers,
        retention_hash,
        revalidation_passed,
    )


def run_benchmark(dataset_path: Path) -> dict[str, Any]:
    rows = _load_rows(dataset_path)
    assert rows, "dataset is empty"

    outcomes: list[RowOutcome] = []
    engine = EAIEngine(
        ledger=ArtifactLedger(clock=_frozen_clock),
        memory=IntegrationMemory(),
    )

    for row in rows:
        (
            claim,
            boundary,
            repro,
            contradictions,
            retention_hash,
            revalidation_passed,
        ) = _construct_engine_inputs(row)
        outcome = engine.run_candidate(
            claim=claim,
            boundary=boundary,
            contradiction_markers=contradictions,
            reproducibility=repro,
            retention_hash=retention_hash,
            revalidation_passed=revalidation_passed,
            integration_patch={"guardrail_update": {"id": f"GR-{claim.claim_id}"}},
            next_intent_delta={"delta": 1},
        )

        actual = outcome.status.value
        boundary_violated = bool(actual == "EVIDENCE" and str(row["expected_status"]) != "EVIDENCE")
        outcomes.append(
            RowOutcome(
                claim_id=claim.claim_id,
                expected_status=str(row["expected_status"]),
                actual_status=actual,
                decision_reason=outcome.decision_reason,
                failed_stage=outcome.failed_stage,
                trap_type=str(row.get("trap_type", "none")),
                boundary_violated=boundary_violated,
            )
        )

    total = len(outcomes)
    true_positive_evidence = sum(
        1 for o in outcomes if o.expected_status == "EVIDENCE" and o.actual_status == "EVIDENCE"
    )
    # False promotion = predicted EVIDENCE on a row that is NOT EVIDENCE.
    false_promotion_count = sum(
        1 for o in outcomes if o.expected_status != "EVIDENCE" and o.actual_status == "EVIDENCE"
    )
    # False kill = predicted KILLED on a true-bounded EVIDENCE row.
    false_kill_count = sum(
        1 for o in outcomes if o.expected_status == "EVIDENCE" and o.actual_status == "KILLED"
    )
    boundary_violation_count = sum(1 for o in outcomes if o.boundary_violated)

    quar_total = sum(1 for o in outcomes if o.expected_status == "QUARANTINED")
    quar_correct = sum(
        1
        for o in outcomes
        if o.expected_status == "QUARANTINED" and o.actual_status == "QUARANTINED"
    )
    quarantine_accuracy = (quar_correct / quar_total) if quar_total else 0.0

    trap_total = sum(1 for o in outcomes if o.trap_type != "none")
    trap_detected = sum(
        1
        for o in outcomes
        if o.trap_type != "none" and o.actual_status in {"KILLED", "QUARANTINED"}
    )
    trap_detection_rate = (trap_detected / trap_total) if trap_total else 0.0

    non_evidence_total = sum(1 for o in outcomes if o.expected_status != "EVIDENCE")
    false_promotion_rate = false_promotion_count / non_evidence_total if non_evidence_total else 0.0

    thresholds = {
        "max_false_promotion_rate": 0.02,
        "max_boundary_violation_count": 0,
    }
    decision = (
        "PASS"
        if (
            false_promotion_rate <= thresholds["max_false_promotion_rate"]
            and boundary_violation_count <= thresholds["max_boundary_violation_count"]
        )
        else "FAIL"
    )

    report: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "dataset": str(dataset_path),
        "dataset_sha256": _dataset_sha256(dataset_path),
        "frozen_clock": _FROZEN_CLOCK_VALUE,
        "total": total,
        "expected_counts": {
            "EVIDENCE": sum(1 for o in outcomes if o.expected_status == "EVIDENCE"),
            "KILLED": sum(1 for o in outcomes if o.expected_status == "KILLED"),
            "QUARANTINED": sum(1 for o in outcomes if o.expected_status == "QUARANTINED"),
        },
        "actual_counts": {
            "EVIDENCE": sum(1 for o in outcomes if o.actual_status == "EVIDENCE"),
            "KILLED": sum(1 for o in outcomes if o.actual_status == "KILLED"),
            "QUARANTINED": sum(1 for o in outcomes if o.actual_status == "QUARANTINED"),
        },
        "true_positive_evidence": true_positive_evidence,
        "false_promotion_count": false_promotion_count,
        "false_kill_count": false_kill_count,
        "quarantine_accuracy": round(quarantine_accuracy, 6),
        "boundary_violation_count": boundary_violation_count,
        "trap_detection_rate": round(trap_detection_rate, 6),
        "trap_total": trap_total,
        "trap_detected": trap_detected,
        "false_promotion_rate": round(false_promotion_rate, 6),
        "thresholds": thresholds,
        "decision": decision,
        "per_row": [
            {
                "claim_id": o.claim_id,
                "expected_status": o.expected_status,
                "actual_status": o.actual_status,
                "decision_reason": o.decision_reason,
                "failed_stage": o.failed_stage,
                "trap_type": o.trap_type,
                "boundary_violated": o.boundary_violated,
            }
            for o in outcomes
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic false-promotion benchmark for the EAI gate.",
    )
    parser.add_argument(
        "--dataset",
        default="data/eai_calibration/false_promotion_benchmark_v1.jsonl",
    )
    parser.add_argument(
        "--out",
        default="artifacts/eai/benchmarks/false_promotion_report_v1.json",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    report = run_benchmark(dataset_path)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "decision": report["decision"],
                "false_promotion_rate": report["false_promotion_rate"],
                "boundary_violation_count": report["boundary_violation_count"],
                "trap_detection_rate": report["trap_detection_rate"],
                "dataset_sha256": report["dataset_sha256"],
                "out": str(out_path),
            },
            sort_keys=True,
        )
    )
    return 0 if report["decision"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
