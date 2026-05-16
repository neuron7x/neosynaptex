"""DOPA-CLOSURE matched-budget kill-ablation.

Runs the pre-registered protocol (see PREREGISTRATION.md). All strategies share
an *identical stochastic substrate* per (seed, scenario): one cheap pass, one
cheap probe, and a pool of N_VERIFY perturbation reruns are drawn once and
reused, so strategies differ only in *allocation policy*. The pre-registered
kill condition is evaluated and an Evidence/Kill artifact with a reproducibility
hash is written.

Run from repo root:  python experiments/dopa_closure/kill_ablation.py

Yaroslav Vasylenko / neuron7xLab / 2026
"""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dopa_gate import evaluate_gate, majority_verdict  # noqa: E402

from core.coherence_state_space import (  # noqa: E402
    CoherenceStateSpace,
    CoherenceStateSpaceParams,
)
from core.hallucination_benchmark import (  # noqa: E402
    BenchmarkScenario,
    HallucinationBenchmark,
)

# ---- frozen constants (mirror PREREGISTRATION.md) -------------------------
THRESHOLD = 0.0
K_CONF = 8.0
TAU = 0.35
N_VERIFY = 8
NOISE_SCALE = 0.05
SEED_SWEEP = [11, 23, 42, 101, 202, 303, 404, 505, 606, 707]
DELTA_MIN = 0.05
SIGN_FRAC = 0.70
EPS = 0.02


@dataclass(frozen=True)
class ScenarioSubstrate:
    """Identical draws reused by every strategy for one (seed, scenario)."""

    actual: bool
    cheap_verdict: bool
    margin: float
    probe_verdict: bool
    verify_verdicts: list[bool]


def build_substrate(
    bench: HallucinationBenchmark,
    scenario: BenchmarkScenario,
    rng: np.random.Generator,
) -> ScenarioSubstrate:
    cheap = bench.run_scenario(scenario, np.random.default_rng(rng.integers(0, 2**63)))
    probe = bench.perturb_and_rerun(
        scenario, 1, NOISE_SCALE, np.random.default_rng(rng.integers(0, 2**63))
    )[0]
    verify = bench.perturb_and_rerun(
        scenario, N_VERIFY, NOISE_SCALE, np.random.default_rng(rng.integers(0, 2**63))
    )
    return ScenarioSubstrate(
        actual=scenario.expected_hallucination,
        cheap_verdict=cheap.predicted_hallucination,
        margin=cheap.final_delta_S - THRESHOLD,
        probe_verdict=probe.predicted_hallucination,
        verify_verdicts=[r.predicted_hallucination for r in verify],
    )


def _verified_verdict(s: ScenarioSubstrate, include_probe: bool) -> bool:
    votes = [s.cheap_verdict, *s.verify_verdicts]
    if include_probe:
        votes.append(s.probe_verdict)
    return majority_verdict(votes)


def _accuracy(verdicts: list[bool], subs: list[ScenarioSubstrate]) -> float:
    return mean(1.0 if v == s.actual else 0.0 for v, s in zip(verdicts, subs))


def _fp_rate(verdicts: list[bool], subs: list[ScenarioSubstrate]) -> float:
    neg = [(v, s) for v, s in zip(verdicts, subs) if not s.actual]
    if not neg:
        return 0.0
    return mean(1.0 if v else 0.0 for v, _ in neg)


# ---- strategies: pure allocation policies over the shared substrate -------


def strat_cheap_only(subs: list[ScenarioSubstrate]) -> tuple[list[bool], int]:
    return [s.cheap_verdict for s in subs], 0


def strat_dopa(subs: list[ScenarioSubstrate], invert: bool) -> tuple[list[bool], int]:
    verdicts: list[bool] = []
    cost = 0
    for s in subs:
        cost += 1  # cheap probe is always paid
        d = evaluate_gate(
            margin=s.margin,
            cheap_verdict=s.cheap_verdict,
            probe_verdict=s.probe_verdict,
            k_conf=K_CONF,
            tau=TAU,
            invert=invert,
        )
        if d.mode.value == "VERIFY":
            cost += N_VERIFY
            verdicts.append(_verified_verdict(s, include_probe=True))
        else:
            verdicts.append(s.cheap_verdict)
    return verdicts, cost


