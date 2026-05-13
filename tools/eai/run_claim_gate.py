from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.eai.engine import EAIEngine
from core.eai.intelligence_cycle import BoundaryCard, ClaimCard, ClaimType, ReproducibilityManifest


def run_claim_gate(
    *,
    claim_text: str,
    context: str,
    retention_hash: str,
    revalidation_passed: bool,
    kill_switch: bool = False,
) -> dict[str, Any]:
    claim = ClaimCard("CLM-CLI-1", claim_text, ClaimType.FACTUAL)
    boundary = BoundaryCard("BND-CLI-1", [context], ["global"], [context], ["global"])
    reproducibility = ReproducibilityManifest(["run_claim_gate"], "local-cli", retention_hash)

    engine = EAIEngine()
    outcome = engine.run_candidate(
        claim=claim,
        boundary=boundary,
        contradiction_markers=[claim_text] if kill_switch else [],
        reproducibility=reproducibility,
        retention_hash=retention_hash,
        revalidation_passed=revalidation_passed,
        integration_patch={"guardrail_update": {"id": "CLI-GR-1"}},
        next_intent_delta={"delta": 1},
    )

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": outcome.status.value,
        "claim": asdict(claim),
        "artifact_id": outcome.ledger_entry.artifact_id,
        "artifact_owner": "eai-research-track",
        "decision_reason": outcome.decision_reason,
        "failed_stage": outcome.failed_stage,
        "telemetry": {"elapsed_ms": outcome.telemetry.elapsed_ms, "path": outcome.telemetry.path},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a one-command EAI claim gate decision.")
    parser.add_argument("--claim", required=True)
    parser.add_argument("--context", default="local")
    parser.add_argument("--retention-hash", default="a" * 64)
    parser.add_argument("--revalidation-passed", action="store_true")
    parser.add_argument("--out", default="artifacts/repro/claim_gate_report.json")
    parser.add_argument("--kill-switch", action="store_true")
    args = parser.parse_args()

    report = run_claim_gate(
        claim_text=args.claim,
        context=args.context,
        retention_hash=args.retention_hash,
        revalidation_passed=args.revalidation_passed,
        kill_switch=args.kill_switch,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
