from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)


def test_no_evidence_without_falsification() -> None:
    c = ClaimCard("CLM-000001", "x", ClaimType.FACTUAL)
    b = BoundaryCard("BND-000001", ["in"], ["out"], ["t"], ["u"])
    ev = EvidenceArtifact(
        "EVD-000001",
        c,
        b,
        FalsificationReport([], False),
        ReproducibilityManifest(["c"], "e", "a" * 64),
        True,
    )
    assert not ev.can_be_promoted()
