from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.eai.external_verification import run_local_command, write_report


def main() -> None:
    p = argparse.ArgumentParser(
        description="Run an external verification command and write a signed report.",
    )
    p.add_argument("--claim-id", required=True)
    p.add_argument("--output", default="external_verification_report.json")
    p.add_argument("command", nargs="+")
    args = p.parse_args()
    report = run_local_command(args.claim_id, args.command)
    write_report(args.output, report)
    print(report.status)


if __name__ == "__main__":
    main()
