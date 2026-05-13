from core.falsification_engine import falsification_decision, violates_physical_plausibility


def test_physics_gate_rejects_perpetual_motion_claim() -> None:
    ok, reason = falsification_decision("This design is a perpetual motion machine.", [])
    assert not ok and reason == "physical_plausibility_violation"


def test_physics_gate_rejects_over_100_percent_efficiency() -> None:
    assert violates_physical_plausibility("Our reactor reaches 120% efficiency in all regimes.")


def test_physics_gate_allows_bounded_claim() -> None:
    ok, reason = falsification_decision(
        "Local benchmark showed 87% efficiency for this setup.", ["fake citation"]
    )
    assert ok and reason == "passed"
