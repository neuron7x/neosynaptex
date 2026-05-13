from core.eai.intelligence_cycle import (
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)


def test_no_evidence_without_boundary() -> None:
    claim = ClaimCard("CLM-000001", "x", ClaimType.FACTUAL)
    ev = EvidenceArtifact(
        "EVD-000001",
        claim,
        None,
        FalsificationReport(["t"], True),
        ReproducibilityManifest(["cmd"], "env", "a" * 64),
        True,
    )
    assert ev.can_be_promoted() is False
