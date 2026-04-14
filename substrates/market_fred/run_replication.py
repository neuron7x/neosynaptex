"""End-to-end FRED γ-replication runner.

Canonical entry point for the FRED macro-economic substrate γ-run.
Fetches a FRED series, computes γ on the log-returns PSD, runs the
null families required by ``docs/NULL_MODEL_HIERARCHY.md``, and
writes a structured result JSON.

Example
-------

    python -m substrates.market_fred.run_replication \\
        --series INDPRO \\
        --out evidence/replications/fred_indpro/result.json

The output JSON is consumed by ``REPLICATION_REPORT_FRED.md`` and
by ``evidence/replications/registry.yaml``.

Scope bounds
------------

* This is a **bounded-secondary** γ-fit using Welch-PSD + Theil-Sen
  (`MEASUREMENT_METHOD_HIERARCHY.md §2.3`). Primary method (specparam
  + IRASA) is a follow-up once the substrate has passed initial
  prereg + one external rerun.
* Null families run in this pass: shuffled + AR(1) + IAAFT.
  Latent-variable surrogate is a Phase III §Step 14 primary threat
  model and is deferred to a follow-up PR once a concrete
  latent-dynamics model for FRED is prereg'd.
* Poisson null is not applicable (continuous series).
* The substrate's `allowed_claim` is `exploratory` per
  `docs/SUBSTRATE_MEASUREMENT_TABLE.yaml`. No evidential claim
  lands on this PR.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import pathlib

import numpy as np

from substrates.market_fred.fred_client import fetch_series, parse_fred_csv
from substrates.market_fred.gamma_fit import (
    NullComparison,
    fit_gamma_log_log_psd,
    null_comparison,
)

logger = logging.getLogger(__name__)


def _log_returns(values: list[float | None]) -> np.ndarray:
    """Return log-returns over the valid non-None values."""

    arr = np.array([v for v in values if v is not None and v > 0], dtype=float)
    if len(arr) < 2:
        raise ValueError("not enough positive valid values for log-returns")
    return np.diff(np.log(arr))


def run_replication(
    series_id: str,
    *,
    null_families: tuple[str, ...] = ("shuffled", "ar1", "iaaft"),
    n_surrogates: int = 500,
    seed: int = 42,
    fs: float = 1.0,
    out_json_path: pathlib.Path | None = None,
    out_csv_path: pathlib.Path | None = None,
) -> dict:
    """Fetch, fit, run nulls, emit structured result.

    Returns the result dict. If ``out_json_path`` is given, also
    writes the JSON to disk.
    """

    logger.info("fetching FRED series %s", series_id)
    fetch = fetch_series(series_id, out_path=out_csv_path)
    rows = parse_fred_csv(fetch.raw_csv)
    values = [r[1] for r in rows]
    returns = _log_returns(values)
    logger.info("parsed %d raw rows; %d valid log-returns", len(rows), len(returns))

    gamma_fit = fit_gamma_log_log_psd(returns, fs=fs, bootstrap_n=500, seed=seed)
    logger.info(
        "γ=%.4f CI=[%.4f,%.4f] r²=%.3f",
        gamma_fit.gamma,
        gamma_fit.ci_low,
        gamma_fit.ci_high,
        gamma_fit.r2,
    )

    nulls: list[NullComparison] = []
    for family in null_families:
        logger.info("running null family: %s (n=%d)", family, n_surrogates)
        try:
            cmp = null_comparison(
                real_gamma=gamma_fit.gamma,
                x=returns,
                null_family=family,
                n_surrogates=n_surrogates,
                seed=seed + hash(family) % 10_000,
                fs=fs,
            )
            nulls.append(cmp)
            logger.info(
                "  %s: μ=%.4f σ=%.4f z=%.3f separable=%s",
                family,
                cmp.mu,
                cmp.sigma,
                cmp.z_score,
                cmp.separable_at_z3,
            )
        except Exception as exc:  # noqa: BLE001 — surface as structured null failure
            logger.warning("null %s failed: %s", family, exc)
            nulls.append(
                NullComparison(
                    null_family=family,
                    n_surrogates=0,
                    mu=float("nan"),
                    sigma=float("nan"),
                    z_score=float("nan"),
                    null_ci_low=float("nan"),
                    null_ci_high=float("nan"),
                    real_outside_null_ci=False,
                    separable_at_z3=False,
                )
            )

    all_separable = all(n.separable_at_z3 for n in nulls if n.n_surrogates > 0)

    result = {
        "substrate": "market_fred",
        "series_id": series_id,
        "claim_status": "measured" if all_separable else "hypothesized",
        "verdict": (
            "separable_from_all_tested_nulls"
            if all_separable
            else "non_separable_from_at_least_one_null"
        ),
        "gamma": dataclasses.asdict(gamma_fit),
        "nulls": [dataclasses.asdict(n) for n in nulls],
        "provenance": fetch.as_provenance_dict(),
        "method_hierarchy_cite": "docs/MEASUREMENT_METHOD_HIERARCHY.md §2.3 (bounded secondary)",
        "null_hierarchy_cite": "docs/NULL_MODEL_HIERARCHY.md §2.1–2.3",
        "interpretation_boundary": (
            "Measures the aperiodic slope of FRED log-returns via "
            "Welch-PSD + Theil-Sen (bounded-secondary method per "
            "MEASUREMENT_METHOD_HIERARCHY.md §2.3). Does NOT license "
            "any claim about market criticality, economic laws, or "
            "cross-substrate γ convergence. Does NOT replace the "
            "primary specparam/IRASA measurement which is a follow-up "
            "PR. Nulls tested are shuffled + AR(1) + IAAFT; OU and "
            "latent-variable surrogate are deferred. Poisson N/A for "
            "continuous series. Per docs/CLAIM_BOUNDARY.md §3.1."
        ),
        "claim_boundary_pointer": "docs/CLAIM_BOUNDARY.md",
        "notes_per_null": {
            "latent_variable": (
                "DEFERRED — needs substrate-specific latent model PR "
                "per NULL_MODEL_HIERARCHY.md §2.5"
            ),
            "ornstein_uhlenbeck": (
                "DEFERRED — AR(1) substitutes in this pass per §2.3 note"
            ),
            "poisson": "N/A — continuous series",
        },
    }

    if out_json_path is not None:
        out_json_path = pathlib.Path(out_json_path)
        out_json_path.parent.mkdir(parents=True, exist_ok=True)
        out_json_path.write_text(json.dumps(result, indent=2, sort_keys=False), encoding="utf-8")
        logger.info("wrote result to %s", out_json_path)

    return result


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fred_replication",
        description=(
            "FRED γ-replication runner. Per docs/MEASUREMENT_METHOD_HIERARCHY.md "
            "and docs/NULL_MODEL_HIERARCHY.md."
        ),
    )
    p.add_argument("--series", required=True, help="FRED series id (e.g. INDPRO)")
    p.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="Output JSON path for the result record.",
    )
    p.add_argument(
        "--raw-out",
        type=pathlib.Path,
        default=None,
        help="Optional: save fetched raw CSV to this path for provenance.",
    )
    p.add_argument("--n-surrogates", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    return p


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    logging.basicConfig(level="INFO", format="[%(levelname)s] %(message)s")
    ns = _build_argparser().parse_args(argv)
    run_replication(
        series_id=ns.series,
        n_surrogates=ns.n_surrogates,
        seed=ns.seed,
        out_json_path=ns.out,
        out_csv_path=ns.raw_out,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
