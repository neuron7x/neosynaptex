"""STN-analog falsifiability test runner (v1).

CONTRACT:
    pre:  dataset path (JSONL with v1_1 schema); output path.
    post: writes deterministic JSON report comparing two gate
          configurations (binary vs graded) on the dataset and
          emits a pre-registered verdict.
    fail: exit 33 on NULL_RESULT, exit 22 on FALSIFIED, exit 0 on
          SUPPORTED. Exit 1 is RESERVED for Python uncaught-exception
          default — CI must treat 1 as a runner-failure (block build),
          NOT as a benign NULL_RESULT. Rare codes (22, 33) are
          unambiguous verdict signals.
    inv:  the binary configuration uses the SAME code paths and
          inputs the test harness in PR #192 used, so binary
          results are byte-comparable to the prior benchmark
          report (modulo dataset extension).

Pre-registered verdict rules (declared BEFORE running):
    SUPPORTED iff
        graded.subtle_slice_false_promotion < binary.subtle_slice_false_promotion
        AND graded.true_positive_evidence >= binary.true_positive_evidence
    FALSIFIED iff
        graded.true_positive_evidence < binary.true_positive_evidence
        (the graded gate kills real evidence; STN-analog hypothesis
         falsified at this fidelity)
    NULL_RESULT iff neither (no movement on subtle slice; gate
        change had no measurable effect)

Determinism: frozen UTC clock, sha-pinned dataset, no network,
no PRNG. Two consecutive runs produce byte-identical reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.eai.graded_gate import decide_with_graded_threshold  # noqa: E402
from core.eai.intelligence_cycle import (  # noqa: E402
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)
from core.falsification_engine import (  # noqa: E402
    falsification_decision,
    falsification_decision_graded,
)

_SCHEMA_VERSION = "EAI-FALSIFIABILITY-TEST-v1"

# Number of dummy revalidation evidence paths available for each row.
# The graded gate's required threshold is ceil(1 + conflict*2); we
# expose 2 paths so:
#   c = 0.0       -> required 1, available 2 -> EVIDENCE
#   c <= 0.5      -> required 2, available 2 -> EVIDENCE
#   c > 0.5       -> required 3, available 2 -> QUARANTINED
# This puts the threshold deliberately at the subtle slice's
# expected conflict_strength range so the test is non-degenerate.
_AVAILABLE_REVALIDATION_PATHS = ["path_primary", "path_replication"]

_CLAIM_TYPE_BY_NAME: dict[str, ClaimType] = {ct.value: ct for ct in ClaimType}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    return rows


def _build_artifact(row: dict[str, Any]) -> EvidenceArtifact:
    claim_type_name = str(row.get("claim_type", "factual"))
    claim_type = _CLAIM_TYPE_BY_NAME.get(claim_type_name, ClaimType.FACTUAL)
    claim = ClaimCard(
        claim_id=str(row["claim_id"]),
        claim_text=str(row["claim_text"]),
        claim_type=claim_type,
    )
    boundary_valid = list(row.get("required_boundary", [])) or ["unspecified"]
    boundary = BoundaryCard(
        boundary_id=f"BND-{row['claim_id']}",
        valid_for=boundary_valid,
        invalid_for=["global", "universal"],
        tested_conditions=boundary_valid,
        untested_conditions=["other_substrates"],
    )
    repro = ReproducibilityManifest(
        commands=["pytest"],
        environment="falsifiability-test-v1",
        artifact_hash="a" * 64,
    )
    # Note: the EvidenceArtifact's FalsificationReport here is the
    # *engine's* internal report (mirroring the production engine's
    # `FalsificationReport(["gate_falsification"], True)` synthesis).
    # The actual falsification verdict from the engine surface
    # (binary or graded) is computed separately below; this report
    # only satisfies `can_be_promoted`'s structural check.
    return EvidenceArtifact(
        artifact_id=f"EVD-{row['claim_id']}",
        claim=claim,
        boundary=boundary,
        falsification_report=FalsificationReport(["gate_falsification"], True),
        reproducibility=repro,
        integration_permission=True,
        revalidation_evidence_paths=list(_AVAILABLE_REVALIDATION_PATHS),
    )


@dataclass(frozen=True)
class _RowVerdict:
    claim_id: str
    expected_status: str
    subtle: bool
    negative_control: bool
    trap_type: str
    actual_status: str
    conflict_strength: float
    required_paths: int
    available_paths: int
    reason: str


def _run_binary_mode(rows: list[dict[str, Any]]) -> list[_RowVerdict]:
    """Binary mode: substring-only falsifier + classic IEV
    semantics. Replicates PR #192 engine behaviour."""
    verdicts: list[_RowVerdict] = []
    for row in rows:
        markers = [str(m) for m in row.get("required_falsifiers", [])]
        passed, reason = falsification_decision(str(row["claim_text"]), markers)
        if not passed:
            actual = "KILLED"
        else:
            # In binary mode the IEV gate sees revalidation_passed=True
            # for EVIDENCE-expected rows and False for QUARANTINED-expected
            # rows (mirrors PR #192 runner). For KILL-expected rows we
            # never reach this branch unless falsifier missed.
            revalidation_passed = row["expected_status"] != "QUARANTINED"
            artifact = _build_artifact(row)
            decision = decide_with_graded_threshold(
                artifact,
                retention_hash="a" * 64,
                revalidation_passed=revalidation_passed,
                conflict_strength=0.0,  # binary mode = no graded threshold
            )
            actual = decision.status
            reason = decision.reason
        verdicts.append(
            _RowVerdict(
                claim_id=str(row["claim_id"]),
                expected_status=str(row["expected_status"]),
                subtle=bool(row.get("subtle", False)),
                negative_control=bool(row.get("negative_control", False)),
                trap_type=str(row.get("trap_type", "none")),
                actual_status=actual,
                conflict_strength=0.0,
                required_paths=1,
                available_paths=len(_AVAILABLE_REVALIDATION_PATHS),
                reason=reason,
            )
        )
    return verdicts


