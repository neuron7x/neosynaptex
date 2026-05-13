from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.eai.calibration import run_calibration


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(dataset_path: Path) -> dict[str, Any]:
    metrics = run_calibration(dataset_path)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256_file(dataset_path),
        "metrics": asdict(metrics),
        "artifact_owner": "eai-research-track",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run EAI calibration and emit structured UTC report."
    )
    parser.add_argument("--dataset", default="data/eai_calibration/dataset_v0.jsonl")
    parser.add_argument("--out", default="artifacts/repro/calibration_report.json")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    report = build_report(dataset_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
