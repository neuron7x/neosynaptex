"""CLI — five-layer null suite on the DEVELOPMENT split (Task 6).

The suite runs on the calibration (development) split only; the
external split stays blind per Task 2 / Task 8 / audit E-02 / E-03.

Usage
-----
  python -m scripts.run_null_suite                          # all 69 dev subjects
  python -m scripts.run_null_suite --n-surrogates 50        # quick smoke mode
  python -m scripts.run_null_suite --subjects nsr2db:nsr001 chfdb:chf01

Outputs
-------
  evidence/surrogates/{cohort}__{record}/null_suite.json
  evidence/surrogates/null_suite_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from tools.data.analysis_split import enforce_dev_only, load_split
from tools.hrv.null_suite import DEFAULT_CONFIG, NullSuiteConfig, compute_null_suite


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--statistic",
        choices=["dfa_alpha_16_64", "sample_entropy"],
        default=DEFAULT_CONFIG.statistic,
    )
    ap.add_argument("--n-surrogates", type=int, default=DEFAULT_CONFIG.n_surrogates_per_layer)
    ap.add_argument("--n-beats-cap", type=int, default=DEFAULT_CONFIG.n_beats_cap)
    ap.add_argument("--sampen-max-n", type=int, default=DEFAULT_CONFIG.sampen_max_n)
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument(
        "--subjects",
        nargs="*",
        help="Specific subjects in 'cohort:record' form (overrides dev split).",
    )
    ap.add_argument("--cache-dir", type=Path, default=Path("data/raw"))
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Defaults to evidence/surrogates (α₂) or evidence/surrogates_sampen.",
    )
    args = ap.parse_args(argv)

    cfg = NullSuiteConfig(
        statistic=args.statistic,
        n_surrogates_per_layer=args.n_surrogates,
        n_beats_cap=args.n_beats_cap,
        sampen_max_n=args.sampen_max_n,
    )
    if args.out_dir is None:
        args.out_dir = (
            Path("evidence/surrogates")
            if args.statistic == "dfa_alpha_16_64"
            else Path("evidence/surrogates_sampen")
        )

    split = load_split()
    if args.subjects:
        subjects = [tuple(s.split(":", 1)) for s in args.subjects]  # type: ignore[misc]
    else:
        subjects = [(s.cohort, s.record) for s in split.development.subjects]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_entries: list[dict] = []
    rc = 0

    _log(
        f"running {cfg.n_surrogates_per_layer} × 5 surrogates on "
        f"{len(subjects)} subjects (beats≤{cfg.n_beats_cap})"
    )

    with enforce_dev_only():
        for i, (cohort, record) in enumerate(subjects, start=1):
            rr_path = args.cache_dir / cohort / f"{record}.rr.npy"
            if not rr_path.exists():
                _log(f"  [{i:3d}/{len(subjects)}] {cohort}:{record} NO_CACHE — skipped")
                rc = 1
                continue
            rr = np.load(rr_path, allow_pickle=False)

            t0 = time.monotonic()
            res = compute_null_suite(
                rr,
                cohort=cohort,
                subject_record=record,
                seed=args.seed_base + i,
                cfg=cfg,
            )
            dt = time.monotonic() - t0

            subj_dir = args.out_dir / f"{cohort}__{record}"
            subj_dir.mkdir(parents=True, exist_ok=True)
            (subj_dir / "null_suite.json").write_text(
                json.dumps(res.as_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            sep = sum(1 for lr in res.per_layer if lr.verdict == "SEPARABLE")
            _log(
                f"  [{i:3d}/{len(subjects)}] {cohort}:{record}  "
                f"α₂={res.statistic_real:+.3f}  sep={sep}/5 → {res.overall_verdict}  ({dt:.1f}s)"
            )
            summary_entries.append(
                {
                    "cohort": cohort,
                    "record": record,
                    "statistic_real": res.statistic_real,
                    "overall_verdict": res.overall_verdict,
                    "layers": {lr.family: lr.verdict for lr in res.per_layer},
                    "z_scores": {lr.family: lr.z_score for lr in res.per_layer},
                    "n_beats_used": res.n_beats_used,
                }
            )

    summary = {
        "schema_version": 1,
        "config": {
            "statistic": cfg.statistic,
            "n_surrogates_per_layer": cfg.n_surrogates_per_layer,
            "dfa_scales": list(cfg.dfa_scales),
            "sampen_m": cfg.sampen_m,
            "sampen_r_frac": cfg.sampen_r_frac,
            "sampen_max_n": cfg.sampen_max_n,
            "n_beats_cap": cfg.n_beats_cap,
            "z_separable": cfg.z_separable,
            "z_borderline_low": cfg.z_borderline_low,
            "required_separable_layers": cfg.required_separable_layers,
        },
        "split_scope": "development_only",
        "subjects": summary_entries,
        "aggregate": {
            "n_subjects": len(summary_entries),
            "overall_verdict_counts": _count_by(summary_entries, "overall_verdict"),
            "layer_separable_counts": {
                fam: sum(1 for e in summary_entries if e["layers"].get(fam) == "SEPARABLE")
                for fam in ("shuffled", "iaaft", "ar1", "poisson", "latent_gmm")
            },
        },
    }
    out = args.out_dir / "null_suite_summary.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _log(f"summary → {out}")
    return rc


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        v = str(r[key])
        out[v] = out.get(v, 0) + 1
    return out


if __name__ == "__main__":
    raise SystemExit(main())
