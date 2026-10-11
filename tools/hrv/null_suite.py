"""Five-layer null-suite orchestrator (Task 6).

For a given HRV RR series, this module computes the primary γ-program
test statistic (DFA α₂ on scales 16–64 beats) on the real signal and
on 200 surrogates drawn from each of the five families defined in
:mod:`tools.hrv.surrogates`.

Per-layer verdict
-----------------
For each of ``{shuffled, iaaft, ar1, poisson, latent_gmm}``:
  z = (statistic_real − μ_null) / σ_null
  verdict =
    SEPARABLE      if |z| ≥ 3.0
    BORDERLINE     if 2.0 ≤ |z| < 3.0
    NOT_SEPARABLE  if |z| < 2.0

Overall verdict
---------------
  null_verdict = "SEPARABLE"    if ≥ 3 layers are SEPARABLE
               = "BORDERLINE"   if 1-2 layers SEPARABLE + rest BORDERLINE
               = "NOT_SEPARABLE" if 0 layers SEPARABLE
  A positive γ-claim downstream requires the SEPARABLE verdict. Anything
  weaker means the null explains the signal. This rule is deterministic
  and review-visible.

Statistic choice
----------------
DFA α₂ on scales ``[16, 64]`` beats is the canonical long-scale HRV
exponent (Peng et al. 1995). It is the primary γ-program marker; the
broader 11-metric panel (Task 3) is not yet under the null test.
Layer-per-metric expansion belongs to a future PR.

Windowing
---------
The runner truncates each subject to the first ``n_beats_cap`` beats
(default 10 000) so the compute budget stays under 30 s per subject
for 200 × 5 surrogates. Full-recording sensitivity is handled by
Task 9 (state contrast).
"""

from __future__ import annotations

import dataclasses
import hashlib
import math
from typing import Any, Literal

import numpy as np

from tools.hrv.baseline_panel import dfa_alpha, sample_entropy
from tools.hrv.surrogates import SURROGATE_FAMILIES, SurrogateFamily, generate_family

__all__ = [
    "NullSuiteConfig",
    "LayerResult",
    "NullSuiteResult",
    "compute_null_suite",
    "verdict_from_z",
    "aggregate_verdict",
    "SEP",
    "BORD",
    "NOTSEP",
]

SEP: Literal["SEPARABLE"] = "SEPARABLE"
BORD: Literal["BORDERLINE"] = "BORDERLINE"
NOTSEP: Literal["NOT_SEPARABLE"] = "NOT_SEPARABLE"

_Verdict = Literal["SEPARABLE", "BORDERLINE", "NOT_SEPARABLE"]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
StatisticName = Literal["dfa_alpha_16_64", "sample_entropy"]


@dataclasses.dataclass(frozen=True)
class NullSuiteConfig:
    statistic: StatisticName = "dfa_alpha_16_64"
    n_surrogates_per_layer: int = 200
    dfa_scales: tuple[int, ...] = (16, 22, 30, 40, 54, 64)
    n_beats_cap: int = 10_000
    # SampEn params — IAAFT destroys template recurrence, so this is the
    # statistic that should give Branch B a path past the 4/69 DFA α₂
    # non-separation. m, r per Richman & Moorman 2000; cap below 10k cap
    # because SampEn is O(N²).
    sampen_m: int = 2
    sampen_r_frac: float = 0.2
    sampen_max_n: int = 2000
    z_separable: float = 3.0
    z_borderline_low: float = 2.0
    required_separable_layers: int = 3


DEFAULT_CONFIG = NullSuiteConfig()


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def verdict_from_z(z: float, cfg: NullSuiteConfig = DEFAULT_CONFIG) -> _Verdict:
    az = abs(z)
    if az >= cfg.z_separable:
        return SEP
    if az >= cfg.z_borderline_low:
        return BORD
    return NOTSEP


def aggregate_verdict(
    per_layer: dict[str, _Verdict], cfg: NullSuiteConfig = DEFAULT_CONFIG
) -> _Verdict:
    sep = sum(1 for v in per_layer.values() if v == SEP)
    bord = sum(1 for v in per_layer.values() if v == BORD)
    if sep >= cfg.required_separable_layers:
        return SEP
    if sep >= 1 or bord >= 2:
        return BORD
    return NOTSEP