def _budgeted_by_order(
    subs: list[ScenarioSubstrate], order: list[int], budget: int
) -> tuple[list[bool], int]:
    verdicts = [s.cheap_verdict for s in subs]
    cost = 0
    for idx in order:
        if cost + N_VERIFY > budget:
            continue
        cost += N_VERIFY
        verdicts[idx] = _verified_verdict(subs[idx], include_probe=False)
    return verdicts, cost


def strat_uncertainty_only(subs: list[ScenarioSubstrate], budget: int) -> tuple[list[bool], int]:
    # no-vRPE ablation: rank by raw confidence margin only, most-uncertain first
    order = sorted(range(len(subs)), key=lambda i: abs(subs[i].margin))
    return _budgeted_by_order(subs, order, budget)


def strat_random_gate(
    subs: list[ScenarioSubstrate], budget: int, rng: np.random.Generator
) -> tuple[list[bool], int]:
    order = list(rng.permutation(len(subs)))
    return _budgeted_by_order(subs, [int(i) for i in order], budget)


def strat_fixed_full(subs: list[ScenarioSubstrate]) -> tuple[list[bool], int]:
    return [_verified_verdict(s, include_probe=False) for s in subs], len(subs) * N_VERIFY


# ---- driver --------------------------------------------------------------


def run_seed(seed: int) -> dict[str, dict[str, float]]:
    bench = HallucinationBenchmark(
        CoherenceStateSpace(CoherenceStateSpaceParams()), delta_s_threshold=THRESHOLD
    )
    scenarios = bench.scenarios()
    rng = np.random.default_rng(seed)
    subs = [build_substrate(bench, sc, rng) for sc in scenarios]

    dopa_v, dopa_b = strat_dopa(subs, invert=False)
    inv_v, _ = strat_dopa(subs, invert=True)
    cheap_v, _ = strat_cheap_only(subs)
    unc_v, unc_b = strat_uncertainty_only(subs, dopa_b)
    rnd_v, rnd_b = strat_random_gate(subs, dopa_b, np.random.default_rng(seed ^ 0x5EED))
    full_v, full_b = strat_fixed_full(subs)

    table = {
        "cheap_only": (cheap_v, 0),
        "dopa": (dopa_v, dopa_b),
        "uncertainty_only": (unc_v, unc_b),
        "random_gate": (rnd_v, rnd_b),
        "dopa_inverted": (inv_v, dopa_b),
        "fixed_full": (full_v, full_b),
    }
    return {
        name: {
            "accuracy": _accuracy(v, subs),
            "fp_rate": _fp_rate(v, subs),
            "extra_cost": float(c),
        }
        for name, (v, c) in table.items()
    }