def _run_graded_mode(rows: list[dict[str, Any]]) -> list[_RowVerdict]:
    """Graded mode: token-overlap falsifier + conflict-modulated IEV
    threshold."""
    verdicts: list[_RowVerdict] = []
    for row in rows:
        markers = [str(m) for m in row.get("required_falsifiers", [])]
        gr = falsification_decision_graded(str(row["claim_text"]), markers)
        if not gr.passed:
            verdicts.append(
                _RowVerdict(
                    claim_id=str(row["claim_id"]),
                    expected_status=str(row["expected_status"]),
                    subtle=bool(row.get("subtle", False)),
                    negative_control=bool(row.get("negative_control", False)),
                    trap_type=str(row.get("trap_type", "none")),
                    actual_status="KILLED",
                    conflict_strength=gr.conflict_strength,
                    required_paths=0,
                    available_paths=len(_AVAILABLE_REVALIDATION_PATHS),
                    reason=gr.reason,
                )
            )
            continue
        revalidation_passed = row["expected_status"] != "QUARANTINED"
        artifact = _build_artifact(row)
        decision = decide_with_graded_threshold(
            artifact,
            retention_hash="a" * 64,
            revalidation_passed=revalidation_passed,
            conflict_strength=gr.conflict_strength,
        )
        verdicts.append(
            _RowVerdict(
                claim_id=str(row["claim_id"]),
                expected_status=str(row["expected_status"]),
                subtle=bool(row.get("subtle", False)),
                negative_control=bool(row.get("negative_control", False)),
                trap_type=str(row.get("trap_type", "none")),
                actual_status=decision.status,
                conflict_strength=gr.conflict_strength,
                required_paths=decision.required_paths,
                available_paths=decision.available_paths,
                reason=decision.reason,
            )
        )
    return verdicts


def _summarise(verdicts: list[_RowVerdict]) -> dict[str, Any]:
    total = len(verdicts)
    total_subtle_kill = sum(
        1 for v in verdicts if v.subtle and not v.negative_control and v.expected_status == "KILLED"
    )
    subtle_kill_promoted = sum(
        1
        for v in verdicts
        if v.subtle
        and not v.negative_control
        and v.expected_status == "KILLED"
        and v.actual_status == "EVIDENCE"
    )
    neg_control_total = sum(1 for v in verdicts if v.negative_control)
    neg_control_evidence = sum(
        1 for v in verdicts if v.negative_control and v.actual_status == "EVIDENCE"
    )
    tp_evidence = sum(
        1 for v in verdicts if v.expected_status == "EVIDENCE" and v.actual_status == "EVIDENCE"
    )
    fp = sum(
        1 for v in verdicts if v.expected_status != "EVIDENCE" and v.actual_status == "EVIDENCE"
    )
    fk = sum(1 for v in verdicts if v.expected_status == "EVIDENCE" and v.actual_status == "KILLED")
    counts = Counter(v.actual_status for v in verdicts)
    return {
        "total": total,
        "verdict_counts": dict(sorted(counts.items())),
        "true_positive_evidence": tp_evidence,
        "false_promotion_count": fp,
        "false_kill_count": fk,
        "subtle_slice_total": total_subtle_kill,
        "subtle_slice_false_promotion": subtle_kill_promoted,
        "subtle_slice_false_promotion_rate": (
            round(subtle_kill_promoted / total_subtle_kill, 6) if total_subtle_kill else 0.0
        ),
        "negative_control_total": neg_control_total,
        "negative_control_passed_as_evidence": neg_control_evidence,
        "negative_control_pass_rate": (
            round(neg_control_evidence / neg_control_total, 6) if neg_control_total else 0.0
        ),
    }


