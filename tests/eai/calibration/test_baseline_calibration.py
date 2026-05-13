from pathlib import Path

from core.eai.calibration import run_calibration


def test_baseline_calibration_run() -> None:
    m = run_calibration(Path("data/eai_calibration/dataset_v0.jsonl"))
    assert m.total == 4
    assert 0.0 <= m.false_promotion_rate <= 1.0
    assert 0.0 <= m.quarantine_accuracy <= 1.0
    assert 0.0 <= m.overclaim_trap_detection <= 1.0
