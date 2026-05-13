from pathlib import Path

from core.eai.external_verification import compute_report_hash, run_local_command, write_report


def test_external_verification_report_shape(tmp_path: Path) -> None:
    report = run_local_command("CLM-000001", ["python", "-c", 'print("ok")'])
    assert report.status == "PASS"
    assert report.report_hash == compute_report_hash(report)
    out = tmp_path / "external_verification_report.json"
    write_report(str(out), report)
    text = out.read_text()
    assert "docker_pytest_v0" in text
    assert "local deterministic verification only" in text


def test_report_hash_stable_for_identical_output() -> None:
    r1 = run_local_command("CLM-000002", ["python", "-c", 'print("ok")'])
    r2 = run_local_command("CLM-000002", ["python", "-c", 'print("ok")'])
    assert r1.report_hash == r2.report_hash


def test_timeout_is_captured_as_fail_report() -> None:
    report = run_local_command(
        "CLM-000003", ["python", "-c", "import time; time.sleep(0.2)"], timeout_sec=0
    )
    assert report.status == "FAIL"
    assert report.report_hash == compute_report_hash(report)