# ---------------------------------------------------------------------------
# Per-subject result
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class LayerResult:
    family: SurrogateFamily
    statistic_null_mean: float
    statistic_null_std: float
    statistic_null_p05: float
    statistic_null_p50: float
    statistic_null_p95: float
    z_score: float
    verdict: _Verdict


@dataclasses.dataclass(frozen=True)
class NullSuiteResult:
    subject_record: str
    cohort: str
    n_beats_used: int
    rr_sha256: str
    statistic_real: float
    config: dict[str, Any]
    per_layer: list[LayerResult]
    overall_verdict: _Verdict

    def as_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["per_layer"] = [dataclasses.asdict(lr) for lr in self.per_layer]
        return d


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def _compute_statistic(rr: np.ndarray, cfg: NullSuiteConfig) -> float:
    if cfg.statistic == "dfa_alpha_16_64":
        return dfa_alpha(rr, np.asarray(cfg.dfa_scales, dtype=np.int64))
    if cfg.statistic == "sample_entropy":
        return sample_entropy(
            rr,
            m=cfg.sampen_m,
            r_frac=cfg.sampen_r_frac,
            max_n=cfg.sampen_max_n,
        )
    raise ValueError(f"unknown statistic: {cfg.statistic!r}")


def compute_null_suite(
    rr: np.ndarray,
    cohort: str,
    subject_record: str,
    seed: int,
    cfg: NullSuiteConfig = DEFAULT_CONFIG,
) -> NullSuiteResult:
    """Run the five-layer null suite on one RR series."""

    rr = np.asarray(rr, dtype=np.float64)
    if rr.size > cfg.n_beats_cap:
        rr = rr[: cfg.n_beats_cap]
    min_beats = max(cfg.dfa_scales) * 4 if cfg.statistic == "dfa_alpha_16_64" else cfg.sampen_m + 4
    if rr.size < min_beats:
        raise ValueError(
            f"rr too short for null suite ({cfg.statistic}): {rr.size} beats, need ≥ {min_beats}"
        )

    stat_real = _compute_statistic(rr, cfg)
    per_layer: list[LayerResult] = []
    per_layer_verdicts: dict[str, _Verdict] = {}

    # distinct seed per family so inter-family draws are uncorrelated
    family_seeds = {fam: seed * 1_000_003 + i for i, fam in enumerate(SURROGATE_FAMILIES)}

    for fam in SURROGATE_FAMILIES:
        surr = generate_family(rr, fam, cfg.n_surrogates_per_layer, family_seeds[fam])
        stats_null = np.array(
            [_compute_statistic(surr[i], cfg) for i in range(surr.shape[0])],
            dtype=np.float64,
        )
        finite = stats_null[np.isfinite(stats_null)]
        if finite.size < cfg.n_surrogates_per_layer // 2:
            mu = math.nan
            sigma = math.nan
            p05 = p50 = p95 = math.nan
            z = math.nan
        else:
            mu = float(finite.mean())
            sigma = float(finite.std(ddof=1))
            p05, p50, p95 = (float(v) for v in np.percentile(finite, [5, 50, 95]))
            z = (stat_real - mu) / sigma if sigma > 0 and math.isfinite(stat_real) else math.nan
        v = verdict_from_z(z, cfg) if math.isfinite(z) else NOTSEP
        per_layer.append(
            LayerResult(
                family=fam,
                statistic_null_mean=mu,
                statistic_null_std=sigma,
                statistic_null_p05=p05,
                statistic_null_p50=p50,
                statistic_null_p95=p95,
                z_score=z,
                verdict=v,
            )
        )
        per_layer_verdicts[fam] = v

    overall = aggregate_verdict(per_layer_verdicts, cfg)

    return NullSuiteResult(
        subject_record=subject_record,
        cohort=cohort,
        n_beats_used=int(rr.size),
        rr_sha256=hashlib.sha256(rr.astype(np.float64).tobytes()).hexdigest(),
        statistic_real=float(stat_real),
        config={
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
            "families": list(SURROGATE_FAMILIES),
        },
        per_layer=per_layer,
        overall_verdict=overall,
    )
