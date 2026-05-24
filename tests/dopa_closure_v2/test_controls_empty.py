from core.eai.dopa_controls import run_controls


def test_controls_empty_batch_fail_closed() -> None:
    out = run_controls([], [], seed=7)
    assert out.passed is False
