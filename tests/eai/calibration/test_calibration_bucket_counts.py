from pathlib import Path

from core.eai.calibration import run_calibration


def test_calibration_reports_bucket_counts() -> None:
    metrics = run_calibration(Path("data/eai_calibration/dataset_v0.jsonl"))
    assert metrics.total == 4
    assert metrics.false_bucket_total == 1
    assert metrics.ambiguous_bucket_total == 1
    assert metrics.adversarial_bucket_total == 1
