#!/usr/bin/env python3
"""Generate product-grade report bundle for Machine Thinking checklist.

One command creates:
- JSON validation report (machine-consumable)
- Markdown executive report (human-consumable)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from substrates.bn_syn.scripts.validate_thinking_checklist import validate_file


def _md_report(payload: dict) -> str:
    lines = [
        "# Machine Thinking Product Report",
        "",
        f"- Timestamp (UTC): {datetime.now(timezone.utc).isoformat()}",
        f"- Checklist: `{payload['checklist_path']}`",
        f"- Profile: `{payload['profile']}`",
        f"- Verdict: **{payload['verdict']}**",
        f"- Completion ratio: `{payload['completion_ratio']}`",
        f"- Value score: `{payload['value_score']}`",
        f"- Capital index: `{payload['capital_index']}`",
        "",
        "## Structural errors",
    ]
    if payload["structure_errors"]:
        lines.extend([f"- {e}" for e in payload["structure_errors"]])
    else:
        lines.append("- none")

    lines += ["", "## Unresolved by section"]
    if payload["unresolved_by_section"]:
        for section, count in sorted(payload["unresolved_by_section"].items()):
            lines.append(f"- {section}: {count}")
    else:
        lines.append("- none")

    lines += ["", "## Intention hints"]
    if payload["intention_hints"]:
        lines.extend([f"- {h}" for h in payload["intention_hints"]])
    else:
        lines.append("- none")

    lines += ["", "## Action plan"]
    if payload["action_plan"]:
        for section, actions in payload["action_plan"].items():
            lines.append(f"### {section}")
            for action in actions:
                lines.append(f"- {action}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checklist", type=Path, required=True)
    ap.add_argument("--profile", choices=["basic", "research_v1"], default="research_v1")
    ap.add_argument("--min-completion", type=float, default=1.0)
    ap.add_argument("--min-capital-index", type=float, default=0.0)
    ap.add_argument("--out-dir", type=Path, default=Path("proof_bundle/reports"))
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = validate_file(
        args.checklist,
        profile=args.profile,
        min_completion=args.min_completion,
        min_capital_index=args.min_capital_index,
    )

    json_path = args.out_dir / "thinking_capital_report.json"
    md_path = args.out_dir / "thinking_capital_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_md_report(report), encoding="utf-8")

    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "verdict": report["verdict"]}, ensure_ascii=False))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
