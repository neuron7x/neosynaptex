"""Replay 8 held-out synthetic studies; emit stable summary and evidence digest.

No inference on real DNCA or claim that model training costs are equal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.dopa_signal_validity.trained_value_falsification import Plan, run

SEEDS = (731, 1031, 1331, 1631, 1931, 2231, 2531, 2831)


def replay() -> dict[str, object]:
    rows = [run(Plan(seed=seed)) for seed in SEEDS]
    model_summary: dict[str, dict[str, object]] = {}
    for name in rows[0]["models"]:
        brier = [float(r["models"][name]["heldout_brier"]) for r in rows]
        selected = [float(r["models"][name]["mean_beneficial_choices_per_group"]) for r in rows]
        model_summary[name] = {
            "mean_brier": float(np.mean(brier)),
            "mean_useful_of_four": float(np.mean(selected)),
            "per_seed_brier": brier,
            "per_seed_utility": selected,
            "checkpoints_sha256": [r["models"][name]["checkpoint_sha256"] for r in rows],
        }
    v = np.asarray(model_summary["trained_value_net"]["per_seed_utility"])
    l = np.asarray(model_summary["full_linear"]["per_seed_utility"])
    u = np.asarray(model_summary["untrained_value_net"]["per_seed_utility"])
    paired = v - l
    rng = np.random.default_rng(20261016)
    bootstrap = [float(paired[rng.integers(0, len(paired), len(paired))].mean())
                 for _ in range(4000)]
    stable = {
        "protocol": "H4_SUPERVISED_VALUE_EIGHT_REPLICATE_CONTROL_v2",
        "scientific_verdict": "SYNTHETIC_ONLY_REAL_DNCA_TD_UNTESTED",
        "seeds": list(SEEDS),
        "model_summary": model_summary,
        "paired_value_minus_linear_per_seed": paired.tolist(),
        "mean_value_minus_linear": float(paired.mean()),
        "mean_value_minus_untrained": float((v-u).mean()),
        "descriptive_seed_bootstrap_95pct": [float(np.quantile(bootstrap, 0.025)),
                                              float(np.quantile(bootstrap, 0.975))],
        "dataset_sha256_by_seed": [r["dataset_sha256"] for r in rows],
        "cost_status": "SLOTS_MATCHED_TOTAL_TRAIN_INFERENCE_NOT_MATCHED",
        "oracle_receipts_verified": False,
        "post_outcome_td_used_for_same_claim_routing": False,
        "caveat": "synthetic prospective utility prediction is not real DNCA TD or external replication",
    }
    raw = json.dumps(stable, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    stable["sha256_before_digest"] = hashlib.sha256(raw).hexdigest()
    return stable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("evidence_path_must_not_exist")
    result = replay()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, sort_keys=True, allow_nan=False)
        fp.write("\n")
    print(json.dumps({"digest": result["sha256_before_digest"],
                      "verdict": result["scientific_verdict"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
