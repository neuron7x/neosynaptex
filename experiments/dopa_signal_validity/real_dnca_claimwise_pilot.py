"""Exploratory actual-DNCA per-claim probe with oracle-blind inference.

This is NOT an admissible test of DNCA verification utility: weights are
randomly initialized and synthetic benefits are not external ground truth.
If torch or DNCA is unavailable, fail explicitly instead of faking cues.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from core.eai.dnca_first_step_contract import assert_one_step_zero_reward_construct
from core.eai.dnca_claimwise_evaluator import ClaimEvidence, StudyPlan, evaluate
from core.eai.dnca_signal_identifiability import paired_claimwise_probe


@dataclass(frozen=True)
class ProbeConfig:
    seeds: tuple[int, ...] = (31, 37, 41, 43)
    candidates: int = 12
    state_dim: int = 16
    hidden_dim: int = 32
    slots: int = 4
    model_seed: int = 20261016

    def __post_init__(self) -> None:
        if self.candidates < 3 or self.candidates > 128:
            raise ValueError("invalid_candidates")
        if self.state_dim < 8 or self.state_dim % 2:
            raise ValueError("invalid_state_dim")
        if self.hidden_dim < 16 or self.hidden_dim % 2:
            raise ValueError("invalid_hidden_dim")
        if not 0 < self.slots < self.candidates:
            raise ValueError("invalid_slots")
        if not self.seeds or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("invalid_seeds")
        if type(self.model_seed) is not int or not 0 <= self.model_seed < 2**63:
            raise ValueError("invalid_model_seed")
        if any(type(seed) is not int or not 0 <= seed < 2**63 for seed in self.seeds):
            raise ValueError("invalid_data_seeds")


def make_cases(seed: int, config: ProbeConfig) -> tuple[list[tuple[float,...]], list[float], list[int]]:
    """Synthetic feature/label mechanism; the model never receives labels."""
    rng = random.Random(seed)
    features: list[tuple[float,...]] = []
    baselines: list[float] = []
    hidden_labels: list[int] = []
    for _ in range(config.candidates):
        x = tuple(rng.gauss(0.0, 0.45) for _ in range(config.state_dim))
        features.append(x)
        baselines.append(1.0 / (1.0 + math.exp(-x[0])))
        hidden_labels.append(int(x[1] + x[2] + rng.gauss(0, 0.3) > 0.0))
    return features, baselines, hidden_labels


def collect_real_dnca_cues(
    features: list[tuple[float, ...]], *, seed: int, config: ProbeConfig
) -> tuple[list[float], int, str]:
    """Fresh *untrained* same-weight DNCA per claim; reward=0, no labels.

    One step avoids cross-claim learning, but makes valence exactly a clipped
    random value projection (gamma*V(x)), NOT trained reward prediction error.
    Assert that construct identity on every real claim or fail closed.
    """
    try:
        import torch
        from neuron7x_agents.dnca.orchestrator import DNCA
        from core.eai.dnca_modulated_router import observe_sps
    except ImportError as exc:
        raise RuntimeError("real_dnca_and_torch_required_no_proxy_fallback") from exc

    cues: list[float] = []
    total_ns = 0
    for x in features:
        if len(x) != config.state_dim or not all(math.isfinite(v) for v in x):
            raise ValueError("invalid_claim_sensory_features")
        t0 = time.perf_counter_ns()
        model = DNCA(state_dim=config.state_dim, hidden_dim=config.hidden_dim,
                     device="cpu", seed=seed)
        model.eval()
        input_tensor = torch.tensor(x, dtype=torch.float32)
        dopamine = model.operators["dopamine"]
        prior_value = float(dopamine._prev_value)
        discount = float(model.sps.temporal_discount.item())
        with torch.no_grad():
            raw_value = float(dopamine.value_net(input_tensor).item())
            model.step(input_tensor, reward=0.0)
        observation = observe_sps(model.sps.snapshot())
        assert_one_step_zero_reward_construct(
            current_value=raw_value,
            observed_valence=observation.signed_valence,
            discount=discount, previous_value=prior_value, reward=0.0,
        )
        elapsed = time.perf_counter_ns() - t0
        if observation.step != 1:
            raise RuntimeError("unexpected_dnca_step_count")
        total_ns += elapsed
        cues.append(observation.signed_valence)
    return cues, total_ns, str(torch.__version__)


def _content_hash(value: object) -> str:
    """Stable canonical payload digest (integrity only, never authenticity)."""
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def execute_pilot(config: ProbeConfig = ProbeConfig()) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    adjudication_rows: list[ClaimEvidence] = []
    for seed in config.seeds:
        features, proxy, hidden_labels = make_cases(seed, config)
        # Strict blindness: collect_real_dnca_cues accepts features only, not labels.
        cues, elapsed_ns, torch_version = collect_real_dnca_cues(
            features, seed=config.model_seed, config=config
        )
        analysis = paired_claimwise_probe(proxy, cues, hidden_labels,
                                          config.slots, seed=seed + 41)
        for i, (base, cue, label) in enumerate(zip(proxy, cues, hidden_labels)):
            adjudication_rows.append(ClaimEvidence(
                group_id=str(seed),
                claim_id=str(i),
                baseline=float(base),
                signed_valence=float(cue),
                oracle_benefit_label=int(label),
                oracle_receipt_sha256="",  # Synthetic target, no independent receipt.
            ))
        rows.append({
            "data_seed": seed,
            "model_seed": config.model_seed,
            "torch_version": torch_version,
            "measured_dnca_init_plus_step_ns": elapsed_ns,
            "analysis": analysis,
            "cue_min": min(cues),
            "cue_max": max(cues),
            "cue_values": cues,
            "sensory_inputs_sha256": _content_hash(features),
            "withheld_utility_sha256": _content_hash(hidden_labels),
            "cue_values_sha256": _content_hash(cues),
        })
    # Four or more independently seeded groups are required for this
    # descriptive resampling diagnostic. No label can reach DNCA inference.
    if len(config.seeds) >= 4:
        prequential: dict[str, object] = evaluate(
            adjudication_rows, StudyPlan(slots=config.slots, gain=0.25)
        )
    else:
        prequential = {"status": "UNTESTED_INSUFFICIENT_GROUPS",
                       "n_groups": len(config.seeds)}
    data: dict[str, object] = {
        "protocol": "REAL_DNCA_UNTRAINED_CLAIMWISE_PILOT_v1",
        "prequential_diagnostic": prequential,
        "verdict": "INSTRUMENT_INADMISSIBLE_UNTRAINED_SIGNAL",
        "model_weights": "FRESH_FIXED_SEED_RANDOM_INITIALIZATION_NOT_TRAINED",
        "signal_construct": "CLIPPED_GAMMA_TIMES_RANDOM_VALUE_NET_NOT_TD_LEARNING",
        "first_step_identity_gate": "ENFORCED_PER_REAL_CLAIM",
        "task": "SYNTHETIC_BINARY_UTILITY_NOT_GENERAL_FACTUAL_VERIFICATION",
        "config": asdict(config),
        "runs": rows,
        "notes": [
            "model seed fixed across data groups; DNCA reinitialized for each claim",
            "first-step valence is clipped gamma*random_V(input), NOT temporal learning",
            "no reward or access to withheld utility",
            "fixed slots across arms; wall time includes DNCA initialization",
            "actual verifier receipts, CPU/energy metering and calibrated value model absent",
            "positive result must never promote scientific validity",
        ],
    }
    data["sha256"] = hashlib.sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    if options.output.exists():
        raise FileExistsError("evidence_output_already_exists")
    result = execute_pilot()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    with options.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
    print(json.dumps({"verdict": result["verdict"],
                      "sha256": result["sha256"],
                      "output": str(options.output)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
