from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass

from core.artifact_ledger import ArtifactLedger, LedgerEntry
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimStatus,
    EvidenceArtifact,
    FalsificationReport,
    IntelligenceClosureUnit,
    KillArtifact,
    QuarantinedClaim,
    ReproducibilityManifest,
)
from core.falsification_engine import falsification_decision
from core.iev_gate import decide_intent_update
from core.integration_memory import IntegrationMemory

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _safe_retention_hash(user_hash: str, *, status: str, claim_id: str, claim_text: str) -> str:
    """Return ``user_hash`` if it is a valid SHA-256 hex digest, else a
    deterministic fallback for non-EVIDENCE policy records.

    The artifact ledger only accepts lowercase SHA-256 hex; a malformed
    user-supplied hash from upstream must not turn a *policy* decision
    (QUARANTINED / KILLED) into a *runtime crash*. For non-EVIDENCE
    statuses the fallback is computed from ``status:claim_id:claim_text``
    so the entry remains audit-stable and reproducible.
    """
    if _SHA256_HEX.fullmatch(user_hash or ""):
        return user_hash
    digest = hashlib.sha256(f"{status}:{claim_id}:{claim_text}".encode())
    return digest.hexdigest()


@dataclass
class CycleTelemetry:
    elapsed_ms: float
    path: list[str]


@dataclass
class EngineOutcome:
    status: ClaimStatus
    icu: IntelligenceClosureUnit
    ledger_entry: LedgerEntry
    decision_reason: str
    failed_stage: str | None
    telemetry: CycleTelemetry


class EAIEngine:
    """Deterministic orchestration over falsification -> IEV gate -> ledger -> memory."""

    def __init__(
        self, *, ledger: ArtifactLedger | None = None, memory: IntegrationMemory | None = None
    ) -> None:
        self.ledger = ledger or ArtifactLedger()
        self.memory = memory or IntegrationMemory()

    def run_candidate(
        self,
        *,
        claim: ClaimCard,
        boundary: BoundaryCard,
        contradiction_markers: list[str],
        reproducibility: ReproducibilityManifest,
        retention_hash: str,
        revalidation_passed: bool,
        integration_patch: dict[str, object] | None,
        next_intent_delta: dict[str, object] | None,
    ) -> EngineOutcome:
        t0 = time.perf_counter()
        path: list[str] = ["falsification"]
        passed, falsification_reason = falsification_decision(
            claim.claim_text, contradiction_markers
        )
        if not passed:
            status = ClaimStatus.KILLED
            safe_hash = _safe_retention_hash(
                retention_hash,
                status=status.value,
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
            )
            kill_artifact = KillArtifact(
                artifact_id=f"KILL-{claim.claim_id}",
                claim=claim,
                kill_reason="falsification_failed",
                failed_test="gate_falsification",
                future_guardrail="block_repromotion",
            )
            icu = IntelligenceClosureUnit(
                status=status, artifact=kill_artifact, retention_hash=safe_hash
            )
            entry = self.ledger.append(
                f"KILL-{claim.claim_id}", claim.claim_id, status.value, safe_hash
            )
            return EngineOutcome(
                status=status,
                icu=icu,
                ledger_entry=entry,
                decision_reason=falsification_reason,
                failed_stage="falsification",
                telemetry=CycleTelemetry(elapsed_ms=(time.perf_counter() - t0) * 1000.0, path=path),
            )

        evidence = EvidenceArtifact(
            artifact_id=f"EVD-{claim.claim_id}",
            claim=claim,
            boundary=boundary,
            falsification_report=FalsificationReport(["gate_falsification"], True),
            reproducibility=reproducibility,
            integration_permission=True,
        )
        path.append("iev_gate")
        decision = decide_intent_update(
            evidence, retention_hash=retention_hash, revalidation_passed=revalidation_passed
        )
        status = ClaimStatus(decision)
        safe_hash = _safe_retention_hash(
            retention_hash,
            status=status.value,
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
        )

        # Three-way fan-out: EVIDENCE keeps the artifact as-is; KILLED
        # synthesizes a KillArtifact (decide_intent_update can return
        # KILLED when can_be_promoted() is False, e.g. missing boundary
        # or invalid reproducibility hash); QUARANTINED wraps the
        # claim with the gate reason.
        outcome_artifact: EvidenceArtifact | KillArtifact | QuarantinedClaim
        artifact_id: str
        decision_reason: str
        if status is ClaimStatus.EVIDENCE:
            outcome_artifact = evidence
            artifact_id = evidence.artifact_id
            decision_reason = "promotion_allowed"
        elif status is ClaimStatus.KILLED:
            outcome_artifact = KillArtifact(
                artifact_id=f"KILL-{claim.claim_id}",
                claim=claim,
                kill_reason="iev_gate_promotion_denied",
                failed_test="gate_iev_can_be_promoted",
                future_guardrail="block_repromotion_until_boundary_repaired",
            )
            artifact_id = outcome_artifact.artifact_id
            decision_reason = "iev_gate_promotion_denied"
        else:  # QUARANTINED
            outcome_artifact = QuarantinedClaim(claim=claim, quarantine_reason="gate_not_satisfied")
            artifact_id = evidence.artifact_id
            decision_reason = (
                "revalidation_failed_or_hash_invalid"
                if not revalidation_passed
                else "gate_quarantine"
            )

        icu = IntelligenceClosureUnit(
            status=status,
            artifact=outcome_artifact,
            retention_hash=safe_hash,
            integration_patch=integration_patch if status is ClaimStatus.EVIDENCE else None,
            next_intent_delta=next_intent_delta if status is ClaimStatus.EVIDENCE else None,
            revalidation_passed=revalidation_passed,
        )
        if status is ClaimStatus.EVIDENCE and integration_patch is not None:
            path.append("integration_memory")
            self.memory.apply_patch(
                claim_id=claim.claim_id, status=status.value, patch=integration_patch
            )

        path.append("artifact_ledger")
        entry = self.ledger.append(artifact_id, claim.claim_id, status.value, safe_hash)
        return EngineOutcome(
            status=status,
            icu=icu,
            ledger_entry=entry,
            decision_reason=decision_reason,
            failed_stage=None if status is ClaimStatus.EVIDENCE else "iev_gate",
            telemetry=CycleTelemetry(elapsed_ms=(time.perf_counter() - t0) * 1000.0, path=path),
        )
