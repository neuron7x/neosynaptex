"""analysis.gamma_meta_analysis — quantitative meta-analysis of the
``gamma ~ 1`` invariant across substrates.

Implements fixed-effects (inverse-variance weighted) and random-effects
(DerSimonian-Laird tau^2) pooling, Cochran's Q / I^2 / H^2
heterogeneity diagnostics, and a 95% prediction interval following
the IntHout-Ioannidis-Borm formulation.

Verdict is ``INVARIANT_CONFIRMED`` iff all three hold:

  1. the random-effects pooled 95% CI contains 1.0,
  2. I^2 < 75% (no severe between-substrate inconsistency), and
  3. the prediction interval contains 1.0 (a new substrate drawn
     from the same distribution would not reject gamma = 1).

The primary data source is ``evidence/gamma_ledger.json`` — the
canonical neosynaptex substrate ledger (VALIDATED entries only).
``xform_combined_gamma_report.json`` contains *corpus-analysis*
gammas (ChatGPT / ODT document slices), not substrate invariants,
and is opt-in via ``--include-xform`` for exploratory sensitivity
analysis only; it is excluded from the main proof.

Dependencies: numpy + scipy only (per invariant I-3 in CONTRACT.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np
from scipy import stats  # type: ignore[import-untyped]

# 95% z-critical value. The spec uses 1.96 literally; we use scipy's
# full-precision constant so fixed/random pooled CIs round-trip
# through SE derivation at machine epsilon.
_Z_95: float = float(stats.norm.ppf(0.975))


class SubstrateResult(NamedTuple):
    """One row of the forest: a substrate with its gamma estimate and 95% CI."""

    name: str
    gamma: float
    ci_lower: float
    ci_upper: float
    n: int


@dataclass(frozen=True)
class MetaResult:
    """Pooled estimate from one model (fixed or random effects)."""

    gamma: float
    se: float
    ci_lower: float
    ci_upper: float
    z: float
    p_value: float  # two-sided p for H0: gamma = 1
    model: str  # "fixed" or "random"
    tau2: float  # 0.0 for fixed-effects


@dataclass(frozen=True)
class HeterogeneityResult:
    """Between-substrate heterogeneity summary."""

    Q: float
    df: int
    p_heterogeneity: float
    I2: float  # percent scale, 0-100
    H2: float


@dataclass(frozen=True)
class ForestRow:
    """Per-substrate row ready for forest-plot rendering."""

    name: str
    gamma: float
    ci_lower: float
    ci_upper: float
    se: float
    weight_fixed_pct: float
    weight_random_pct: float


@dataclass(frozen=True)
class ProofBundle:
    """Complete, JSON-serializable output of a full meta-analysis."""

    n_substrates: int
    fixed: MetaResult
    random: MetaResult
    heterogeneity: HeterogeneityResult
    prediction_interval: tuple[float, float]
    forest: list[ForestRow]
    verdict: str  # "INVARIANT_CONFIRMED" | "INVARIANT_REJECTED"
    verdict_reasons: list[str]


class GammaMetaAnalysis:
    """Meta-analytic proof of the gamma ~ 1 invariant.

    Given per-substrate ``SubstrateResult`` rows (with 95% CIs),
    pools them under both fixed and random effects, reports
    heterogeneity, and emits a verdict.
    """

    def __init__(self, substrate_data: list[SubstrateResult]) -> None:
        if len(substrate_data) < 2:
            raise ValueError(f"meta-analysis requires >= 2 substrates; got {len(substrate_data)}")
        self.data: list[SubstrateResult] = list(substrate_data)

        gammas = np.asarray([s.gamma for s in self.data], dtype=float)
        half_widths = np.asarray([(s.ci_upper - s.ci_lower) / 2.0 for s in self.data], dtype=float)
        if not np.all(half_widths > 0):
            bad = [s.name for s, hw in zip(self.data, half_widths) if hw <= 0]
            raise ValueError(f"degenerate CI on: {bad}")

        self._gammas: np.ndarray = gammas
        # se_i = (ci_upper_i - ci_lower_i) / (2 * z_0.975)
        self._se: np.ndarray = half_widths / _Z_95
        # w_i = 1 / se_i^2   (fixed-effects inverse-variance weight)
        self._w_fixed: np.ndarray = 1.0 / (self._se**2)

    # ── pooled estimates ──────────────────────────────────────────────

    def pooled_estimate_fixed_effects(self) -> MetaResult:
        w = self._w_fixed
        g = self._gammas
        gamma_hat = float(np.sum(w * g) / np.sum(w))
        se = float(1.0 / np.sqrt(np.sum(w)))
        return self._to_meta(gamma_hat, se, tau2=0.0, model="fixed")

    def pooled_estimate_random_effects(self) -> MetaResult:
        # DerSimonian-Laird tau^2. The moment estimator is:
        #   tau^2 = max(0, (Q - df) / c)
        # with c = sum(w) - sum(w^2)/sum(w). Cochran's Q is computed
        # against the fixed-effects centre.
        fe = self.pooled_estimate_fixed_effects()
        w = self._w_fixed
        g = self._gammas
        Q = float(np.sum(w * (g - fe.gamma) ** 2))
        df = len(self.data) - 1
        sum_w = float(np.sum(w))
        sum_w_sq = float(np.sum(w**2))
        c = sum_w - (sum_w_sq / sum_w) if sum_w > 0 else 0.0
        tau2 = max(0.0, (Q - df) / c) if c > 0 else 0.0

        # Random-effects weights: w*_i = 1 / (se_i^2 + tau^2)
        w_star = 1.0 / (self._se**2 + tau2)
        gamma_hat = float(np.sum(w_star * g) / np.sum(w_star))
        se = float(1.0 / np.sqrt(np.sum(w_star)))
        return self._to_meta(gamma_hat, se, tau2=float(tau2), model="random")

    # ── heterogeneity ─────────────────────────────────────────────────

    def heterogeneity(self) -> HeterogeneityResult:
        fe = self.pooled_estimate_fixed_effects()
        w = self._w_fixed
        g = self._gammas
        Q = float(np.sum(w * (g - fe.gamma) ** 2))
        df = len(self.data) - 1
        p = float(1.0 - stats.chi2.cdf(Q, df=df)) if df > 0 else float("nan")
        # I^2 is a descriptive stat; clamp to [0, 100].
        I2 = max(0.0, (Q - df) / Q) * 100.0 if Q > 0 else 0.0
        H2 = (Q / df) if df > 0 else float("nan")
        return HeterogeneityResult(
            Q=Q,
            df=df,
            p_heterogeneity=p,
            I2=float(I2),
            H2=float(H2),
        )

    # ── prediction interval (IntHout-Ioannidis-Borm) ──────────────────

    def prediction_interval(self) -> tuple[float, float]:
        """95% prediction interval for the true gamma of a *new* substrate.

        PI = gamma_RE +/- t_{k-2, 0.975} * sqrt(tau^2 + se_RE^2)

        Wider than the pooled CI because it bounds where a single new
        substrate's true gamma could fall, not just the meta-analytic
        centre.
        """
        re = self.pooled_estimate_random_effects()
        k = len(self.data)
        df = max(1, k - 2)
        t_crit = float(stats.t.ppf(0.975, df=df))
        sd = float(np.sqrt(re.tau2 + re.se**2))
        return (re.gamma - t_crit * sd, re.gamma + t_crit * sd)

    # ── forest-plot rows ──────────────────────────────────────────────

    def forest_plot_data(self) -> list[ForestRow]:
        re = self.pooled_estimate_random_effects()
        w_fixed = self._w_fixed
        w_random = 1.0 / (self._se**2 + re.tau2)
        wf_total = float(np.sum(w_fixed))
        wr_total = float(np.sum(w_random))
        rows: list[ForestRow] = []
        for i, s in enumerate(self.data):
            rows.append(
                ForestRow(
                    name=s.name,
                    gamma=s.gamma,
                    ci_lower=s.ci_lower,
                    ci_upper=s.ci_upper,
                    se=float(self._se[i]),
                    weight_fixed_pct=float(w_fixed[i] / wf_total * 100.0),
                    weight_random_pct=float(w_random[i] / wr_total * 100.0),
                )
            )
        return rows

    # ── verdict ───────────────────────────────────────────────────────

    def run_full_analysis(self) -> ProofBundle:
        fe = self.pooled_estimate_fixed_effects()
        re = self.pooled_estimate_random_effects()
        het = self.heterogeneity()
        pi = self.prediction_interval()
        forest = self.forest_plot_data()

        pooled_contains_one = re.ci_lower <= 1.0 <= re.ci_upper
        pi_contains_one = pi[0] <= 1.0 <= pi[1]
        low_heterogeneity = het.I2 < 75.0

        reasons: list[str] = []
        if not pooled_contains_one:
            reasons.append(
                f"pooled random-effects CI does not contain 1.0: "
                f"[{re.ci_lower:.4f}, {re.ci_upper:.4f}]"
            )
        if not low_heterogeneity:
            reasons.append(f"I^2 too high: {het.I2:.1f}% >= 75%")
        if not pi_contains_one:
            reasons.append(f"prediction interval does not contain 1.0: [{pi[0]:.4f}, {pi[1]:.4f}]")

        verdict = (
            "INVARIANT_CONFIRMED"
            if pooled_contains_one and low_heterogeneity and pi_contains_one
            else "INVARIANT_REJECTED"
        )
        return ProofBundle(
            n_substrates=len(self.data),
            fixed=fe,
            random=re,
            heterogeneity=het,
            prediction_interval=pi,
            forest=forest,
            verdict=verdict,
            verdict_reasons=reasons,
        )

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _to_meta(gamma: float, se: float, tau2: float, model: str) -> MetaResult:
        ci_lower = gamma - _Z_95 * se
        ci_upper = gamma + _Z_95 * se
        z = (gamma - 1.0) / se if se > 0 else float("nan")
        p = 2.0 * (1.0 - float(stats.norm.cdf(abs(z))))
        return MetaResult(
            gamma=float(gamma),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            z=float(z),
            p_value=float(p),
            model=model,
            tau2=float(tau2),
        )


# ── loaders ───────────────────────────────────────────────────────────


def load_from_gamma_ledger(path: str | Path) -> list[SubstrateResult]:
    """Parse ``evidence/gamma_ledger.json`` into substrate rows.

    Returns one ``SubstrateResult`` per entry with ``status ==
    "VALIDATED"`` and a complete ``(gamma, ci_low, ci_high)`` triple.
    Entries missing any of those fields are dropped silently — they
    are in-progress and cannot contribute statistically yet.
    """
    blob = json.loads(Path(path).read_text())
    entries = blob.get("entries", {})
    # Phase 2 hardening (ledger v2.0.0): meta-analysis pools the same
    # measurement tiers as the substrate-diversity report — VALIDATED
    # plus pre-VALIDATED tiers (EVIDENCE_CANDIDATE, SUPPORTED_BY_NULLS,
    # VALIDATED_SUBSTRATE_EVIDENCE). Sub-γ statuses (LOCAL_STRUCTURAL_…,
    # BLOCKED_BY_…, NO_ADMISSIBLE_CLAIM) are excluded because they do
    # not emit a γ value.
    _MEASURED_STATUSES = {
        "VALIDATED",
        "VALIDATED_SUBSTRATE_EVIDENCE",
        "EVIDENCE_CANDIDATE",
        "SUPPORTED_BY_NULLS",
    }
    out: list[SubstrateResult] = []
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") not in _MEASURED_STATUSES:
            continue
        g = entry.get("gamma")
        lo = entry.get("ci_low")
        hi = entry.get("ci_high")
        if g is None or lo is None or hi is None:
            continue
        n_val = entry.get("n_pairs") or entry.get("n") or 0
        out.append(
            SubstrateResult(
                name=str(key),
                gamma=float(g),
                ci_lower=float(lo),
                ci_upper=float(hi),
                n=int(n_val),
            )
        )
    return out


def load_from_xform_combined(path: str | Path) -> list[SubstrateResult]:
    """Parse ``xform_combined_gamma_report.json`` into substrate rows.

    Each top-level ``results`` slice (ALL, PRODUCTIVE, CHATGPT_*, ODT_*)
    becomes a ``SubstrateResult`` named ``xform::<slice>``. These are
    corpus-analysis gammas, not physical substrates — include only via
    the ``--include-xform`` CLI flag for sensitivity analysis.
    """
    blob = json.loads(Path(path).read_text())
    results = blob.get("results", {})
    out: list[SubstrateResult] = []
    for slice_name, r in results.items():
        if not isinstance(r, dict):
            continue
        try:
            g = float(r["gamma"])
            lo = float(r["ci_low"])
            hi = float(r["ci_high"])
            n = int(r.get("n", 0))
        except (KeyError, TypeError, ValueError):
            continue
        out.append(
            SubstrateResult(
                name=f"xform::{slice_name}",
                gamma=g,
                ci_lower=lo,
                ci_upper=hi,
                n=n,
            )
        )
    return out


# ── formatting ────────────────────────────────────────────────────────


def format_report(bundle: ProofBundle) -> str:
    """Render a proof bundle as a publication-ready plain-text table."""
    lines: list[str] = []
    bar = "=" * 78
    lines.append(bar)
    lines.append("GAMMA META-ANALYSIS -- proof of gamma ~ 1 invariant")
    lines.append(bar)
    lines.append(f"Substrates pooled: {bundle.n_substrates}")
    lines.append("")

    lines.append("Per-substrate estimates (forest plot):")
    lines.append(f"  {'name':30s} {'gamma':>8s}  {'95% CI':>19s}  {'w_fe':>6s}  {'w_re':>6s}")
    for r in bundle.forest:
        lines.append(
            f"  {r.name[:30]:30s} "
            f"{r.gamma:8.4f}  "
            f"[{r.ci_lower:6.3f}, {r.ci_upper:6.3f}]  "
            f"{r.weight_fixed_pct:5.1f}% "
            f"{r.weight_random_pct:5.1f}%"
        )
    lines.append("")

    lines.append("Pooled estimates:")
    for m in (bundle.fixed, bundle.random):
        tail = f"  tau^2 = {m.tau2:.4g}" if m.model == "random" else ""
        lines.append(
            f"  {m.model:<8s} gamma = {m.gamma:.4f}  "
            f"95% CI [{m.ci_lower:.4f}, {m.ci_upper:.4f}]  "
            f"SE = {m.se:.4f}  z = {m.z:+.3f}  "
            f"p(H0: gamma=1) = {m.p_value:.4g}" + tail
        )
    lines.append("")

    h = bundle.heterogeneity
    lines.append(
        f"Heterogeneity:  Q = {h.Q:.3f} (df={h.df}), "
        f"p = {h.p_heterogeneity:.4g},  "
        f"I^2 = {h.I2:.1f}%,  H^2 = {h.H2:.3f}"
    )
    pi_lo, pi_hi = bundle.prediction_interval
    lines.append(f"95% prediction interval:  [{pi_lo:.4f}, {pi_hi:.4f}]")
    lines.append("")

    lines.append("VERDICT: " + bundle.verdict)
    if bundle.verdict_reasons:
        for reason in bundle.verdict_reasons:
            lines.append(f"  - {reason}")
    else:
        lines.append("  - pooled random-effects CI contains 1.0")
        lines.append("  - I^2 < 75%")
        lines.append("  - 95% prediction interval contains 1.0")
    lines.append(bar)
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ledger",
        default="evidence/gamma_ledger.json",
        help="path to the canonical gamma ledger (primary data source)",
    )
    p.add_argument(
        "--xform",
        default="xform_combined_gamma_report.json",
        help="path to xform corpus gamma report (opt-in)",
    )
    p.add_argument(
        "--include-xform",
        action="store_true",
        help="also include xform corpus slices (sensitivity analysis)",
    )
    args = p.parse_args(argv)

    substrates = load_from_gamma_ledger(args.ledger)
    if args.include_xform:
        substrates += load_from_xform_combined(args.xform)

    if len(substrates) < 2:
        print(
            f"need >= 2 substrates for meta-analysis; got {len(substrates)}",
            file=sys.stderr,
        )
        return 2

    analysis = GammaMetaAnalysis(substrates)
    bundle = analysis.run_full_analysis()
    print(format_report(bundle))
    return 0 if bundle.verdict == "INVARIANT_CONFIRMED" else 1


if __name__ == "__main__":
    sys.exit(main())
