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


def _evidence() -> EvidenceArtifact:
    return EvidenceArtifact(
        artifact_id="EVD-ICU-1",
        claim=ClaimCard("CLM-ICU-1", "bounded validated claim", ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-ICU-1", ["local"], ["global"], ["local"], ["global"]),
        falsification_report=FalsificationReport(["falsify"], True),
        reproducibility=ReproducibilityManifest(["cmd"], "env", "a" * 64),
        integration_permission=True,
    )


def test_icu_policy_requires_intent_shift_and_guardrail_update() -> None:
    icu = IntelligenceClosureUnit(
        status=ClaimStatus.EVIDENCE,
        artifact=_evidence(),
        retention_hash="a" * 64,
        integration_patch={"patch": 1, "guardrail_update": {"id": "GRD-1"}},
        next_intent_delta={"delta": 1},
        revalidation_passed=True,
    )
    assert icu.satisfies_icu_policy()


def test_icu_policy_rejects_missing_anti_regression_control() -> None:
    icu = IntelligenceClosureUnit(
        status=ClaimStatus.EVIDENCE,
        artifact=_evidence(),
        retention_hash="a" * 64,
        integration_patch={"patch": 1},
        next_intent_delta={"delta": 1},
        revalidation_passed=True,
    )
    assert not icu.satisfies_icu_policy()


def test_icu_requires_sha256_retention_hash_for_all_statuses() -> None:
    ev = IntelligenceClosureUnit(
        status=ClaimStatus.EVIDENCE,
        artifact=_evidence(),
        retention_hash="bad",
        integration_patch={"patch": 1, "guardrail_update": {"id": "GRD-1"}},
        next_intent_delta={"delta": 1},
        revalidation_passed=True,
    )
    assert not ev.is_intelligence_unit()
