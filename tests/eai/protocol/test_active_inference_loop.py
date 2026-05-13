from core.eai.active_inference import run_active_inference_loop


def test_active_inference_loop_stabilizes_on_clean_claims() -> None:
    result = run_active_inference_loop(
        claims=["bounded local claim", "verified under local tests"],
        contradiction_markers=["fake citation"],
    )
    assert result.stabilized
    assert result.entropy_score == 0.0
    assert all(step.predicted_status == "EVIDENCE" for step in result.steps)


def test_active_inference_loop_detects_entropy_from_invalid_claims() -> None:
    result = run_active_inference_loop(
        claims=["perpetual motion machine", "bounded local claim"],
        contradiction_markers=["fake citation"],
    )
    assert not result.stabilized
    assert result.entropy_score > 0.2
    assert result.steps[0].predicted_status == "KILLED"
