from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimStatus,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    IntelligenceClosureUnit,
    ReproducibilityManifest,
)


def test_cycle_without_next_intent_delta_is_not_intelligence() -> None:
    c = ClaimCard("CLM-000001", "x", ClaimType.FACTUAL)
    b = BoundaryCard("BND-000001", ["a"], ["b"], ["t"], ["u"])
    e = EvidenceArtifact(
        "EVD-000001",
        c,
        b,
        FalsificationReport(["t"], True),
        ReproducibilityManifest(["cmd"], "env", "a" * 64),
        True,
    )
    icu = IntelligenceClosureUnit(ClaimStatus.EVIDENCE, e, "a" * 64, {"integration": 1}, None)
    assert not icu.is_intelligence_unit()
