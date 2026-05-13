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


def test_candidate_to_evidence_pipeline() -> None:
    c = ClaimCard("CLM-000001", "ok", ClaimType.FACTUAL)
    b = BoundaryCard("BND-000001", ["local"], ["global"], ["local"], ["global"])
    e = EvidenceArtifact(
        "EVD-000001",
        c,
        b,
        FalsificationReport(["f1"], True),
        ReproducibilityManifest(["cmd"], "env", "a" * 64),
        True,
    )
    icu = IntelligenceClosureUnit(
        ClaimStatus.EVIDENCE, e, "a" * 64, {"patch": 1}, {"delta": 1}, revalidation_passed=True
    )
    assert e.can_be_promoted() and icu.is_intelligence_unit()


def test_evidence_without_revalidation_cannot_update_intent() -> None:
    c = ClaimCard("CLM-000002", "ok", ClaimType.FACTUAL)
    b = BoundaryCard("BND-000002", ["local"], ["global"], ["local"], ["global"])
    e = EvidenceArtifact(
        "EVD-000002",
        c,
        b,
        FalsificationReport(["f1"], True),
        ReproducibilityManifest(["cmd"], "env", "b" * 64),
        True,
    )
    icu = IntelligenceClosureUnit(
        ClaimStatus.EVIDENCE, e, "b" * 64, {"patch": 1}, {"delta": 1}, revalidation_passed=False
    )
    assert not icu.is_intelligence_unit()
