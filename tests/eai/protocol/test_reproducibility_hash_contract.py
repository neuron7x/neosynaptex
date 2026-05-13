from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)


def test_evidence_rejects_non_sha256_repro_hash() -> None:
    artifact = EvidenceArtifact(
        artifact_id="EVD-REPRO-1",
        claim=ClaimCard("CLM-REPRO-1", "validated claim", ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-1", ["local"], ["global"], ["local"], ["global"]),
        falsification_report=FalsificationReport(["falsify"], True),
        reproducibility=ReproducibilityManifest(["cmd"], "env", "not-a-sha256"),
        integration_permission=True,
    )
    assert not artifact.can_be_promoted()


def test_evidence_accepts_valid_sha256_repro_hash() -> None:
    artifact = EvidenceArtifact(
        artifact_id="EVD-REPRO-2",
        claim=ClaimCard("CLM-REPRO-2", "validated claim", ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-1", ["local"], ["global"], ["local"], ["global"]),
        falsification_report=FalsificationReport(["falsify"], True),
        reproducibility=ReproducibilityManifest(["cmd"], "env", "a" * 64),
        integration_permission=True,
    )
    assert artifact.can_be_promoted()
