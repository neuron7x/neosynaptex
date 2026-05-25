from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_full_pipeline_validator_to_compiler(tmp_path: Path) -> None:
    checklist = tmp_path / "checklist.md"
    checklist.write_text(
        "## PRE-WORK\n- [x] ok\n## MATH\n- [ ] unresolved\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "reports"
    gen_cmd = [
        sys.executable,
        "substrates/bn_syn/scripts/generate_thinking_product_report.py",
        "--checklist",
        str(checklist),
        "--profile",
        "basic",
        "--min-completion",
        "0.5",
        "--out-dir",
        str(out_dir),
    ]
    gen = subprocess.run(gen_cmd, check=False, capture_output=True, text=True)
    assert gen.returncode == 0

    report_json = out_dir / "thinking_capital_report.json"
    assert report_json.exists()

    compile_cmd = [
        sys.executable,
        "substrates/bn_syn/scripts/compile_thinking_artifact.py",
        "--report-json",
        str(report_json),
        "--out-json",
        str(out_dir / "thinking_operational_artifact.json"),
        "--top-k",
        "3",
    ]
    comp = subprocess.run(compile_cmd, check=False, capture_output=True, text=True)
    assert comp.returncode == 0

    artifact = json.loads((out_dir / "thinking_operational_artifact.json").read_text(encoding="utf-8"))
    assert artifact["source_verdict"] == "PASS"
    assert "convergence" in artifact