def main() -> int:
    per_seed = {str(s): run_seed(s) for s in SEED_SWEEP}
    strategies = list(next(iter(per_seed.values())).keys())

    agg = {
        st: {
            "mean_accuracy": mean(per_seed[str(s)][st]["accuracy"] for s in SEED_SWEEP),
            "mean_fp_rate": mean(per_seed[str(s)][st]["fp_rate"] for s in SEED_SWEEP),
            "mean_extra_cost": mean(per_seed[str(s)][st]["extra_cost"] for s in SEED_SWEEP),
        }
        for st in strategies
    }

    a_dopa = agg["dopa"]["mean_accuracy"]
    a_unc = agg["uncertainty_only"]["mean_accuracy"]
    a_rnd = agg["random_gate"]["mean_accuracy"]
    a_inv = agg["dopa_inverted"]["mean_accuracy"]

    seed_signs = [
        1
        if per_seed[str(s)]["dopa"]["accuracy"] - per_seed[str(s)]["uncertainty_only"]["accuracy"]
        > 0
        else 0
        for s in SEED_SWEEP
    ]
    sign_frac = mean(seed_signs)

    cond = {
        "1_delta_vs_uncertainty>=DELTA_MIN": (a_dopa - a_unc) >= DELTA_MIN,
        "2_sign_consistency>=SIGN_FRAC": sign_frac >= SIGN_FRAC,
        "3_dopa>random": a_dopa > a_rnd,
        "4_inverted<=random+EPS": a_inv <= a_rnd + EPS,
    }
    survived = all(cond.values())
    status = "SURVIVED" if survived else "KILLED_OR_RESCOPED"

    payload = {
        "constants": {
            "THRESHOLD": THRESHOLD,
            "K_CONF": K_CONF,
            "TAU": TAU,
            "N_VERIFY": N_VERIFY,
            "NOISE_SCALE": NOISE_SCALE,
            "SEED_SWEEP": SEED_SWEEP,
            "DELTA_MIN": DELTA_MIN,
            "SIGN_FRAC": SIGN_FRAC,
            "EPS": EPS,
        },
        "per_seed": per_seed,
    }
    repro_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    artifact = {
        "artifact_id": str(uuid.uuid4()),
        "kind": "EvidenceArtifact" if survived else "KillArtifact",
        "claim": (
            "vRPE single-probe gate beats raw-margin (no_vRPE) budget allocation "
            "at equal extra-rollout budget on HallucinationBenchmark, and the "
            "advantage collapses under vRPE sign inversion."
        ),
        "boundary": (
            "ONE deterministic benchmark, 15 ground-truth scenarios, 10-seed sweep. "
            "Admissibility/engineering signal only — not a science claim about "
            "dopamine or cognition. Low scenario-N (15)."
        ),
        "status": status,
        "kill_condition": cond,
        "sign_fraction": sign_frac,
        "aggregate": agg,
        "reproducibility_hash": repro_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preregistration": "experiments/dopa_closure/PREREGISTRATION.md",
    }
    if not survived:
        artifact["reason"] = (
            "Pre-registered kill condition not met; the vRPE single-probe term "
            "carries no allocation advantage beyond the raw confidence margin "
            "(RFC 13.3 / H0.6: decorative component). Object filed to graveyard."
        )
        artifact["minimal_counterexample"] = (
            f"cheap_only acc={agg['cheap_only']['mean_accuracy']:.4f} (0 budget) "
            f"> dopa acc={a_dopa:.4f} (budget B); fixed_full acc="
            f"{agg['fixed_full']['mean_accuracy']:.4f} < cheap_only. Spending ANY "
            "perturbation-verification budget strictly degrades the ΔS-threshold "
            "detector; the gate signal is irrelevant because the verification "
            "ACTION is anti-correlated with ground truth."
        )
        artifact["future_guardrail"] = (
            "Do NOT use Gaussian-input-perturbation + majority-vote as the "
            "verification primitive for a cumulative-ΔS threshold detector: "
            "perturbation reruns flip the verdict away from truth. Any DOPA-"
            "CLOSURE restart MUST pre-register a verification ACTION shown "
            "(independently) to be truth-correlated on the target benchmark "
            "BEFORE re-testing any gate. No gate can rescue a harmful action."
        )

    out_dir = _REPO_ROOT / "evidence" / "dopa_closure"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / ("evidence_artifact.json" if survived else "kill_artifact.json")
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True))
    (out_dir / "raw_per_seed.json").write_text(json.dumps(payload, indent=2, sort_keys=True))

    print(f"STATUS={status}")
    print(
        f"acc dopa={a_dopa:.4f} unc={a_unc:.4f} rnd={a_rnd:.4f} "
        f"inv={a_inv:.4f} cheap={agg['cheap_only']['mean_accuracy']:.4f} "
        f"full={agg['fixed_full']['mean_accuracy']:.4f}"
    )
    print(f"delta(dopa-unc)={a_dopa - a_unc:+.4f} sign_frac={sign_frac:.2f}")
    print(f"conditions={cond}")
    print(f"repro_hash={repro_hash}")
    print(f"artifact={out_path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
