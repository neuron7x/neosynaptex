from pathlib import Path

from tools.eai.run_calibration import build_report


def test_calibration_report_has_utc_and_dataset_hash() -> None:
    report = build_report(Path("data/eai_calibration/dataset_v0.jsonl"))
    assert report["timestamp_utc"].endswith("+00:00")
    assert len(report["dataset_sha256"]) == 64
    assert report["artifact_owner"] == "eai-research-track"
    metrics = report["metrics"]
    assert metrics["total"] >= 1
