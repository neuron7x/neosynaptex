#!/usr/bin/env python3
"""Single-entrypoint deterministic pipeline for Machine Thinking artifacts."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "substrates" / "bn_syn" / "scripts"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checklist", type=Path, required=True)
    ap.add_argument("--profile", choices=["basic", "research_v1"], default="research_v1")
    ap.add_argument("--min-capital-index", type=float, default=0.9)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--out-dir", type=Path, default=Path("proof_bundle/reports"))
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_json = args.out_dir / "thinking_capital_report.json"
    artifact_json = args.out_dir / "thinking_operational_artifact.json"

    gen_cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "generate_thinking_product_report.py"),
        "--checklist",
        str(args.checklist),
        "--profile",
        args.profile,
        "--min-capital-index",
        str(args.min_capital_index),
        "--out-dir",
        str(args.out_dir),
    ]
    gen = run(gen_cmd)
    if gen.returncode != 0:
        sys.stderr.write(gen.stdout + gen.stderr)
        return gen.returncode

    comp_cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "compile_thinking_artifact.py"),
        "--report-json",
        str(report_json),
        "--out-json",
        str(artifact_json),
        "--top-k",
        str(args.top_k),
    ]
    comp = run(comp_cmd)
    if comp.returncode != 0:
        sys.stderr.write(comp.stdout + comp.stderr)
        return comp.returncode

    report = json.loads(report_json.read_text(encoding="utf-8"))
    artifact = json.loads(artifact_json.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "verdict": report.get("verdict"),
                "capital_index": report.get("capital_index"),
                "convergence_status": artifact.get("convergence", {}).get("status"),
                "report_json": str(report_json),
                "artifact_json": str(artifact_json),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
