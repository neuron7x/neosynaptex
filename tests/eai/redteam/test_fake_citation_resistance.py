from core.eai.intelligence_cycle import ClaimCard, ClaimType, QuarantinedClaim


def test_fake_citation_resistance() -> None:
    c = ClaimCard("CLM-000001", "fake citation", ClaimType.FACTUAL)
    q = QuarantinedClaim(c, "no independent source")
    assert q.integration_permission is False
