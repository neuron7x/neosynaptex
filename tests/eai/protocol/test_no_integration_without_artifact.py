from core.eai.intelligence_cycle import ClaimStatus, IntelligenceClosureUnit


def test_no_integration_without_artifact() -> None:
    icu = IntelligenceClosureUnit(ClaimStatus.EVIDENCE, None, "a" * 64, {}, {"next": 1})
    assert not icu.is_intelligence_unit()
