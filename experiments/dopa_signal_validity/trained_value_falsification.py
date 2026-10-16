"""H4: held-out synthetic claim-utility prediction, not DNCA or real verification.

The exact dopamine value_net topology is trained as a *supervised predictor*.
Reward prediction residual is computed AFTER outcomes; it cannot route that claim.
No claim of TD learning, independent oracle receipts, or total-compute parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn


@dataclass(frozen=True)
class Plan:
    train_n: int = 1200
    validation_n: int = 320
    test_groups: int = 24
    candidates: int = 16
    slots: int = 4
    dimensions: int = 8
    hidden: int = 32
    epochs: int = 55
    seed: int = 731

    def __post_init__(self) -> None:
        ints = (self.train_n, self.validation_n, self.test_groups,
                self.candidates, self.slots, self.dimensions,
                self.hidden, self.epochs, self.seed)
        if any(type(v) is not int for v in ints):
            raise ValueError("noninteger_plan")
        if not (200 <= self.train_n <= 20000 and 80 <= self.validation_n <= 10000
                and 4 <= self.test_groups <= 500 and 3 <= self.candidates <= 100
                and 1 <= self.slots < self.candidates and self.dimensions >= 4
                and 8 <= self.hidden <= 512 and 1 <= self.epochs <= 300
                and 0 <= self.seed < 2**32):
            raise ValueError("invalid_plan")


def _make_data(n: int, seed: int, d: int) -> tuple[torch.Tensor, torch.Tensor]:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, d)).astype(np.float32)
    # Only the synthetic oracle sees this generation mechanism.
    z = 0.40 * x[:, 0] + 1.25 * x[:, 1] - 1.10 * x[:, 2] - 0.10
    p = 1.0 / (1.0 + np.exp(-z))
    y = rng.binomial(1, p).astype(np.float32)
    return torch.from_numpy(x), torch.from_numpy(y)


def _network(d: int, hidden: int) -> nn.Module:
    # Same layer types and relative shape as DopamineOperator.value_net.
    return nn.Sequential(nn.Linear(d, hidden // 2), nn.GELU(),
                         nn.Linear(hidden // 2, 1))


def _fit(model: nn.Module, x_train: torch.Tensor, y_train: torch.Tensor,
         x_val: torch.Tensor, y_val: torch.Tensor, epochs: int) -> tuple[float, float]:
    optimizer = torch.optim.Adam(model.parameters(), lr=0.02)
    criterion = nn.BCEWithLogitsLoss()
    best = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    start = time.perf_counter_ns()
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(x_train).flatten(), y_train)
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            val = float(torch.mean((torch.sigmoid(model(x_val).flatten()) - y_val)**2))
        if val < best:
            best, best_state = val, {k: v.detach().clone() for k, v in model.state_dict().items()}
    assert best_state is not None
    model.load_state_dict(best_state)
    model.eval()
    return (time.perf_counter_ns() - start) / 1e9, best


def _scores(model: nn.Module, x: torch.Tensor) -> tuple[np.ndarray, float]:
    begin = time.perf_counter_ns()
    with torch.no_grad():
        values = torch.sigmoid(model(x).flatten()).cpu().numpy().astype(float)
    elapsed = (time.perf_counter_ns() - begin) / 1e9
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError("nonfinite_or_out_of_range_prediction")
    return values, elapsed


def _model_sha(model: nn.Module) -> str:
    # State dictionary deterministically encodes tensors, names, dtypes, shapes.
    h = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        raw = value.detach().cpu().contiguous().numpy()
        h.update(name.encode());h.update(str(raw.dtype).encode())
        h.update(str(raw.shape).encode());h.update(raw.tobytes())
    return h.hexdigest()


def _selection(scores: np.ndarray, groups: int, n: int, k: int) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(sorted(range(g*n, (g+1)*n), key=lambda i:(-scores[i],i))[:k])
                 for g in range(groups))


def _utility(chosen: tuple[tuple[int, ...], ...], y: torch.Tensor) -> float:
    # Labels are used only in evaluation, never in score construction or selection.
    return float(np.mean([sum(int(y[i].item()) for i in selected) for selected in chosen]))


def _brier(scores: np.ndarray, labels: torch.Tensor) -> float:
    return float(np.mean((scores-labels.detach().numpy())**2))


def run(plan: Plan = Plan()) -> dict[str, object]:
    torch.set_num_threads(1)
    random.seed(plan.seed);np.random.seed(plan.seed);torch.manual_seed(plan.seed)
    xt, yt = _make_data(plan.train_n, plan.seed+101, plan.dimensions)
    xv, yv = _make_data(plan.validation_n, plan.seed+202, plan.dimensions)
    xh, yh = _make_data(plan.test_groups*plan.candidates, plan.seed+303, plan.dimensions)
    # Train / validation / held-out test sources are disjoint deterministic seeds.
    inputs_hashes = {name: hashlib.sha256(x.numpy().tobytes()+y.numpy().tobytes()).hexdigest()
                     for name,(x,y) in {"train":(xt,yt),"validation":(xv,yv),"test":(xh,yh)}.items()}
    network = _network(plan.dimensions, plan.hidden)
    untrained = _network(plan.dimensions, plan.hidden)
    untrained.load_state_dict(network.state_dict())  # exact untrained ablation
    torch.manual_seed(plan.seed+1)
    shuffled_model = _network(plan.dimensions, plan.hidden)
    full_linear = nn.Linear(plan.dimensions,1)
    baseline_linear = nn.Linear(1,1)
    rng = torch.Generator().manual_seed(plan.seed+404)
    shuffled_labels = yt[torch.randperm(len(yt),generator=rng)]
    shuffled_val_labels = yv[torch.randperm(len(yv),generator=rng)]
    models = {"trained_value_net":(network,xt,xv,yt,yv),
              "untrained_value_net":(untrained,None,None,None,None),
              "shuffled_reward_net":(shuffled_model,xt,xv,shuffled_labels,shuffled_val_labels),
              "full_linear":(full_linear,xt,xv,yt,yv),
              "one_feature_linear":(baseline_linear,xt[:,:1],xv[:,:1],yt,yv)}
    result: dict[str, dict[str, object]] = {}
    # Freeze and evaluate held-out scores before consulting held-out rewards.
    frozen_choices: dict[str, tuple[tuple[int,...],...]] = {}
    for name,(model,xtrain,xval,ytrain,yval) in models.items():
        if xtrain is not None:
            duration, best_val = _fit(model,xtrain,ytrain,xval,yval,plan.epochs)
        else:
            duration, best_val = 0.0,None
        pred, infer_s = _scores(model,xh[:,:1] if name=="one_feature_linear" else xh)
        frozen_choices[name] = _selection(pred,plan.test_groups,plan.candidates,plan.slots)
        result[name] = {"checkpoint_sha256":_model_sha(model),
                        "validation_brier":best_val,
                        "heldout_brier":_brier(pred,yh),
                        "train_seconds":duration,"inference_seconds":infer_s,
                        "mean_beneficial_choices_per_group":None}
    oracle = yh.numpy().astype(float)
    oracle_selected = _selection(oracle,plan.test_groups,plan.candidates,plan.slots)
    for name,choices in frozen_choices.items():
        result[name]["mean_beneficial_choices_per_group"] = _utility(choices,yh)
    # Post-outcome residual: terminal transition delta=r-V(s); NEVER a selection cue.
    # This is NOT the running DNCA DopamineOperator's gamma=0.99 TD signal.
    brier_best = float(result["trained_value_net"]["heldout_brier"])
    report: dict[str,object] = {
      "protocol":"H4_SUPERVISED_VALUE_PROOF_OF_INSTRUMENT_v1",
      "scientific_verdict":"INADMISSIBLE_SYNTHETIC_ORACLE_NO_ACTUAL_DNCA",
      "claim":"SUPERVISED_CLASSIFIER_NOT_TEMPORAL_DIFFERENCE_LEARNING",
      "plan":asdict(plan),"dataset_sha256":inputs_hashes,
      "models":result,
      "oracle_ceiling_beneficial_choices_per_group":_utility(oracle_selected,yh),
      "test_event_count":len(yh),
      "terminal_post_outcome_residual_rmse":math.sqrt(brier_best),
      "residual_available_for_same_claim_routing":False,
      "cost_comparability":"UNMATCHED_MODEL_TRAINING_AND_INFERENCE;SLOTS_ONLY_MATCHED",
      "torch_version":torch.__version__,"numpy_version":np.__version__,
      "python":platform.python_version(),
      "limitations":["synthetic labels not independent real verifier receipts",
       "value predictor trained supervised on synthetic benefit, not TD trajectories",
       "different models use different training/inference times; no equal total compute",
       "one outcome sample per synthetic claim, no causal attribution to DNCA",
       "post-outcome residual not available before verifying same claim"]
    }
    digest = json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
    report["report_sha256_without_digest"] = hashlib.sha256(digest).hexdigest()
    return report


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise FileExistsError("output_already_exists")
    record=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(record,f,indent=2,sort_keys=True,default=str,allow_nan=False)
        f.write("\n")
    print(json.dumps({"scientific_verdict":record["scientific_verdict"],
                      "sha256":record["report_sha256_without_digest"]}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
