from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_compile_divergence_convergence(tmp_path: Path) -> None:
    src = tmp_path / "report.json"
    src.write_text(
        json.dumps(
            {
                "verdict": "FAIL",
                "capital_index": 0.3,
                "unresolved_by_section": {"VALIDATION": 2, "ARTIFACT": 1},
                "action_plan": {
                    "VALIDATION": ["Run adversarial tests", "Add property tests"],
                    "ARTIFACT": ["Add one-command run example"],
                },
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "artifact.json"
    cmd = [
        sys.executable,
        "substrates/bn_syn/scripts/compile_thinking_artifact.py",
        "--report-json",
        str(src),
        "--out-json",
        str(out),
        "--top-k",
        "2",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["divergence"]
    assert payload["convergence"]["task_count"] == 2


def test_compile_fallback_action_when_plan_missing(tmp_path: Path) -> None:
    src = tmp_path / "report_missing_plan.json"
    src.write_text(
        json.dumps({"verdict": "FAIL", "capital_index": 0.1, "unresolved_by_section": {"MATH": 1}, "action_plan": {}}),
        encoding="utf-8",
    )
    out = tmp_path / "artifact_missing_plan.json"
    cmd = [
        sys.executable,
        "substrates/bn_syn/scripts/compile_thinking_artifact.py",
        "--report-json",
        str(src),
        "--out-json",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["divergence"][0]["action"].startswith("Resolve unresolved items")


def test_compile_fails_on_missing_contract_keys(tmp_path: Path) -> None:
    src = tmp_path / "bad_report.json"
    src.write_text(json.dumps({"verdict": "FAIL"}), encoding="utf-8")
    out = tmp_path / "artifact_bad.json"
    cmd = [
        sys.executable,
        "substrates/bn_syn/scripts/compile_thinking_artifact.py",
        "--report-json",
        str(src),
        "--out-json",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode != 0
    assert "missing required keys" in (proc.stderr + proc.stdout)
