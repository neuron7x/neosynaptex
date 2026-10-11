"""CLI — run the outlier protocol (Task 7) on every cohort subject."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

from tools.data.physionet_cohort import COHORTS, fetch_record
from tools.hrv.outlier_protocol import (
    DEFAULT_CFG,
    compute_outlier_report,
    dump_yaml,
    emit_cohort_summary,
)


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def main() -> int:
    cache_dir = Path("data/raw")
    yaml_dir = Path("evidence/outlier_protocol")
    yaml_dir.mkdir(parents=True, exist_ok=True)

    for cohort, spec in COHORTS.items():
        _log(f"cohort {cohort}: {spec.expected_n_subjects} subjects")
        for record in spec.expected_records:
            rr_path = cache_dir / cohort / f"{record}.rr.npy"
            if not rr_path.exists():
                _log(f"  missing cache for {cohort}:{record}, fetching")
                rec = fetch_record(spec, record, cache_dir=cache_dir / cohort)
                if rec.status != "ok":
                    _log(f"  FAIL {cohort}:{record}: {rec.error_message}")
                    continue
            rr = np.load(rr_path, allow_pickle=False)

            # re-fetch symbols to run signal-quality + ectopy stages
            try:
                import wfdb

                ann = wfdb.rdann(record, spec.annotation_extension, pn_dir=spec.pn_dir)
                symbols = list(ann.symbol)
            except Exception as e:
                _log(f"  symbol-fetch fail {cohort}:{record}: {e}")
                symbols = None

            report = compute_outlier_report(
                rr_raw_s=rr,
                symbols=symbols,
                cohort=cohort,
                record=record,
                cfg=DEFAULT_CFG,
            )
            dump_yaml(report, yaml_dir / f"{cohort}__{record}.yaml")
            _log(f"  {cohort}:{record} → {report.decision}")

    summary = emit_cohort_summary(
        Path("reports/outlier_protocol/summary.json"),
        yaml_dir,
    )
    _log(f"summary: {summary['decision_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
