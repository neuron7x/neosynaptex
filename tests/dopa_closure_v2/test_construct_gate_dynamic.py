from core.eai.dopa_construct_gate import ConstructContext, validate_construct_context


def test_construct_gate_accepts_callable_checks() -> None:
    ctx = ConstructContext(
        lambda: True,
        lambda: True,
        lambda: False,
        lambda: False,
        lambda: True,
        lambda: True,
    )
    v = validate_construct_context(ctx)
    assert v.admissible is True
