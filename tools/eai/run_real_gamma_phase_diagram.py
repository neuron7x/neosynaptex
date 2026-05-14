"""Real-ledger phase-diagram runner: 490 cells over real γ-ledger entries.

CONTRACT:
    pre:  γ-ledger path (read-only); output paths derived from CLI.
    post: writes three byte-deterministic artifacts (JSON + CSV + MD).
          Two consecutive runs are byte-identical.
    fail: exit 0 on PHASE_REGION_FOUND; 33 on NO_SEPARABLE_REGION_FOUND
          (warning, build passes); 22 on REGRESSION_REGION_FOUND or
          INVALID_EXPERIMENT (CI blocks); 1 reserved for uncaught
          Python exception (CI blocks).
    inv:  γ-ledger is READ-ONLY. PR #193 gamma_bridge module is NOT
          modified. PR #195/#196 anchors are NOT modified. Production
          engine modules (core/eai/engine.py, core/iev_gate.py) are
          NOT modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.eai.gamma_bridge import load_ledger  # noqa: E402
from core.eai.real_gamma_phase_diagram import (  # noqa: E402
    RealCellRecord,
    classify_region,
    evaluate_cell,
    generate_grid,
    summarize_regions,
)

_SCHEMA_VERSION = "EAI-REAL-GAMMA-PHASE-DIAGRAM-v1"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_to_dict(r: RealCellRecord) -> dict[str, Any]:
    return {
        "cell_id": r.cell_id,
        "axes": {
            "ledger_key": r.axes.ledger_key,
            "probe_count_used": r.axes.probe_count_used,
            "evidence_path_count": r.axes.evidence_path_count,
        },
        "ledger_meta": {
            "substrate": r.ledger_substrate,
            "status": r.ledger_status,
            "evidence_tier": r.ledger_evidence_tier,
            "hash_bound": r.hash_bound,
        },
        "binary": {"verdict": r.binary_verdict, "reason": r.binary_reason},
        "graded": {
            "verdict": r.graded_verdict,
            "reason": r.graded_reason,
            "conflict_strength": r.conflict_strength,
            "required_paths": r.required_paths,
            "available_paths": r.available_paths,
        },
        "useful": r.useful,
        "regression": r.regression,
        "null": r.null_cell,
        "region": classify_region(r),
    }


def _records_to_csv(records: list[RealCellRecord]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "cell_id",
        "ledger_key",
        "probe_count_used",
        "evidence_path_count",
        "ledger_substrate",
        "ledger_status",
        "ledger_evidence_tier",
        "hash_bound",
        "binary_verdict",
        "binary_reason",
        "graded_verdict",
        "graded_reason",
        "conflict_strength",
        "required_paths",
        "available_paths",
        "useful",
        "regression",
        "null",
        "region",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in records:
        writer.writerow(
            {
                "cell_id": r.cell_id,
                "ledger_key": r.axes.ledger_key,
                "probe_count_used": r.axes.probe_count_used,
                "evidence_path_count": r.axes.evidence_path_count,
                "ledger_substrate": r.ledger_substrate,
                "ledger_status": r.ledger_status,
                "ledger_evidence_tier": r.ledger_evidence_tier,
                "hash_bound": r.hash_bound,
                "binary_verdict": r.binary_verdict,
                "binary_reason": r.binary_reason,
                "graded_verdict": r.graded_verdict,
                "graded_reason": r.graded_reason,
                "conflict_strength": r.conflict_strength,
                "required_paths": r.required_paths,
                "available_paths": r.available_paths,
                "useful": r.useful,
                "regression": r.regression,
                "null": r.null_cell,
                "region": classify_region(r),
            }
        )
    return buf.getvalue()


def _summary_markdown(summary: dict[str, Any], ledger_sha: str) -> str:
    lines: list[str] = []
    lines.append("# EAI Real-Data γ-Ledger Phase Diagram v1 — Summary\n")
    lines.append(f"- **schema_version**: `{_SCHEMA_VERSION}`")
    lines.append(f"- **ledger_sha256**: `{ledger_sha}`")
    lines.append(f"- **total_cells**: `{summary['total_cells']}`")
    lines.append(f"- **verdict**: **`{summary['verdict']}`**")
    lines.append(f"- **verdict_reason**: {summary['verdict_reason']}")
    lines.append("")
    lines.append("## Region totals (global)\n")
    lines.append("| Region | Count |")
    lines.append("|---|---:|")
    lines.append(f"| useful | {summary['useful_global']} |")
    lines.append(f"| regression | {summary['regression_global']} |")
    lines.append(f"| null | {summary['null_global']} |")
    lines.append("")
    lines.append("## Zone breakdown (evidence_tier / ledger_status)\n")
    lines.append("| zone | useful | regression | null |")
    lines.append("|---|---:|---:|---:|")
    for zk, counts in summary["zone_breakdown"].items():
        lines.append(f"| `{zk}` | {counts['useful']} | {counts['regression']} | {counts['null']} |")
    lines.append("")
    lines.append("## Claim boundary\n")
    lines.append(
        "> EAI Real-Data γ-Ledger Phase Diagram v1 reports binary-vs-graded\n"
        "> gate behaviour across 10 real γ-ledger entries × 7 probe-count\n"
        "> values × 7 evidence-path-count values, under a fixed canonical\n"
        "> probe pool. Diagnostic only. γ-ledger read-only. No production\n"
        "> engine modified."
    )
    return "\n".join(lines) + "\n"


def run_real_phase_diagram(
    ledger_path: Path,
) -> tuple[list[RealCellRecord], dict[str, Any], dict[str, dict[str, Any]], str]:
    version, entries = load_ledger(ledger_path)
    cells = generate_grid(list(entries.keys()))
    records: list[RealCellRecord] = []
    for cell in cells:
        entry = entries[cell.ledger_key]
        records.append(evaluate_cell(cell, entry, ledger_version=version))
    summary = summarize_regions(records)
    return records, summary, entries, version


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministic real-data phase-diagram runner: binary vs graded "
            "gate on 10 real γ-ledger entries × 7 probe-count × 7 evidence-"
            "path-count = 490 cells."
        ),
    )
    parser.add_argument("--ledger", default="evidence/gamma_ledger.json")
    parser.add_argument(
        "--out-json",
        default="artifacts/eai/phase_diagrams/real_gamma_phase_diagram_v1.json",
    )
    parser.add_argument(
        "--out-csv",
        default="artifacts/eai/phase_diagrams/real_gamma_phase_diagram_v1.csv",
    )
    parser.add_argument(
        "--out-summary",
        default="artifacts/eai/phase_diagrams/real_gamma_phase_diagram_summary.md",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    records, summary, _entries, version = run_real_phase_diagram(ledger_path)

    ledger_sha = _file_sha256(ledger_path)
    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_summary)
    # Codex P2 fix: create parent directories for ALL output paths,
    # not just out_json. Callers using custom --out-csv / --out-summary
    # with non-existent parent directories would otherwise crash with
    # FileNotFoundError (exit 1 = Python uncaught-exception default
    # = CI blocks for the wrong reason).
    for path in (out_json, out_csv, out_md):
        path.parent.mkdir(parents=True, exist_ok=True)

    full_report: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "ledger_path": str(ledger_path),
        "ledger_version": version,
        "ledger_sha256": ledger_sha,
        "grid_cells": len(records),
        "summary": summary,
        "cells": [_record_to_dict(r) for r in records],
    }
    out_json.write_text(
        json.dumps(full_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_csv.write_text(_records_to_csv(records), encoding="utf-8")
    out_md.write_text(_summary_markdown(summary, ledger_sha), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": summary["verdict"],
                "verdict_reason": summary["verdict_reason"],
                "ledger_sha256": ledger_sha,
                "total_cells": len(records),
                "useful": summary["useful_global"],
                "regression": summary["regression_global"],
                "null": summary["null_global"],
                "out_json": str(out_json),
                "out_csv": str(out_csv),
                "out_summary": str(out_md),
            },
            sort_keys=True,
        )
    )

    verdict = summary["verdict"]
    if verdict == "PHASE_REGION_FOUND":
        return 0
    if verdict in {"REGRESSION_REGION_FOUND", "INVALID_EXPERIMENT"}:
        return 22
    return 33  # NO_SEPARABLE_REGION_FOUND


if __name__ == "__main__":
    raise SystemExit(main())
