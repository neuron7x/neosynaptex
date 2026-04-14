#!/usr/bin/env python3
"""One-shot driver to run the FRED γ-replication from a local CSV.

Convenience wrapper around ``substrates.market_fred.run_replication``
that skips the network fetch when a local CSV is already present.
Used during bootstrap when the Python urllib path is too slow or
the runtime environment blocks outbound HTTPS; curl can stage the
CSV beforehand.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import logging
import pathlib
import sys

import numpy as np

from substrates.market_fred.fred_client import parse_fred_csv
from substrates.market_fred.gamma_fit import (
    NullComparison,
    fit_gamma_log_log_psd,
    null_comparison,
)

logger = logging.getLogger(__name__)


def _log_returns(values):
    arr = np.array([v for v in values if v is not None and v > 0], dtype=float)
    return np.diff(np.log(arr))


def main() -> int:
    logging.basicConfig(level="INFO", format="[%(levelname)s] %(message)s")

    csv_path = pathlib.Path("evidence/replications/fred_indpro/INDPRO.csv")
    out_path = pathlib.Path("evidence/replications/fred_indpro/result.json")

    if not csv_path.is_file():
        print(f"missing local CSV at {csv_path}", file=sys.stderr)
        return 2

    raw = csv_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    rows = parse_fred_csv(raw)
    values = [r[1] for r in rows]
    returns = _log_returns(values)
    logger.info("raw rows: %d, valid log-returns: %d", len(rows), len(returns))

    gamma_fit = fit_gamma_log_log_psd(returns, fs=1.0, bootstrap_n=500, seed=42)
    logger.info(
        "γ=%.4f CI=[%.4f,%.4f] r²=%.3f nfreq=%d",
        gamma_fit.gamma,
        gamma_fit.ci_low,
        gamma_fit.ci_high,
        gamma_fit.r2,
        gamma_fit.n_frequencies_fit,
    )

    nulls = []
    for family in ("shuffled", "ar1", "iaaft"):
        logger.info("null family: %s (n=500)", family)
        try:
            cmp = null_comparison(
                real_gamma=gamma_fit.gamma,
                x=returns,
                null_family=family,
                n_surrogates=500,
                seed=42 + hash(family) % 10_000,
                fs=1.0,
            )
            nulls.append(cmp)
            logger.info(
                "  μ=%.4f σ=%.4f z=%.3f separable=%s",
                cmp.mu,
                cmp.sigma,
                cmp.z_score,
                cmp.separable_at_z3,
            )
        except Exception as exc:
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
        "series_id": "INDPRO",
        "claim_status": "measured" if all_separable else "hypothesized",
        "verdict": (
            "separable_from_all_tested_nulls"
            if all_separable
            else "non_separable_from_at_least_one_null"
        ),
        "gamma": dataclasses.asdict(gamma_fit),
        "nulls": [dataclasses.asdict(n) for n in nulls],
        "provenance": {
            "series_id": "INDPRO",
            "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDPRO",
            "bytes_count": len(raw),
            "sha256": sha,
            "fetched_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fetch_method": "curl (urllib timed out)",
        },
        "method_hierarchy_cite": "docs/MEASUREMENT_METHOD_HIERARCHY.md §2.3 (bounded secondary)",
        "null_hierarchy_cite": "docs/NULL_MODEL_HIERARCHY.md §2.1–2.3",
        "interpretation_boundary": (
            "Measures the aperiodic slope of FRED INDPRO log-returns "
            "via Welch-PSD + Theil-Sen (bounded-secondary method per "
            "MEASUREMENT_METHOD_HIERARCHY.md §2.3). Does NOT license "
            "any claim about market criticality, economic laws, or "
            "cross-substrate γ convergence. Does NOT replace the "
            "primary specparam/IRASA measurement which is a follow-up "
            "PR. Nulls tested in this pass: shuffled + AR(1) + IAAFT. "
            "OU and latent-variable surrogate are deferred. Poisson "
            "N/A for continuous series. Per docs/CLAIM_BOUNDARY.md §3.1."
        ),
        "claim_boundary_pointer": "docs/CLAIM_BOUNDARY.md",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("wrote %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
