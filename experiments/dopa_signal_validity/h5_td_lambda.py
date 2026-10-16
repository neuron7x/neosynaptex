"""H5 controlled stochastic-environment TD(lambda) study.

Actual sequential rollouts of a *software-simulated* P_env, NOT physical data.
Distinct, frozen train/validation/test episodes; reward audit independent of
prediction; neural and linear models share the same forward-view TD(lambda).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import time
from dataclasses import asdict, dataclass

import numpy as np
import torch
from torch import nn


@dataclass(frozen=True)
class Plan:
    train_episodes: int = 180
    validation_episodes: int = 48
    test_episodes: int = 64
    horizon: int = 12
    epochs: int = 55
    gamma: float = 0.95
    lam: float = 0.8
    learning_rate: float = 0.01
    seed: int = 1917

    def __post_init__(self) -> None:
        nums = (self.train_episodes, self.validation_episodes, self.test_episodes,
                self.horizon, self.epochs, self.seed)
        if any(type(v) is not int for v in nums):
            raise ValueError("invalid_integer_plan")
        if not (16 <= self.train_episodes <= 10000 and 8 <= self.validation_episodes <= 5000
                and 8 <= self.test_episodes <= 5000 and 2 <= self.horizon <= 128
                and 1 <= self.epochs <= 300 and 0 <= self.seed < 2**32):
            raise ValueError("invalid_plan")
        for name, val in (("gamma", self.gamma), ("lam", self.lam)):
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or not 0 <= val <= 1:
                raise ValueError(f"invalid_{name}")
        lr = self.learning_rate
        if isinstance(lr, bool) or not isinstance(lr, (int, float)) or not math.isfinite(lr) or not 0 < lr <= 0.1:
            raise ValueError("invalid_learning_rate")


@dataclass(frozen=True)
class Step:
    state: tuple[float, ...]
    action: int
    reward: float
    next_state: tuple[float, ...]
    done: bool


# Explicit stochastic transition kernel. Time-to-horizon is part of the state.
def augment(x: list[float], phase: float) -> tuple[float, ...]:
    """8D Markov feature layout; compatible with DNCA state_dim=8."""
    return tuple(x + [phase, x[0]**2, x[1]*x[2], x[3]**2])


def collect(seed: int, episodes: int, horizon: int) -> list[list[Step]]:
    rng = random.Random(seed)
    result = []
    for _ in range(episodes):
        x = [rng.uniform(-0.7, 0.7) for _ in range(4)]
        episode = []
        for t in range(horizon):
            state = augment(x, 1.0 - t / horizon)
            action = rng.randrange(2)
            disturbance = [rng.gauss(0, 0.13) for _ in range(4)]
            y = [
                math.tanh(0.7*x[0] + 0.3*x[1] + (2*action-1)*0.25 + disturbance[0]),
                math.tanh(0.8*x[1] - 0.2*x[2] + disturbance[1]),
                math.tanh(0.75*x[2] + 0.25*x[3] + disturbance[2]),
                math.tanh(0.8*x[3] + 0.12*x[0] + disturbance[3]),
            ]
            next_state = augment(y, 1.0 - (t + 1)/horizon)
            # Environment reward; independently recomputed by audit_oracle.
            reward = 0.6*math.sin(y[0] + 0.5*y[2]) + 0.5*y[1]**2 + 0.12*(2*action-1)*x[0] - 0.03
            episode.append(Step(state, action, reward, next_state, t == horizon-1))
            x = y
        result.append(episode)
    return result


def audit_oracle(trajectories: list[list[Step]]) -> str:
    """Independent reward formula and temporal contract, not external authority."""
    if not trajectories:
        raise ValueError("no_trajectories")
    for episode in trajectories:
        if len(episode) < 2:
            raise ValueError("invalid_episode_length")
        for i, step in enumerate(episode):
            if (len(step.state) != 8 or len(step.next_state) != 8 or
                    type(step.action) is not int or step.action not in (0, 1) or
                    type(step.done) is not bool):
                raise ValueError("invalid_transition_contract")
            if not all(math.isfinite(v) for v in (*step.state, *step.next_state, step.reward)):
                raise ValueError("nonfinite_transition")
            s, after, a = step.state, step.next_state, step.action
            # Recompute from stored transition, with no access to env RNG.
            recomputed = (0.6*math.sin(after[0]+after[2]/2.0)
                          + 0.5*after[1]*after[1]
                          + 0.12*(a+a-1)*s[0] - 0.03)
            if abs(recomputed - step.reward) > 1e-10:
                raise ValueError("reward_oracle_mismatch")
            if step.done != (i == len(episode)-1):
                raise ValueError("terminal_flag_mismatch")
            if i and any(abs(b-a) > 1e-12 for a,b in zip(episode[i-1].next_state, step.state)):
                raise ValueError("transition_chain_broken")
            if not 0 <= s[4] <= 1 or not 0 <= after[4] <= 1:
                raise ValueError("invalid_time_state")
    raw = json.dumps([[asdict(x) for x in ep] for ep in trajectories],
                     sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def separate_process_oracle(trajectories: list[list[Step]]) -> dict:
    """Recompute rewards in -I child Python with a minimal environment."""
    oracle_path=Path(__file__).with_name("h5_oracle.py").resolve()
    if not oracle_path.is_file():
        raise FileNotFoundError("oracle_source_missing")
    with tempfile.TemporaryDirectory(prefix="h5-oracle-") as directory:
        record=Path(directory)/"trajectories.json"
        raw=json.dumps([[asdict(st) for st in ep] for ep in trajectories],
                       sort_keys=True,separators=(",", ":"),allow_nan=False).encode()
        record.write_bytes(raw)
        proc=subprocess.run([sys.executable,"-I",str(oracle_path),"--input",str(record)],
            capture_output=True,text=True,timeout=20,check=False,
            env={"PATH":os.environ.get("PATH", ""),"PYTHONHASHSEED":"0"})
        if proc.returncode:
            raise ValueError("separate_oracle_rejected:"+proc.stderr[:500])
        receipt=json.loads(proc.stdout)
        if receipt.get("trajectory_sha256")!=hashlib.sha256(raw).hexdigest():
            raise ValueError("oracle_receipt_hash_mismatch")
        if receipt.get("transitions")!=sum(map(len,trajectories)):
            raise ValueError("oracle_receipt_count_mismatch")
        return receipt


def monte_carlo(episodes: list[list[Step]], gamma: float) -> torch.Tensor:
    values = []
    for episode in episodes:
        g = 0.
        seq=[]
        for st in reversed(episode):
            g = st.reward + gamma*g*(not st.done)
            seq.append(g)
        values.extend(reversed(seq))
    return torch.tensor(values, dtype=torch.float32)


def lambda_returns(episodes: list[list[Step]], bootstrap: torch.Tensor,
                   gamma: float, lam: float) -> torch.Tensor:
    """Forward-view episodic lambda-return computed backward from frozen V(next).

    For terminal: G=r. Otherwise: G=r+gamma*((1-lam)*V(s')+lam*G_next).
    """
    if bootstrap.ndim != 1 or len(bootstrap) != sum(map(len, episodes)):
        raise ValueError("bootstrap_shape_mismatch")
    if not torch.isfinite(bootstrap).all():
        raise ValueError("nonfinite_bootstrap")
    if not (0 <= gamma <= 1 and 0 <= lam <= 1):
        raise ValueError("invalid_discount_lambda")
    result=[]
    start=0
    for episode in episodes:
        vals=bootstrap[start:start+len(episode)]
        next_return=0.
        seq=[]
        for st,v in zip(reversed(episode), reversed(vals)):
            if st.done:
                g=st.reward
            else:
                g=st.reward + gamma*((1-lam)*float(v) + lam*next_return)
            seq.append(g)
            next_return=g
        result.extend(reversed(seq))
        start+=len(episode)
    return torch.tensor(result, dtype=torch.float32)


def _tensor(episodes: list[list[Step]], which: str) -> torch.Tensor:
    return torch.tensor([getattr(st,which) for ep in episodes for st in ep], dtype=torch.float32)


def _fit(model: nn.Module, train: list[list[Step]], val: list[list[Step]], p: Plan) -> tuple[nn.Module, dict]:
    sx, nx = _tensor(train,"state"), _tensor(train,"next_state")
    vx = _tensor(val,"state")
    vy = monte_carlo(val,p.gamma)
    opt=torch.optim.Adam(model.parameters(),lr=p.learning_rate)
    best=float("inf")
    best_state=None
    start=time.perf_counter_ns()
    for _ in range(p.epochs):
        model.eval()
        with torch.no_grad():
            frozen_next=model(nx).flatten().detach()
            target=lambda_returns(train,frozen_next,p.gamma,p.lam)
        model.train()
        opt.zero_grad(set_to_none=True)
        pred=model(sx).flatten()
        loss=torch.mean((pred-target)**2)
        if not torch.isfinite(loss):
            raise ValueError("nonfinite_training_loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),max_norm=2.)
        opt.step()
        model.eval()
        with torch.no_grad():
            val_loss=float(torch.mean((model(vx).flatten()-vy)**2))
        if val_loss < best:
            best=val_loss
            best_state={k:v.detach().clone() for k,v in model.state_dict().items()}
    if best_state is None:
        raise ValueError("no_valid_checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    return model, {"train_seconds":(time.perf_counter_ns()-start)/1e9,
                   "validation_mse":best}


def _sha_model(model: nn.Module) -> str:
    h=hashlib.sha256()
    for k,v in sorted(model.state_dict().items()):
        a=v.detach().cpu().contiguous().numpy()
        h.update(k.encode()); h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
    return h.hexdigest()


def _metrics(model: nn.Module, episodes: list[list[Step]], gamma: float) -> dict:
    x=_tensor(episodes,"state")
    tic=time.perf_counter_ns()
    with torch.no_grad():
        prediction=model(x).flatten()
    seconds=(time.perf_counter_ns()-tic)/1e9
    # Labels are materialized only after all ex-ante predictions are frozen.
    truth=monte_carlo(episodes,gamma)
    selected=[]
    oracle_ceiling=[]
    start=0
    for episode in episodes:
        n=len(episode); k=min(3,n)
        ids=range(start,start+n)
        picks=sorted(ids,key=lambda i:(-float(prediction[i]),i))[:k]
        ideal=sorted(ids,key=lambda i:(-float(truth[i]),i))[:k]
        selected.append(sum(float(truth[i]) for i in picks)/k)
        oracle_ceiling.append(sum(float(truth[i]) for i in ideal)/k)
        start+=n
    return {"holdout_top3_realized_return":sum(selected)/len(selected),
            "holdout_top3_oracle_ceiling":sum(oracle_ceiling)/len(oracle_ceiling),
            "holdout_return_mse":float(torch.mean((prediction-truth)**2)),
            "holdout_return_mae":float(torch.mean(torch.abs(prediction-truth))),
            "inference_seconds":seconds,
            "forward_MACs_upper_bound_per_state":sum(m.in_features*m.out_features for m in model.modules() if isinstance(m,nn.Linear)),
            "parameter_count":sum(q.numel() for q in model.parameters()),
            "parameter_bytes":sum(q.numel()*q.element_size() for q in model.parameters()),
            "checkpoint_sha256":_sha_model(model)}


def run(p:Plan=Plan()) -> dict:
    torch.set_num_threads(1)
    torch.manual_seed(p.seed)
    train=collect(p.seed+101,p.train_episodes,p.horizon)
    val=collect(p.seed+202,p.validation_episodes,p.horizon)
    test=collect(p.seed+303,p.test_episodes,p.horizon)
    dataset_hashes={k:audit_oracle(v) for k,v in (("train",train),("validation",val),("test",test))}
    receipts={k:separate_process_oracle(v) for k,v in (("train",train),("validation",val),("test",test))}
    if len(set(dataset_hashes.values()))!=3:
        raise ValueError("train_test_provenance_collision")
    models={"td_lambda_neural":nn.Sequential(nn.Linear(8,16),nn.GELU(),nn.Linear(16,1)),
            "td_lambda_linear":nn.Linear(8,1)}
    data={}
    for name,model in models.items():
        model,training=_fit(model,train,val,p)
        data[name]={**training,**_metrics(model,test,p.gamma)}
    # The next-state oracle outcome is *not* available before action/verification.
    report={"protocol":"H5_STOCHASTIC_SOFTWARE_ENV_TDLAMBDA_v1",
            "plan":asdict(p),"dataset_sha256":dataset_hashes,
            "oracle_subprocess_receipts":receipts,
            "trajectory_origin":"EXECUTED_STOCHASTIC_SOFTWARE_SIMULATOR_NOT_FIELD_DATA",
            "oracle":"SEPARATE_PROCESS_DETERMINISTIC_RECOMPUTATION",
            "oracle_external_independence":False,
            "model_outputs":"EX_ANTE_STATE_VALUE_ONLY",
            "reward_leakage_into_action_selection":False,
            "td_lambda_targets":"FROZEN_NEXT_VALUE_PER_EPOCH",
            "policies_cost_matched":False,
            "scientific_verdict":"INSTRUMENT_PROTOTYPE_ONLY_REAL_ENV_AND_DNCA_UNTESTED",
            "models":data,"torch_version":torch.__version__,
            "limitations":["simulator rollouts not measured real-world trajectories",
                "no OS-isolated verifier or independently authenticated environmental rewards",
                "model trained offline but not installed into live DNCA",
                "training cost and inference cost measured but not matched"]}
    return report


def prepare_frozen_value_checkpoint(p: Plan = Plan()):
    """In-memory safe tensor handoff, no pickle; no access to test episodes.

    This is a software-environment trained predictor, not a qualified field oracle.
    """
    torch.set_num_threads(1)
    torch.manual_seed(p.seed)
    train=collect(p.seed+101,p.train_episodes,p.horizon)
    val=collect(p.seed+202,p.validation_episodes,p.horizon)
    train_receipt=separate_process_oracle(train)
    val_receipt=separate_process_oracle(val)
    network=nn.Sequential(nn.Linear(8,16),nn.GELU(),nn.Linear(16,1))
    network,metadata=_fit(network,train,val,p)
    weights={key:val.detach().cpu().clone() for key,val in network.state_dict().items()}
    return weights,_sha_model(network),{"training":metadata,"train_receipt":train_receipt,
        "validation_receipt":val_receipt,"domain":"STOCHASTIC_SOFTWARE_ENV_NOT_FIELD_DATA"}
