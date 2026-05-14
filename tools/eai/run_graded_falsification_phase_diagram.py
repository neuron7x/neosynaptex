"""Deterministic phase-diagram runner: binary vs graded gate over a 6-axis grid.

CONTRACT:
    pre:  output paths (json, csv, summary md); all derived from CLI.
    post: writes three byte-deterministic artifacts:
            - JSON (full per-cell records + summary)
            - CSV (per-cell flattened)
            - Markdown summary (per-class metrics + verdict)
          Two consecutive runs produce byte-identical outputs.
    fail: exit 22 on REGRESSION_REGION_FOUND or INVALID_EXPERIMENT
          (build blocks); exit 33 on NO_SEPARABLE_REGION_FOUND
          (warning, build passes); exit 0 on PHASE_REGION_FOUND.
          Exit 1 reserved for Python uncaught-exception default
          (CI blocks).
    inv:  production engine modules are read-only; this tool never
          imports from core.eai.engine or core.iev_gate; the diagnostic
          is built on the isolated graded_gate + graded_phase_diagram
          modules.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.eai.graded_phase_diagram import (  # noqa: E402
    CellRecord,
    classify_region,
    compute_region_metrics,
    evaluate_cell,
    generate_grid,
    summarize_regions,
)

_SCHEMA_VERSION = "EAI-PHASE-DIAGRAM-v1"


def _record_to_dict(r: CellRecord) -> dict[str, Any]:
    return {
        "cell_id": r.cell_id,
        "axes": {
            "conflict_marker_count": r.axes.conflict_marker_count,
            "evidence_path_count": r.axes.evidence_path_count,
            "claim_class": r.axes.claim_class,
            "contradiction_density": r.axes.contradiction_density,
            "revalidation_state": r.axes.revalidation_state,
            "boundary_state": r.axes.boundary_state,
        },
        "binary": {"verdict": r.binary_verdict, "reason": r.binary_reason},
        "graded": {
            "verdict": r.graded_verdict,
            "reason": r.graded_reason,
            "conflict_strength": r.conflict_strength,
            "required_paths": r.required_paths,
            "available_paths": r.available_paths,
        },
        "expected_status": r.expected_status,
        "graded_reduced_false_promotion": r.graded_reduced_false_promotion,
        "graded_killed_true_evidence": r.graded_killed_true_evidence,
        "graded_quarantined_ambiguous": r.graded_quarantined_ambiguous,
        "region": classify_region(r),
    }


def _records_to_csv(records: list[CellRecord]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "cell_id",
        "conflict_marker_count",
        "evidence_path_count",
        "claim_class",
        "contradiction_density",
        "revalidation_state",
        "boundary_state",
        "expected_status",
        "binary_verdict",
        "binary_reason",
        "graded_verdict",
        "graded_reason",
        "conflict_strength",
        "required_paths",
        "available_paths",
        "graded_reduced_false_promotion",
        "graded_killed_true_evidence",
        "graded_quarantined_ambiguous",
        "region",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in records:
        writer.writerow(
            {
                "cell_id": r.cell_id,
                "conflict_marker_count": r.axes.conflict_marker_count,
                "evidence_path_count": r.axes.evidence_path_count,
                "claim_class": r.axes.claim_class,
                "contradiction_density": r.axes.contradiction_density,
                "revalidation_state": r.axes.revalidation_state,
                "boundary_state": r.axes.boundary_state,
                "expected_status": r.expected_status,
                "binary_verdict": r.binary_verdict,
                "binary_reason": r.binary_reason,
                "graded_verdict": r.graded_verdict,
                "graded_reason": r.graded_reason,
                "conflict_strength": r.conflict_strength,
                "required_paths": r.required_paths,
                "available_paths": r.available_paths,
                "graded_reduced_false_promotion": r.graded_reduced_false_promotion,
                "graded_killed_true_evidence": r.graded_killed_true_evidence,
                "graded_quarantined_ambiguous": r.graded_quarantined_ambiguous,
                "region": classify_region(r),
            }
        )
    return buf.getvalue()


def _summary_markdown(summary: dict[str, Any], regions: dict[str, int]) -> str:
    lines: list[str] = []
    lines.append("# EAI Graded Falsification Phase Diagram v1 — Summary\n")
    lines.append(f"- **schema_version**: `{_SCHEMA_VERSION}`")
    lines.append(f"- **total cells**: `{summary['total_cells']}`")
    lines.append(f"- **verdict**: **`{summary['verdict']}`**")
    lines.append(f"- **verdict_reason**: {summary['verdict_reason']}")
    lines.append("")
    lines.append("## Region totals (global)\n")
    lines.append("| Region | Count |")
    lines.append("|---|---:|")
    lines.append(f"| useful | {regions['useful']} |")
    lines.append(f"| regression | {regions['regression']} |")
    lines.append(f"| null | {regions['null']} |")
    lines.append("")
    lines.append("## Per-claim-class metrics\n")
    lines.append(
        "| claim_class | total | binary_FPR | graded_FPR | ΔFPR | binary_TPR | graded_TPR | "
        "ΔTPR | regression_cells | useful_cells | null_cells |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for cls, m in summary["per_class"].items():
        lines.append(
            f"| `{cls}` | {m['total_cells']} | "
            f"{m['binary_false_promotion_rate']} | "
            f"{m['graded_false_promotion_rate']} | "
            f"{m['graded_delta_false_promotion']} | "
            f"{m['binary_true_positive_rate']} | "
            f"{m['graded_true_positive_rate']} | "
            f"{m['graded_delta_true_positive']} | "
            f"{m['regression_cells_count']} | "
            f"{m['useful_cells_count']} | "
            f"{m['null_cells_count']} |"
        )
    lines.append("")
    lines.append("## Claim boundary\n")
    lines.append(
        "> EAI Graded Falsification Phase Diagram v1 maps the behavioural\n"
        "> difference between binary and graded gates over a deterministic\n"
        "> 6-axis synthetic grid. Outputs are diagnostic only; no\n"
        "> production engine has been modified."
    )
    return "\n".join(lines) + "\n"


def run_phase_diagram() -> tuple[list[CellRecord], dict[str, Any], dict[str, int]]:
    cells = generate_grid()
    records = [evaluate_cell(c) for c in cells]
    summary = summarize_regions(records)
    regions = compute_region_metrics(records)
    return records, summary, regions


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministic phase-diagram tool: binary vs graded gate over a "
            "6-axis grid; pre-registered verdict rules."
        ),
    )
    parser.add_argument(
        "--out-json",
        default="artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_v1.json",
    )
    parser.add_argument(
        "--out-csv",
        default="artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_v1.csv",
    )
    parser.add_argument(
        "--out-summary",
        default="artifacts/eai/phase_diagrams/graded_falsification_phase_diagram_summary.md",
    )
    args = parser.parse_args()

    records, summary, regions = run_phase_diagram()

    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_summary)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    full_report: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "grid_cells": len(records),
        "regions": regions,
        "summary": summary,
        "cells": [_record_to_dict(r) for r in records],
    }
    out_json.write_text(
        json.dumps(full_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_csv.write_text(_records_to_csv(records), encoding="utf-8")
    out_md.write_text(_summary_markdown(summary, regions), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": summary["verdict"],
                "verdict_reason": summary["verdict_reason"],
                "total_cells": len(records),
                "useful": regions["useful"],
                "regression": regions["regression"],
                "null": regions["null"],
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
    if verdict == "REGRESSION_REGION_FOUND":
        return 22
    if verdict == "INVALID_EXPERIMENT":
        return 22
    return 33  # NO_SEPARABLE_REGION_FOUND


if __name__ == "__main__":
    raise SystemExit(main())
