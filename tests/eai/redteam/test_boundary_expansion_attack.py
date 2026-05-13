from core.eai.intelligence_cycle import BoundaryCard


def test_boundary_expansion_attack() -> None:
    b = BoundaryCard("BND-000001", ["bench"], ["universal"], ["bench"], ["universal"])
    assert b.allows("universal") is False
