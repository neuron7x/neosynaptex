from core.eai.intelligence_cycle import BoundaryCard


def test_no_claim_expansion_beyond_boundary() -> None:
    b = BoundaryCard("BND-000001", ["local"], ["universal"], ["local"], ["universal"])
    assert b.allows("universal") is False
