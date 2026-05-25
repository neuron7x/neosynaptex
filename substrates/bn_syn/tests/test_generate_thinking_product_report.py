from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_generator_writes_json_and_markdown(tmp_path: Path) -> None:
    checklist = _write(
        tmp_path / "ok.md",
        "## PRE-WORK\n- [x] ok\n## MATH\n- [x] ok\n## IMPLEMENTATION\n- [x] ok\n## VALIDATION\n- [x] ok\n## FALSIFICATION\n- [x] ok\n## ARTIFACT\n- [x] ok\n## GOVERNANCE\n- [x] ok\n## FINAL TEST\n- [x] ok\n",
    )
    out = tmp_path / "out"
    cmd = [
        sys.executable,
        "substrates/bn_syn/scripts/generate_thinking_product_report.py",
        "--checklist",
        str(checklist),
        "--profile",
        "research_v1",
        "--out-dir",
        str(out),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert proc.returncode == 0

    payload = json.loads((out / "thinking_capital_report.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS"
    assert (out / "thinking_capital_report.md").exists()


def test_generator_fail_exit_on_unresolved(tmp_path: Path) -> None:
    checklist = _write(tmp_path / "bad.md", "## VALIDATION\n- [ ] unresolved\n")
    out = tmp_path / "out2"
    cmd = [
        sys.executable,
        "substrates/bn_syn/scripts/generate_thinking_product_report.py",
        "--checklist",
        str(checklist),
        "--profile",
        "basic",
        "--min-completion",
        "1.0",
        "--out-dir",
        str(out),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert proc.returncode == 1
