"""CLI — emit a publication-grade γ-program run report (Task 10)."""

from __future__ import annotations

import sys

from tools.hrv.full_report import write_full_report


def main() -> int:
    path = write_full_report()
    print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
