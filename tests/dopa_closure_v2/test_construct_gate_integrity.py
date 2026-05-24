from core.eai.dopa_construct_gate import validate_construct_context


class FakeContext:
    dnca_substrate_check = True


def test_context_contamination_blocked() -> None:
    verdict = validate_construct_context(FakeContext())  # type: ignore[arg-type]
    assert verdict.admissible is False
    assert verdict.verdict == "INSTRUMENT_INADMISSIBLE"
