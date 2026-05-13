from core.eai.intelligence_cycle import (
    ClaimCard,
    ClaimStatus,
    ClaimType,
    IntelligenceClosureUnit,
    KillArtifact,
)


def test_candidate_to_killed_pipeline() -> None:
    c = ClaimCard("CLM-000001", "bad", ClaimType.CAUSAL)
    k = KillArtifact("KILL-000001", c, "failed null model", "N0", "guardrail")
    icu = IntelligenceClosureUnit(ClaimStatus.KILLED, k, "a" * 64)
    assert (
        not k.can_be_integrated()
        and k.retained
        and k.is_high_quality_kill()
        and icu.is_intelligence_unit()
    )
