"""CLI entry point for the estimator admissibility trial.

Usage::

    python -m tools.phase_3.admissibility.run_admissibility_trial \\
        --M 100 --smoke \\
        --out evidence/estimator_admissibility/smoke.json

The CLI is the single artefact the CI workflow invokes; everything
non-CI (tests, ad-hoc analysis) imports from
``tools.phase_3.admissibility.trial`` and ``.verdict`` directly.

Exit codes:
    0 — trial completed; verdict block written to ``--out``.
    2 — invalid CLI arguments.
    Any non-zero — the trial completed but the verdict says BLOCKED;
                   the runner does NOT fail-closed on a BLOCKED
                   verdict. Phase 3's null-screen runner is the layer
                   that gates on the verdict, not this CLI.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

from tools.phase_3.admissibility.estimators import (
    ESTIMATOR_NAMES,
    get_bootstrap_b,
    set_bootstrap_b,
)
from tools.phase_3.admissibility.trial import (
    DEFAULT_GAMMA_GRID,
    DEFAULT_N_GRID,
    DEFAULT_SIGMA_GRID,
    TrialConfig,
    run_trial,
)
from tools.phase_3.admissibility.verdict import build_verdict, format_verdict_block
from tools.phase_3.result_hash import compute_result_hash

__all__ = ["main"]


_SMOKE_M_DEFAULT: int = 100
_CANONICAL_M_DEFAULT: int = 1000
_DEFAULT_SEED_BASE: int = 0xC0FFEE

# Smoke-mode caps. Selected so that all 5 estimators × the smoke grid
# fits in a single CI matrix leg's 30 min budget. Documented divergence
# from the spec — the spec mandates B=1000 and N up to 1024 for the
# main matrix; smoke trades resolution for throughput so PR-time runs
# stay tractable. The full B=1000 + N up to 1024 is exercised at
# canonical M=1000 on push / merge_group, where each estimator runs
# in its own job with a 360-min timeout.
#
# At N=1024 with B=1000 a single bootstrap_median_slope replicate
# costs ~16 s. Smoke at M=100 would therefore be 16 × 100 × 7 × 4 ≈
# 12 hours just for that one estimator at that one N. Caps below
# bring the slow legs under 30 min each.
_SMOKE_N_GRID: tuple[int, ...] = (20, 64, 128, 256)
_SMOKE_BOOTSTRAP_B: int = 100
# Window/drift/dispersion metrics are O(M_window * N) per cell; capping
# at 5 replicates instead of 20 gives a 4× speedup on smoke without
# changing what those metrics *report* (we still report the worst-case
# across the cap, the conservative direction for an admissibility gate).
_SMOKE_WINDOW_REPLICATES: int = 5


def _build_parser() -> argparse.ArgumentParser:
    """Return the trial CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="run_admissibility_trial",
        description="Estimator admissibility trial — Phase 3 P0 measurement gate.",
    )
    p.add_argument(
        "--M",
        type=int,
        default=_SMOKE_M_DEFAULT,
        help="Number of replicates per cell. Smoke=100 (default), canonical=1000.",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help=(
            "Smoke mode. Caps the N grid at N=512 (drops N=1024) and sets "
            "bootstrap B=200 to keep the matrix tractable in the CI time "
            "budget (~5-15 min). The full N grid and B=1000 are exercised "
            "at canonical M=1000 on main / merge_group."
        ),
    )
    p.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output JSON path. Parent directory is created if needed.",
    )
    p.add_argument(
        "--estimators",
        type=str,
        default=",".join(ESTIMATOR_NAMES),
        help=(
            "Comma-separated subset of estimator names to evaluate. "
            f"Default: all five ({','.join(ESTIMATOR_NAMES)})."
        ),
    )
    p.add_argument(
        "--noise-sigma",
        type=str,
        default=",".join(f"{s:g}" for s in DEFAULT_SIGMA_GRID),
        help="Comma-separated σ grid (default: 0,0.05,0.1,0.2).",
    )
    p.add_argument(
        "--gamma-grid",
        type=str,
        default=",".join(f"{g:g}" for g in DEFAULT_GAMMA_GRID),
        help="Comma-separated γ_true grid.",
    )
    p.add_argument(
        "--n-grid",
        type=str,
        default=None,
        help=(
            "Comma-separated N grid. Default depends on --smoke: smoke uses "
            f"{','.join(str(n) for n in _SMOKE_N_GRID)}, canonical uses "
            f"{','.join(str(n) for n in DEFAULT_N_GRID)}."
        ),
    )
    p.add_argument(
        "--bootstrap-b",
        type=int,
        default=None,
        help=(
            "Bootstrap resample count for bootstrap_median_slope. Default "
            f"depends on --smoke: smoke={_SMOKE_BOOTSTRAP_B}, "
            "canonical=1000."
        ),
    )
    p.add_argument(
        "--seed-base",
        type=lambda s: int(s, 0),
        default=_DEFAULT_SEED_BASE,
        help="RNG seed base. Same seed → identical result_hash.",
    )
    p.add_argument(
        "--n-window-replicates",
        type=int,
        default=None,
        help=(
            "Cap on the number of replicates used for the window-based "
            "metrics (5-7). Default depends on --smoke: smoke="
            f"{_SMOKE_WINDOW_REPLICATES}, canonical=20."
        ),
    )
    p.add_argument(
        "--print-block",
        action="store_true",
        help="Print the six-field verdict block to stdout after writing JSON.",
    )
    return p


