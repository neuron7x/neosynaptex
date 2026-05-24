#!/usr/bin/env python3
"""Validate minimum semantics for Six-File Methodology artifacts.

This complements presence checks: a non-empty file is not enough. The gate emits a
machine-readable report and exits non-zero when required structure is absent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(".")
OUT = ROOT / "artifacts/audit/six_file_semantics_report.json"
REQUIRED_INVARIANT_IDS = {"PRE-03", "MATH-01", "VAL-01", "SEM-01", "ARCH-01"}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_yaml(path: str) -> dict[str, Any]:
    payload = yaml.safe_load(_read(path)) or {}
    return payload if isinstance(payload, dict) else {}


def _record(checks: list[dict[str, str]], name: str, passed: bool) -> None:
    checks.append({"check": name, "status": "PASS" if passed else "FAIL"})


def main() -> int:
    checks: list[dict[str, str]] = []

    problem = _read("docs/research/01_problem.md")
    _record(checks, "PRE-01.problem_statement", bool(re.search(r"Проблема\s*:", problem)))
    _record(checks, "PRE-01.falsification_condition", "Falsification Condition" in problem)

    contract = _load_yaml("docs/research/02_contract.yaml")
    for key in ("inputs", "outputs", "boundaries"):
        _record(checks, f"PRE-02.{key}", bool(contract.get(key)))

    invariants = _load_yaml("docs/research/03_invariants.yaml").get("invariants", [])
    invariant_items = [item for item in invariants if isinstance(item, dict)]
    found_ids = {item.get("id") for item in invariant_items}
    _record(checks, "INVARIANTS.required_ids", REQUIRED_INVARIANT_IDS.issubset(found_ids))
    _record(checks, "INVARIANTS.pass_condition", all(item.get("pass_condition") for item in invariant_items))

    test_plan = _read("docs/research/04_test_plan.md")
    _record(checks, "VAL-01.red_green", "Red" in test_plan and "Green" in test_plan)
    _record(checks, "VAL-03.adversarial", "Adversarial" in test_plan)

    governance = _read("docs/research/05_governance.md")
    _record(checks, "GOV-01.human_impact", "Human Impact" in governance)
    _record(checks, "GOV-02.rollback", "Rollback" in governance)
    _record(checks, "GOV-03.ci_mapping", "CI Failure Mapping" in governance)

    change_plan = _read("docs/research/06_change_plan.md")
    steps = re.findall(r"^\d+\.", change_plan, flags=re.MULTILINE)
    _record(checks, "IMPL-PLAN.min_steps_3", len(steps) >= 3)

    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    report = {
        "check_id": "SEM-01",
        "protocol_id": "NEOSYNAPTEX-PROTOCOL-v1.1",
        "status": status,
        "checks": checks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(OUT)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
