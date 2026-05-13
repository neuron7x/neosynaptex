from __future__ import annotations

from dataclasses import dataclass

from core.eai.intelligence_cycle import ClaimCard, ClaimType, KillArtifact
from core.falsification_engine import falsification_decision


@dataclass
class AnagulationResult:
    status: str
    reason: str
    kill_artifact: KillArtifact | None


def anagulate_claim(
    *,
    claim_id: str,
    claim_text: str,
    contradiction_markers: list[str],
    reproducibility_ok: bool,
) -> AnagulationResult:
    passed, reason = falsification_decision(claim_text, contradiction_markers)

    if not passed:
        kill = KillArtifact(
            artifact_id=f"KILL-{claim_id}",
            claim=ClaimCard(claim_id, claim_text, ClaimType.FACTUAL),
            kill_reason="falsification_failed",
            failed_test=reason,
            future_guardrail=f"Block claims matching: {claim_text[:80]}",
        )
        return AnagulationResult(status="KILLED", reason=reason, kill_artifact=kill)

    if not reproducibility_ok:
        kill = KillArtifact(
            artifact_id=f"KILL-{claim_id}",
            claim=ClaimCard(claim_id, claim_text, ClaimType.FACTUAL),
            kill_reason="reproducibility_missing",
            failed_test="artifact_hash_missing_or_invalid",
            future_guardrail="Require valid SHA-256 reproducibility hash",
        )
        return AnagulationResult(
            status="KILLED", reason="reproducibility_failed", kill_artifact=kill
        )

    return AnagulationResult(status="EVIDENCE", reason="passed", kill_artifact=None)
