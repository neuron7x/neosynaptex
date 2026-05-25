#!/usr/bin/env python3
"""Validate RESEARCH·ENGINEERING checklist completion from Markdown.

Profiles:
- basic: any checklist items are allowed; PASS when completion >= threshold.
- research_v1: enforces canonical RESEARCH·ENGINEERING v1.0 section structure,
  per-section item presence, and full completion.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from substrates.bn_syn.scripts.mt_contract import CANONICAL_SECTIONS, SECTION_WEIGHTS

CHECK_PATTERN = re.compile(r"^\s*(?:[-*+]\s+)?\[(?P<mark>[ xX])\]\s+(?P<item>.+?)\s*$")
SECTION_PATTERN = re.compile(r"^\s*##\s+(?P<section>[^#].*?)\s*$")


@dataclass(frozen=True)
class Finding:
    line: int
    item: str
    section: str


def _normalize_section(text: str) -> str:
    return text.strip().upper()


def parse_checklist(text: str) -> tuple[list[Finding], list[Finding], dict[str, int]]:
    checked: list[Finding] = []
    unchecked: list[Finding] = []
    section_counts: dict[str, int] = {}
    current_section = "UNSCOPED"

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        section_match = SECTION_PATTERN.match(raw_line)
        if section_match is not None:
            current_section = _normalize_section(section_match.group("section"))
            section_counts.setdefault(current_section, 0)
            continue

        match = CHECK_PATTERN.match(raw_line)
        if match is None:
            continue

        section_counts[current_section] = section_counts.get(current_section, 0) + 1
        finding = Finding(line=line_number, item=match.group("item"), section=current_section)
        if match.group("mark").lower() == "x":
            checked.append(finding)
        else:
            unchecked.append(finding)

    return checked, unchecked, section_counts


def _compute_weighted_score(checked: list[Finding], unchecked: list[Finding]) -> float:
    totals: dict[str, int] = {}
    done: dict[str, int] = {}
    for f in checked + unchecked:
        totals[f.section] = totals.get(f.section, 0) + 1
    for f in checked:
        done[f.section] = done.get(f.section, 0) + 1

    weighted_done = 0.0
    weighted_total = 0.0
    for section, total in totals.items():
        w = SECTION_WEIGHTS.get(section, 1.0)
        weighted_done += w * done.get(section, 0)
        weighted_total += w * total
    return round((weighted_done / weighted_total) if weighted_total else 0.0, 6)


def _compute_capital_index(completion_ratio: float, value_score: float, structure_ok: bool) -> float:
    """Composite practical-capital signal for governance dashboards.

    Formula (bounded 0..1):
      0.5 * value_score + 0.3 * completion_ratio + 0.2 * structure_bonus
    where structure_bonus is 1 only when canonical structure was evaluated and satisfied.
    """
    structure_bonus = 1.0 if structure_ok else 0.0
    score = 0.5 * value_score + 0.3 * completion_ratio + 0.2 * structure_bonus
    return round(max(0.0, min(1.0, score)), 6)


def _intention_hints(unresolved_by_section: dict[str, int], top_k: int = 3) -> list[str]:
    if not unresolved_by_section:
        return []
    priorities = sorted(unresolved_by_section.items(), key=lambda kv: (-SECTION_WEIGHTS.get(kv[0], 1.0) * kv[1], kv[0]))
    hints: list[str] = []
    for section, unresolved in priorities[:top_k]:
        hints.append(
            f"Focus {section}: close {unresolved} unresolved item(s); impact weight={SECTION_WEIGHTS.get(section, 1.0):.1f}."
        )
    return hints


def _load_intent_map() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "docs" / "MACHINE_THINKING_INTENT_MAP.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _section_actions(section: str, intent_map: dict[str, Any]) -> list[str]:
    cfg = (intent_map.get("intent_to_action", {}) or {}).get(section, {})
    actions = cfg.get("actions", [])
    return [str(a) for a in actions]


def validate_file(path: Path, profile: str, min_completion: float, min_capital_index: float) -> dict[str, Any]:
    checked, unchecked, section_counts = parse_checklist(path.read_text(encoding="utf-8"))
    total_items = len(checked) + len(unchecked)

    structure_errors: list[str] = []
    if profile == "research_v1":
        missing_sections = [s for s in CANONICAL_SECTIONS if s not in section_counts]
        if missing_sections:
            structure_errors.append(f"Missing canonical sections: {missing_sections}")
        empty_sections = [s for s in CANONICAL_SECTIONS if section_counts.get(s, 0) == 0]
        if empty_sections:
            structure_errors.append(f"Sections without checklist items: {empty_sections}")

    unresolved_by_section: dict[str, int] = {}
    for finding in unchecked:
        unresolved_by_section[finding.section] = unresolved_by_section.get(finding.section, 0) + 1

    completion_ratio = (len(checked) / total_items) if total_items else 0.0
    value_score = _compute_weighted_score(checked, unchecked)
    structure_ok = profile == "research_v1" and not structure_errors
    capital_index = _compute_capital_index(completion_ratio, value_score, structure_ok)

    intent_map = _load_intent_map()

    if profile == "basic":
        verdict = "PASS" if total_items > 0 and completion_ratio >= min_completion and capital_index >= min_capital_index else "FAIL"
    else:
        verdict = "PASS" if total_items > 0 and not unchecked and structure_ok and capital_index >= min_capital_index else "FAIL"

    return {
        "checklist_path": str(path),
        "profile": profile,
        "total_items": total_items,
        "checked_items": len(checked),
        "unchecked_items": len(unchecked),
        "completion_ratio": round(completion_ratio, 6),
        "value_score": value_score,
        "capital_index": capital_index,
        "min_completion": min_completion,
        "min_capital_index": min_capital_index,
        "verdict": verdict,
        "sections": section_counts,
        "structure_errors": structure_errors,
        "unresolved_by_section": unresolved_by_section,
        "intention_hints": _intention_hints(unresolved_by_section),
        "action_plan": {
            section: _section_actions(section, intent_map)
            for section in sorted(unresolved_by_section.keys())
        },
        "unchecked": [{"line": f.line, "section": f.section, "item": f.item} for f in unchecked],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", type=Path, required=True, help="Path to a Markdown checklist file.")
    parser.add_argument("--profile", choices=["basic", "research_v1"], default="research_v1")
    parser.add_argument("--json-out", type=Path, help="Optional path for writing JSON report.")
    parser.add_argument("--min-completion", type=float, default=1.0, help="Completion threshold for basic profile.")
    parser.add_argument("--min-capital-index", type=float, default=0.0, help="Minimum capital index required for PASS.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 0.0 <= args.min_completion <= 1.0:
        raise SystemExit("--min-completion must be in [0, 1]")
    if not 0.0 <= args.min_capital_index <= 1.0:
        raise SystemExit("--min-capital-index must be in [0, 1]")

    report = validate_file(
        args.checklist,
        profile=args.profile,
        min_completion=args.min_completion,
        min_capital_index=args.min_capital_index,
    )
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
