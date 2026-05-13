"""Run every γ-ledger entry through the EAI gate, emit a deterministic decision report.

This is a *measurement of admissibility*, not a re-assertion of γ. The
ledger is read-only. The output JSON records, for each entry, what
verdict the EAI gate produced under the deterministic input mapping
defined in ``core/eai/gamma_bridge.py``.

Determinism:
- No network, no LLM, no PRNG.
- Frozen UTC clock injected into the ledger transcript.
- ``ledger_sha256`` and ``bridge_module_sha256`` pin the inputs.
- The report is byte-identical across re-runs for the same ledger.

Exit codes:
- 0 always (this is a measurement, not a pass/fail gate). Aggregate
  metrics are emitted to the report for downstream CI checks to
  enforce thresholds.
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

from core.artifact_ledger import ArtifactLedger  # noqa: E402
from core.eai.engine import EAIEngine  # noqa: E402
from core.eai.gamma_bridge import (  # noqa: E402
    GammaGateInputs,
    ledger_entry_to_gate_inputs,
    load_ledger,
)
from core.integration_memory import IntegrationMemory  # noqa: E402

_FROZEN_CLOCK_VALUE = "1970-01-01T00:00:00+00:00"
_SCHEMA_VERSION = "EAI-GAMMA-BRIDGE-v1"


def _frozen_clock() -> str:
    return _FROZEN_CLOCK_VALUE


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class EntryReport:
    ledger_key: str
    substrate: str
    ledger_status: str
    ledger_evidence_tier: str
    hash_bound: bool
    status_tags: list[str]
    gate_status: str
    gate_decision_reason: str
    gate_failed_stage: str | None
    artifact_id: str
    retention_hash: str


def _run_entry(
    engine: EAIEngine, key: str, entry: dict[str, Any], gi: GammaGateInputs
) -> EntryReport:
    outcome = engine.run_candidate(
        claim=gi.claim,
        boundary=gi.boundary,
        contradiction_markers=gi.contradiction_markers,
        reproducibility=gi.reproducibility,
        retention_hash=gi.retention_hash,
        revalidation_passed=gi.revalidation_passed,
        integration_patch={"guardrail_update": {"id": f"GR-{gi.claim.claim_id}"}},
        next_intent_delta={"delta": 1},
    )
    return EntryReport(
        ledger_key=key,
        substrate=str(entry.get("substrate") or "unknown"),
        ledger_status=str(entry.get("status") or ""),
        ledger_evidence_tier=str(entry.get("evidence_tier") or ""),
        hash_bound=gi.hash_bound,
        status_tags=list(gi.status_tags),
        gate_status=outcome.status.value,
        gate_decision_reason=outcome.decision_reason,
        gate_failed_stage=outcome.failed_stage,
        artifact_id=outcome.ledger_entry.artifact_id,
        retention_hash=outcome.ledger_entry.retention_hash,
    )


def run_bridge(ledger_path: Path, bridge_module_path: Path) -> dict[str, Any]:
    version, entries = load_ledger(ledger_path)
    engine = EAIEngine(
        ledger=ArtifactLedger(clock=_frozen_clock),
        memory=IntegrationMemory(),
    )

    reports: list[EntryReport] = []
    for key in sorted(entries):
        entry = entries[key]
        gate_inputs = ledger_entry_to_gate_inputs(key, entry, ledger_version=version)
        reports.append(_run_entry(engine, key, entry, gate_inputs))

    total = len(reports)
    gate_counts = Counter(r.gate_status for r in reports)
    hash_bound_count = sum(1 for r in reports if r.hash_bound)

    # Admissibility = gate verdict EVIDENCE on a ledger entry whose
    # status is the published EVIDENCE_CANDIDATE (i.e. the ledger
    # asserts measurement-grade and the gate agrees).
    admissible_evidence = sum(
        1
        for r in reports
        if r.gate_status == "EVIDENCE" and r.ledger_status == "EVIDENCE_CANDIDATE"
    )
    candidate_total = sum(1 for r in reports if r.ledger_status == "EVIDENCE_CANDIDATE")
    admissibility_rate = admissible_evidence / candidate_total if candidate_total else 0.0

    report: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "ledger_path": str(ledger_path),
        "ledger_version": version,
        "ledger_sha256": _file_sha256(ledger_path),
        "bridge_module_sha256": _file_sha256(bridge_module_path),
        "frozen_clock": _FROZEN_CLOCK_VALUE,
        "total_entries": total,
        "gate_verdict_counts": dict(sorted(gate_counts.items())),
        "hash_bound_count": hash_bound_count,
        "candidate_total": candidate_total,
        "admissible_evidence": admissible_evidence,
        "admissibility_rate": round(admissibility_rate, 6),
        "per_entry": [
            {
                "ledger_key": r.ledger_key,
                "substrate": r.substrate,
                "ledger_status": r.ledger_status,
                "ledger_evidence_tier": r.ledger_evidence_tier,
                "hash_bound": r.hash_bound,
                "status_tags": r.status_tags,
                "gate_status": r.gate_status,
                "gate_decision_reason": r.gate_decision_reason,
                "gate_failed_stage": r.gate_failed_stage,
                "artifact_id": r.artifact_id,
                "retention_hash": r.retention_hash,
            }
            for r in reports
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run every γ-ledger entry through the EAI gate and emit a JSON report.",
    )
    parser.add_argument("--ledger", default="evidence/gamma_ledger.json")
    parser.add_argument(
        "--out",
        default="artifacts/eai/benchmarks/gamma_ledger_gate_decisions_v1.json",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    bridge_module_path = _REPO_ROOT / "core" / "eai" / "gamma_bridge.py"
    report = run_bridge(ledger_path, bridge_module_path)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "ledger_sha256": report["ledger_sha256"],
                "total_entries": report["total_entries"],
                "gate_verdict_counts": report["gate_verdict_counts"],
                "admissibility_rate": report["admissibility_rate"],
                "hash_bound_count": report["hash_bound_count"],
                "out": str(out_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
