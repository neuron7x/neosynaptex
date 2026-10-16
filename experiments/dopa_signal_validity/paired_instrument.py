"""Synthetic positive/null controls for *instrument sensitivity*, not DNCA efficacy.

Preregistered policy allocation: identical candidate sets and exactly k routing
slots for all arms. Oracle labels are withheld from policy selection. The fixture
may intentionally generate informative or null cues; it is NOT a real DNCA cue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrialConfig:
    trials: int = 128
    candidates: int = 128
    slots: int = 16
    gain: float = 0.25
    seed: int = 7301

    def __post_init__(self) -> None:
        if not (4 <= self.trials <= 10000):
            raise ValueError("trials must lie in [4,10000]")
        if not (2 <= self.candidates <= 10000):
            raise ValueError("candidates must lie in [2,10000]")
        if not (1 <= self.slots < self.candidates):
            raise ValueError("slots must be positive and less than candidates")
        if not (0.0 <= self.gain <= 0.25):
            raise ValueError("gain must lie in [0,0.25]")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")


@dataclass(frozen=True)
class Candidate:
    claim_id: int
    uncertainty_proxy: float
    cue: float
    verification_benefit: int  # oracle-only; no policy may inspect


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def generate_trial(rng: random.Random, n: int, informative: bool) -> list[Candidate]:
    """Synthetic classifier features; cue reliability is controlled by fixture."""
    rows: list[Candidate] = []
    for claim_id in range(n):
        y = int(rng.random() < 0.35)
        proxy = _clamp(0.5 + (0.12 if y else -0.12) + rng.gauss(0, 0.30), 0, 1)
        cue = (_clamp((0.65 if y else -0.65) + rng.gauss(0, 0.50), -1, 1)
               if informative else rng.uniform(-1, 1))
        rows.append(Candidate(claim_id, proxy, cue, y))
    return rows


def selected_indices(rows: list[Candidate], scores: list[float], k: int) -> tuple[int, ...]:
    if len(rows) != len(scores):
        raise ValueError("score count does not match candidates")
    # Stable, label-blind selection. Outcome labels must not enter scores.
    return tuple(sorted(range(len(rows)), key=lambda i: (-scores[i], rows[i].claim_id))[:k])


def _outcomes(rows: list[Candidate], scores: list[float], k: int) -> int:
    # Only the evaluator sees oracle labels, after the selection is committed.
    chosen = selected_indices(rows, scores, k)
    return sum(rows[i].verification_benefit for i in chosen)


def run_trial(rng: random.Random, config: TrialConfig, informative: bool) -> dict[str, int]:
    rows = generate_trial(rng, config.candidates, informative)
    proxy = [r.uncertainty_proxy for r in rows]
    cue = [r.cue for r in rows]
    permuted = cue[:]
    rng.shuffle(permuted)
    random_scores = [rng.random() for _ in rows]
    return {
        "uncertainty_only": _outcomes(rows, proxy, config.slots),
        "modulated": _outcomes(rows, [p + config.gain * s for p, s in zip(proxy, cue)], config.slots),
        "permuted": _outcomes(rows, [p + config.gain * s for p, s in zip(proxy, permuted)], config.slots),
        "sign_reversed": _outcomes(rows, [p - config.gain * s for p, s in zip(proxy, cue)], config.slots),
        "random": _outcomes(rows, random_scores, config.slots),
        "oracle_ceiling": _outcomes(rows, [float(r.verification_benefit) for r in rows], config.slots),
    }


def _mean(values: list[float]) -> float:
    return statistics.fmean(values)


def _paired_ci(values: list[float], seed: int) -> list[float]:
    """Seeded paired percentile bootstrap; inferential illustration only."""
    rng = random.Random(seed)
    n = len(values)
    means = sorted(_mean([values[rng.randrange(n)] for _ in range(n)]) for _ in range(1000))
    return [means[24], means[975]]


def evaluate(config: TrialConfig = TrialConfig()) -> dict[str, object]:
    regimes: dict[str, object] = {}
    for condition in ("informative", "null"):
        rng = random.Random(config.seed + (0 if condition == "informative" else 1000003))
        trials = [run_trial(rng, config, condition == "informative") for _ in range(config.trials)]
        keys = list(trials[0])
        means = {key: _mean([t[key] for t in trials]) for key in keys}
        paired = [float(t["modulated"] - t["uncertainty_only"]) for t in trials]
        regimes[condition] = {
            "mean_verified_benefit_per_trial": means,
            "paired_gain_vs_uncertainty": _mean(paired),
            "paired_bootstrap_95pct": _paired_ci(paired, config.seed + (17 if condition == "informative" else 19)),
            "fixed_routing_slots_per_trial": config.slots,
        }
    out = {
        "protocol": "SYNTHETIC_CUE_INSTRUMENT_CHECK_v1",
        "scope": "INSTRUMENT_SENSITIVITY_ONLY_NOT_DNCA_VALIDITY",
        "config": asdict(config),
        "regimes": regimes,
        "caveats": [
            "informative cue was generated using oracle labels inside the simulator",
            "routing slots matched; signal generation, verifier CPU and LLM token costs not metered",
            "synthetic outcomes are not independently measured DNCA or task results",
            "bootstrap intervals describe simulation replicates, not external replication",
        ],
    }
    raw = json.dumps(out, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    out["payload_sha256"] = hashlib.sha256(raw).hexdigest()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate()
    raw = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Experimental output must not overwrite another evidence report.
        with args.output.open("x", encoding="utf-8") as file:
            file.write(raw)
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
