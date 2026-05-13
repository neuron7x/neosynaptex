from pathlib import Path

from core.eai.calibration import contradiction_decision, run_contradiction_calibration


def test_context_contradiction_traps_block_evidence() -> None:
    m = run_contradiction_calibration(Path("data/eai_calibration/context_contradiction_v0a.jsonl"))
    assert m.false_promotion_rate == 0.0


def test_direct_contradiction_is_not_evidence() -> None:
    assert contradiction_decision("correlation only", "causal mechanism confirmed") != "EVIDENCE"
