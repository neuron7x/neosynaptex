from core.eai.guardrail_registry import GuardrailRegistry
from core.eai.intelligence_cycle import (
    ClaimCard,
    ClaimStatus,
    ClaimType,
    IntelligenceClosureUnit,
    KillArtifact,
)


def test_killed_future_guardrail_enters_guardrail_registry_not_integration_memory() -> None:
    claim = ClaimCard("CLM-300001", "proves universal law", ClaimType.THEORETICAL)
    killed = KillArtifact(
        artifact_id="KILL-300001",
        claim=claim,
        kill_reason="boundary expansion",
        failed_test="boundary_lock",
        future_guardrail="Do not promote universal claims from local tests.",
    )

    icu = IntelligenceClosureUnit(
        status=ClaimStatus.KILLED, artifact=killed, retention_hash="a" * 64
    )
    assert icu.integration_patch is None

    registry = GuardrailRegistry()
    patch = registry.register_from_kill(killed, retention_hash="a" * 64, domain="research")
    assert patch.source_kill_artifact_id == "KILL-300001"
    assert (
        registry.evaluate_candidate("this proves universal law", ClaimType.THEORETICAL) == "KILLED"
    )
    assert icu.integration_patch is None
