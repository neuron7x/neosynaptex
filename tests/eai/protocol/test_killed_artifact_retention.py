from core.eai.intelligence_cycle import ClaimCard, ClaimType, KillArtifact


def test_killed_artifact_retention() -> None:
    c = ClaimCard("CLM-000001", "bad", ClaimType.THEORETICAL)
    k = KillArtifact("KILL-000001", c, "reason", "falsifier", "guard")
    assert k.retained and not k.can_be_integrated() and k.is_high_quality_kill()