def _parse_csv_floats(s: str) -> tuple[float, ...]:
    return tuple(float(x) for x in s.split(",") if x.strip())


def _parse_csv_ints(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in s.split(",") if x.strip())


def _parse_csv_strs(s: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in s.split(",") if x.strip())


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    estimator_names = _parse_csv_strs(args.estimators)
    invalid = [e for e in estimator_names if e not in ESTIMATOR_NAMES]
    if invalid:
        print(f"unknown estimator names: {invalid}", file=sys.stderr)
        return 2

    # ``canonical_theil_sen`` is the verdict-comparison anchor — every
    # alternate is judged "accepted vs canonical" or "rejected, this
    # alternate is the replacement". The CI matrix parallelises across
    # estimators, so single-estimator legs (e.g. ``--estimators
    # odr_log_log``) still need canonical present for the verdict
    # block. Auto-include it; the cost is one extra estimator-grid per
    # leg, which is the cheapest of the five (no bootstrap, no ODR
    # fit, no quantile sweep).
    if "canonical_theil_sen" not in estimator_names:
        estimator_names = ("canonical_theil_sen", *estimator_names)

    # Smoke-aware defaults for N grid and bootstrap B.
    if args.n_grid is None:
        n_grid = _SMOKE_N_GRID if args.smoke else DEFAULT_N_GRID
    else:
        n_grid = _parse_csv_ints(args.n_grid)
    if args.bootstrap_b is None:
        bootstrap_b = _SMOKE_BOOTSTRAP_B if args.smoke else 1000
    else:
        bootstrap_b = int(args.bootstrap_b)
    set_bootstrap_b(bootstrap_b)

    if args.n_window_replicates is None:
        n_window = _SMOKE_WINDOW_REPLICATES if args.smoke else 20
    else:
        n_window = int(args.n_window_replicates)

    config = TrialConfig(
        gamma_grid=_parse_csv_floats(args.gamma_grid),
        n_grid=tuple(n_grid),
        sigma_grid=_parse_csv_floats(args.noise_sigma),
        estimator_names=estimator_names,
        m_replicates=int(args.M),
        seed_base=int(args.seed_base),
        n_replicates_for_window_metrics=n_window,
    )

    started = _dt.datetime.now(tz=_dt.timezone.utc)
    results = run_trial(config)
    finished = _dt.datetime.now(tz=_dt.timezone.utc)

    verdict = build_verdict(results)
    block = format_verdict_block(verdict)

    # Hashable payload contains ONLY the deterministic content fields.
    # Wall-clock (started/finished) and measured runtime are stamped
    # *after* hashing so that two identical-config runs produce a
    # byte-identical ``result_hash`` despite differing timestamps.
    hashable: dict[str, Any] = {
        "schema_version": "1.0.0",
        "verdict": verdict,
        "verdict_block": block,
        "results": results,
        "bootstrap_b": int(get_bootstrap_b()),
    }
    payload: dict[str, Any] = dict(hashable)
    payload["generated_at_utc"] = started.isoformat()
    payload["completed_at_utc"] = finished.isoformat()
    payload["runtime_seconds"] = (finished - started).total_seconds()
    payload["result_hash"] = compute_result_hash(hashable)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if args.print_block:
        print(block, end="")
        print(f"\nresult_hash: {payload['result_hash']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
