from core.eai.intelligence_cycle import (
    ClaimCard,
    ClaimStatus,
    ClaimType,
    IntelligenceClosureUnit,
    QuarantinedClaim,
)


def test_candidate_to_quarantine_pipeline() -> None:
    q = QuarantinedClaim(
        ClaimCard("CLM-000001", "untestable", ClaimType.THEORETICAL), "insufficient testability"
    )
    icu = IntelligenceClosureUnit(ClaimStatus.QUARANTINED, q, "a" * 64)
    assert (
        (not q.integration_permission)
        and (not q.can_update_integration_memory())
        and icu.is_intelligence_unit()
    )
