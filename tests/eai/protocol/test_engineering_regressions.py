import pytest

from core.artifact_ledger import ArtifactLedger
from core.eai.active_inference import run_active_inference_loop
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)


def test_evidence_rejects_boundary_with_invalid_scope_overlap() -> None:
    e = EvidenceArtifact(
        artifact_id="EVD-X",
        claim=ClaimCard("CLM-X", "x", ClaimType.FACTUAL),
        boundary=BoundaryCard("B", ["global"], ["global"], ["global"], []),
        falsification_report=FalsificationReport(["t"], True),
        reproducibility=ReproducibilityManifest(["cmd"], "env", "a" * 64),
    )
    assert not e.can_be_promoted()


def test_artifact_ledger_rejects_invalid_retention_hash() -> None:
    ledger = ArtifactLedger()
    with pytest.raises(ValueError):
        ledger.append("A", "C", "EVIDENCE", "bad-hash")


def test_active_inference_threshold_parameter_controls_stability() -> None:
    claims = ["perpetual motion machine", "bounded claim"]
    result = run_active_inference_loop(claims, [], stabilization_threshold=0.6)
    assert result.stabilized
