import pytest

from core.artifact_ledger import ArtifactLedger
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)
from core.iev_gate import decide_intent_update
from core.integration_memory import IntegrationMemory


def _artifact() -> EvidenceArtifact:
    return EvidenceArtifact(
        artifact_id="EVD-GATE-1",
        claim=ClaimCard("CLM-GATE-1", "local validated claim", ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-1", ["local"], ["global"], ["local"], ["global"]),
        falsification_report=FalsificationReport(["falsify"], True),
        reproducibility=ReproducibilityManifest(["cmd"], "env", "a" * 64),
        integration_permission=True,
    )


def test_iev_gate_quarantines_without_revalidation() -> None:
    status = decide_intent_update(_artifact(), retention_hash="a" * 64, revalidation_passed=False)
    assert status == "QUARANTINED"


def test_iev_gate_allows_memory_patch_on_evidence() -> None:
    artifact = _artifact()
    status = decide_intent_update(artifact, retention_hash="a" * 64, revalidation_passed=True)
    memory = IntegrationMemory()
    ledger = ArtifactLedger()
    assert status == "EVIDENCE"
    assert memory.apply_patch(
        claim_id=artifact.claim.claim_id, status=status, patch={"accepted": True}
    )
    assert memory.get(artifact.claim.claim_id) == {"accepted": True}
    entry = ledger.append(artifact.artifact_id, artifact.claim.claim_id, status, "a" * 64)
    assert entry.status == "EVIDENCE" and len(ledger.entries) == 1


def test_iev_gate_quarantines_invalid_retention_hash() -> None:
    status = decide_intent_update(_artifact(), retention_hash="BAD", revalidation_passed=True)
    assert status == "QUARANTINED"


def test_iev_gate_emergency_exit_forces_quarantine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAI_EMERGENCY_EXIT", "true")
    status = decide_intent_update(_artifact(), retention_hash="a" * 64, revalidation_passed=True)
    assert status == "QUARANTINED"
