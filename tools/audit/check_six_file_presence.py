#!/usr/bin/env python3
"""Validate Six-File Methodology artifacts exist and are non-empty.

Usage:
  python tools/audit/check_six_file_presence.py [--root <repo-root>] [--out <json-path>]

Exit code:
  0 if PASS, 1 if FAIL.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = [
    Path("docs/research/01_problem.md"),
    Path("docs/research/02_contract.yaml"),
    Path("docs/research/03_invariants.yaml"),
    Path("docs/research/04_test_plan.md"),
    Path("docs/research/05_governance.md"),
    Path("docs/research/06_change_plan.md"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--out",
        default="artifacts/audit/six_file_presence_report.json",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out

    checks: list[dict[str, object]] = []
    for rel in REQUIRED:
        fp = root / rel
        exists = fp.exists()
        non_empty = exists and fp.is_file() and fp.stat().st_size > 0
        checks.append(
            {
                "path": str(rel),
                "exists": exists,
                "non_empty": bool(non_empty),
                "status": "PASS" if non_empty else "FAIL",
            }
        )

    all_pass = all(c["status"] == "PASS" for c in checks)
    report = {
        "check_id": "PRE-03",
        "protocol_id": "NEOSYNAPTEX-PROTOCOL-v1.1",
        "status": "PASS" if all_pass else "FAIL",
        "required_files": checks,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