def _verdict_rules(binary: dict[str, Any], graded: dict[str, Any]) -> tuple[str, str]:
    """Apply pre-registered verdict rules. Returns (verdict, reason).
    These rules are declared in module docstring and in
    docs/research/EAI_GRADED_FALSIFICATION_V1.md BEFORE first run.
    """
    if graded["true_positive_evidence"] < binary["true_positive_evidence"]:
        return (
            "HYPOTHESIS_FALSIFIED",
            f"graded.true_positive_evidence={graded['true_positive_evidence']} "
            f"< binary.true_positive_evidence={binary['true_positive_evidence']}; "
            "graded gate killed real evidence",
        )
    if (
        graded["subtle_slice_false_promotion"] < binary["subtle_slice_false_promotion"]
        and graded["true_positive_evidence"] >= binary["true_positive_evidence"]
    ):
        return (
            "HYPOTHESIS_SUPPORTED",
            f"graded reduced subtle-slice false_promotion from "
            f"{binary['subtle_slice_false_promotion']} to "
            f"{graded['subtle_slice_false_promotion']} without dropping TP "
            f"({binary['true_positive_evidence']} -> {graded['true_positive_evidence']})",
        )
    return (
        "NULL_RESULT",
        f"no measurable improvement on subtle slice "
        f"(binary={binary['subtle_slice_false_promotion']}, "
        f"graded={graded['subtle_slice_false_promotion']}); "
        "STN-analog not demonstrated at this fidelity",
    )


def run_falsifiability_test(dataset_path: Path) -> dict[str, Any]:
    rows = _load_rows(dataset_path)
    if not rows:
        raise ValueError("dataset is empty")

    binary_verdicts = _run_binary_mode(rows)
    graded_verdicts = _run_graded_mode(rows)
    binary_summary = _summarise(binary_verdicts)
    graded_summary = _summarise(graded_verdicts)
    verdict, verdict_reason = _verdict_rules(binary_summary, graded_summary)

    return {
        "schema_version": _SCHEMA_VERSION,
        "dataset_path": str(dataset_path),
        "dataset_sha256": _file_sha256(dataset_path),
        "total_rows": len(rows),
        "binary": binary_summary,
        "graded": graded_summary,
        "hypothesis": (
            "STN-analog: graded falsification with conflict-modulated IEV "
            "threshold reduces false promotion on the subtle-contradiction "
            "slice without regressing true evidence on the EVIDENCE slice."
        ),
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "per_row_binary": [
            {
                "claim_id": v.claim_id,
                "expected_status": v.expected_status,
                "actual_status": v.actual_status,
                "subtle": v.subtle,
                "negative_control": v.negative_control,
                "trap_type": v.trap_type,
                "conflict_strength": v.conflict_strength,
                "reason": v.reason,
            }
            for v in binary_verdicts
        ],
        "per_row_graded": [
            {
                "claim_id": v.claim_id,
                "expected_status": v.expected_status,
                "actual_status": v.actual_status,
                "subtle": v.subtle,
                "negative_control": v.negative_control,
                "trap_type": v.trap_type,
                "conflict_strength": v.conflict_strength,
                "required_paths": v.required_paths,
                "available_paths": v.available_paths,
                "reason": v.reason,
            }
            for v in graded_verdicts
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="STN-analog falsifiability test: binary vs graded gate on v1_1 dataset.",
    )
    parser.add_argument(
        "--dataset",
        default="data/eai_calibration/false_promotion_benchmark_v1_1.jsonl",
    )
    parser.add_argument(
        "--out",
        default="artifacts/eai/benchmarks/falsifiability_test_v1_report.json",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    report = run_falsifiability_test(dataset_path)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "verdict_reason": report["verdict_reason"],
                "binary.subtle_slice_false_promotion": report["binary"][
                    "subtle_slice_false_promotion"
                ],
                "graded.subtle_slice_false_promotion": report["graded"][
                    "subtle_slice_false_promotion"
                ],
                "binary.true_positive_evidence": report["binary"]["true_positive_evidence"],
                "graded.true_positive_evidence": report["graded"]["true_positive_evidence"],
                "dataset_sha256": report["dataset_sha256"],
                "out": str(out_path),
            },
            sort_keys=True,
        )
    )
    # Verdict-specific exit codes, chosen to NOT collide with Python's
    # default exit code 1 (uncaught exception). Codex P1: distinguishing
    # NULL_RESULT from runner crash is critical, because a silent bug
    # in the runner would have exit code 1 and be misread as a benign
    # NULL_RESULT by CI.
    #   0  = HYPOTHESIS_SUPPORTED
    #   22 = HYPOTHESIS_FALSIFIED (CI MUST block)
    #   33 = NULL_RESULT          (CI warning, build passes)
    #   1  = reserved for Python's uncaught-exception default
    #         (handled by CI as runner failure, build blocks)
    if report["verdict"] == "HYPOTHESIS_SUPPORTED":
        return 0
    if report["verdict"] == "HYPOTHESIS_FALSIFIED":
        return 22
    return 33  # NULL_RESULT


if __name__ == "__main__":
    raise SystemExit(main())
