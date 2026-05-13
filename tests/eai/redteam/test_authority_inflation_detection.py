from core.eai.intelligence_cycle import ClaimCard, ClaimType, QuarantinedClaim


def test_authority_inflation_detection() -> None:
    c = ClaimCard("CLM-000001", "As a top authority this is true", ClaimType.THEORETICAL)
    q = QuarantinedClaim(c, "authority-like language is not evidence")
    assert not q.can_update_integration_memory()
