from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUNNER = Path("substrates/bn_syn/scripts/run_thinking_pipeline.py").resolve()


def _write_valid_checklist(path: Path) -> None:
    path.write_text(
        "## PRE-WORK\n- [x] ok\n"
        "## MATH\n- [x] ok\n"
        "## IMPLEMENTATION\n- [x] ok\n"
        "## VALIDATION\n- [x] ok\n"
        "## FALSIFICATION\n- [x] ok\n"
        "## ARTIFACT\n- [x] ok\n"
        "## GOVERNANCE\n- [x] ok\n"
        "## FINAL TEST\n- [x] ok\n",
        encoding="utf-8",
    )


def test_run_pipeline_pass(tmp_path: Path) -> None:
    checklist = tmp_path / "ok.md"
    _write_valid_checklist(checklist)
    out = tmp_path / "out"
    cmd = [
        sys.executable,
        str(RUNNER),
        "--checklist",
        str(checklist),
        "--profile",
        "research_v1",
        "--out-dir",
        str(out),
    ]

    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["verdict"] == "PASS"
    assert (out / "thinking_capital_report.json").exists()
    assert (out / "thinking_operational_artifact.json").exists()


def test_run_pipeline_passes_from_non_repo_cwd(tmp_path: Path) -> None:
    checklist = tmp_path / "ok.md"
    _write_valid_checklist(checklist)
    out = tmp_path / "out"
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    cmd = [
        sys.executable,
        str(RUNNER),
        "--checklist",
        str(checklist),
        "--profile",
        "research_v1",
        "--out-dir",
        str(out),
    ]

    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)

    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["verdict"] == "PASS"
    assert (out / "thinking_capital_report.json").exists()
    assert (out / "thinking_operational_artifact.json").exists()


def test_run_pipeline_fails_closed_on_unresolved_checklist(tmp_path: Path) -> None:
    checklist = tmp_path / "bad.md"
    checklist.write_text("## PRE-WORK\n- [ ] unresolved\n", encoding="utf-8")
    out = tmp_path / "out"
    cmd = [
        sys.executable,
        str(RUNNER),
        "--checklist",
        str(checklist),
        "--profile",
        "research_v1",
        "--out-dir",
        str(out),
    ]

    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert proc.returncode != 0
    assert "verdict" in proc.stderr or "structure_errors" in proc.stderr
