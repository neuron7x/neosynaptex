from core.eai.intelligence_cycle import ClaimCard, ClaimType, QuarantinedClaim


def test_quarantined_claim_cannot_update_memory() -> None:
    q = QuarantinedClaim(ClaimCard("CLM-000001", "?", ClaimType.PREDICTIVE), "untestable")
    assert not q.can_update_integration_memory()
