"""DOPA-VALIDITY-001 — construct-validity gate for DNCA/dopamine routing.

This is NOT a test of the DOPA-CLOSURE theory. It is the *machine that prevents
an invalid instrument from pretending it tested the theory*. It re-implements,
honestly, the question PR #198/#199 only pretended to ask
(evidence/dopa_closure/RETRACTION.md is authoritative):

    Can an *actual* DNCA/dopamine-derived signed vRPE predict verification
    benefit better than uncertainty/margin, under an admissible verifier and a
    true sign-flip negative control?

Decision logic (pre-registered — see docs/experiments/DOPA_VALIDITY_001_PREREGISTRATION.md):

    Step A  DNCA/dopamine signal must be *executable* (real import + forward),
            else INADMISSIBLE_MISSING_DNCA_EXECUTABLE_SIGNAL.
    Step B1 The verification action must beat majority AND random baselines,
            else INADMISSIBLE_WEAK_VERIFIER.
    Step B2 The routed signal (-vRPE) must be truth-correlated with
            verification benefit (Spearman) BEFORE any routing comparison —
            fail-closed and INDEPENDENT: on a seed band disjoint from the
            Step-D draws, significant + positive on EVERY seed. Else
            INADMISSIBLE_WEAK_VERIFIER (RETRACTION precondition #3: a fragile
            or non-independent gate may not license a destructive verdict).
    Step C  Verified-Closure Rate must NOT collapse to plain policy accuracy,
            else INADMISSIBLE_METRIC_COLLAPSE.
    Step D  Only now: 6-policy routing test under equal budget with a paired
            significance test. SURVIVED_INITIAL iff dopa beats uncertainty_only
            by the pre-registered delta, p < alpha, the *true* sign-flip control
            loses its advantage, and the verifier stays above baseline.
            Otherwise KILLED — scoped strictly to this implementation.

A clean INADMISSIBLE verdict is the designed success mode. The scaffold never
fabricates a kill and never rescues the theory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray
from scipy import stats

from experiments import dopa_validity_001_config as cfg

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

SIGNED_VRPE_DEFINITION: Final[str] = (
    "DopamineOperator.modulate(...)['valence'] = clamp(delta, -1, 1) where "
    "delta = r + gamma*V(s_t) - V(s_{t-1}) is the temporal-difference "
    "prediction error BEFORE the Schultz asymmetric gain. Sign is preserved; "
    "the negative control negates this signed scalar (vRPE -> -vRPE), it is "
    "NOT a complement of |vRPE|."
)

VERIFIED_CLOSURE_DEFINITION: Final[str] = (
    "A Verified-Closure event = the independent deterministic verifier spent a "
    "budgeted verification action on an item AND returned a definitive "
    "VERIFIED/REFUTED outcome bound to an evidence hash under a fixed boundary "
    "(pure recomputation, network disabled). VCR = (closure events) / (items). "
    "It is distinct from policy label accuracy: VCR counts independent "
    "verifier-confirmed closures, not whether the policy's own label was right."
)


# --------------------------------------------------------------------------
# Step A — executable DNCA/dopamine signal
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DopamineHandle:
    operator: Any
    torch_mod: Any


def load_dopamine_operator() -> DopamineHandle | None:
    """Import and forward-run the *actual* DNCA DopamineOperator.

    Returns ``None`` iff the signal is not executable — the scaffold then
    emits INADMISSIBLE_MISSING_DNCA_EXECUTABLE_SIGNAL rather than faking it.
    """
    try:
        import torch  # noqa: PLC0415 — optional heavy dep, gated on purpose
        from neuron7x_agents.dnca.neuromodulators.dopamine import (  # noqa: PLC0415
            DopamineOperator,
        )
    except Exception:  # pragma: no cover - environment-dependent
        return None

    try:
        torch.manual_seed(cfg.SEED)
        op = DopamineOperator(state_dim=cfg.STATE_DIM, hidden_dim=cfg.HIDDEN_DIM)
        probe = op.modulate(
            {
                "sensory": torch.zeros(cfg.STATE_DIM),
                "reward_context": torch.tensor([0.0]),
                "temporal_discount": torch.tensor([0.99]),
            }
        )
        if cfg.SIGNED_VRPE_FIELD not in probe:
            return None
        float(probe[cfg.SIGNED_VRPE_FIELD].item())
    except Exception:  # pragma: no cover - environment-dependent
        return None

    return DopamineHandle(operator=op, torch_mod=torch)


# --------------------------------------------------------------------------
# Deterministic Verified-Closure micro-task
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TaskDraw:
    a: IntArray
    b: IntArray
    claimed: IntArray  # the claim presented for verification
    truth_valid: IntArray  # 1 iff claimed == a+b  (ground truth)
    policy_label: IntArray  # policy's SUPPORT(1)/REFUTE(0) decision
    policy_margin: FloatArray  # |policy_estimate - claimed|, the confidence proxy
    policy_correct: IntArray  # 1 iff policy_label == truth_valid


def _make_task(seed: int) -> TaskDraw:
    rng = np.random.default_rng(seed)
    n = cfg.N_ITEMS
    a = rng.integers(2, 100, size=n).astype(np.int64)
    b = rng.integers(2, 100, size=n).astype(np.int64)
    true_sum = a + b

    valid = rng.integers(0, 2, size=n).astype(np.int64)
    noise = rng.integers(1, 9, size=n) * rng.choice([-1, 1], size=n)
    claimed = np.where(valid == 1, true_sum, true_sum + noise).astype(np.int64)
    truth_valid = (claimed == true_sum).astype(np.int64)

    # Weak arithmetic policy: estimates the sum with bounded skill, then judges
    # the claim against its own (noisy) estimate. No ground truth touches this.
    skill = rng.random(n) < 0.72
    est_noise = rng.integers(1, 6, size=n) * rng.choice([-1, 1], size=n)
    estimate = np.where(skill, true_sum, true_sum + est_noise).astype(np.int64)
    policy_label = (estimate == claimed).astype(np.int64)
    policy_margin = np.abs(estimate - claimed).astype(np.float64)
    policy_correct = (policy_label == truth_valid).astype(np.int64)

    return TaskDraw(
        a=a,
        b=b,
        claimed=claimed,
        truth_valid=truth_valid,
        policy_label=policy_label,
        policy_margin=policy_margin,
        policy_correct=policy_correct,
    )


def _draw_blob(seed: int) -> bytes:
    t = _make_task(seed)
    return b"".join(
        arr.tobytes()
        for arr in (
            t.a,
            t.b,
            t.claimed,
            t.truth_valid,
            t.policy_label,
            t.policy_margin,
            t.policy_correct,
        )
    )


def _b2_seeds() -> list[int]:
    """Independent B2 seed band, disjoint from the Step-D routing seeds."""
    return [cfg.SEED + cfg.B2_SEED_OFFSET + s for s in range(cfg.N_B2_SEEDS)]


def _decision_seeds() -> list[int]:
    """Every seed whose draw can enter a verdict: Step-B1 (SEED), the
    independent Step-B2 band, and all Step-D routing draws."""
    return [cfg.SEED] + _b2_seeds() + [cfg.SEED + s for s in range(cfg.N_SEEDS)]


def task_data_hash() -> str:
    """Hash *every* task draw that can enter a decision.

    Hashing only cfg.SEED would let nonzero-seed draws change a KILLED/SURVIVED
    decision without changing data_hash — a provenance hole flagged in review.
    """
    h = hashlib.sha256()
    for s in _decision_seeds():
        h.update(s.to_bytes(8, "little", signed=False))
        h.update(_draw_blob(s))
    return h.hexdigest()


# --------------------------------------------------------------------------
# Step B1 — admissible deterministic verifier
# --------------------------------------------------------------------------
def run_verifier(task: TaskDraw) -> tuple[FloatArray, float]:
    """Independent verification action: pure recomputation, no policy input.

    Returns (per-item verified-correct array, verifier accuracy vs ground
    truth). Deterministic, network-free — boundary fixed by construction.
    """
    verifier_valid = (task.claimed == (task.a + task.b)).astype(np.int64)
    correct = (verifier_valid == task.truth_valid).astype(np.float64)
    return correct, float(correct.mean())


def majority_baseline(task: TaskDraw) -> float:
    p = float(task.truth_valid.mean())
    return max(p, 1.0 - p)


def random_baseline(task: TaskDraw) -> float:
    # Two-class guess on a balanced-by-construction label.
    return 0.5


# --------------------------------------------------------------------------
# Actual DNCA signed vRPE per item (no ground-truth leakage)
# --------------------------------------------------------------------------
def signed_vrpe(handle: DopamineHandle, task: TaskDraw) -> FloatArray:
    """Drive the *real* DopamineOperator over the policy's inference trace.

    sensory      = standardized item/policy features (NO ground truth)
    reward_context = the policy's own confidence (information available at
                     inference time; ground-truth-free, so no leakage)
    """
    torch = handle.torch_mod
    op = handle.operator
    op.reset()

    n = cfg.N_ITEMS
    feats = np.stack(
        [
            task.a.astype(np.float64),
            task.b.astype(np.float64),
            task.claimed.astype(np.float64),
            task.policy_margin,
            task.policy_label.astype(np.float64),
        ],
        axis=1,
    )
    feats = (feats - feats.mean(axis=0)) / (feats.std(axis=0) + 1e-9)

    # confidence in [0,1]: high when policy estimate sits on the claim
    conf = 1.0 / (1.0 + task.policy_margin)

    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        sensory = np.zeros(cfg.STATE_DIM, dtype=np.float64)
        sensory[: feats.shape[1]] = feats[i]
        sps = {
            "sensory": torch.tensor(sensory, dtype=torch.float32),
            "reward_context": torch.tensor([float(conf[i])], dtype=torch.float32),
            "temporal_discount": torch.tensor([0.99], dtype=torch.float32),
        }
        res = op.modulate(sps)
        out[i] = float(res[cfg.SIGNED_VRPE_FIELD].item())
    return out


# --------------------------------------------------------------------------
# Step B2 — independent, fail-closed truth-correlation of the routed signal
# --------------------------------------------------------------------------
def b2_truth_correlation(handle: DopamineHandle) -> dict[str, Any]:
    """Per RETRACTION precondition #3, the estimator must be shown
    truth-correlated *independently* and *before* any routing read.

    Evaluated on a seed band disjoint from the Step-D decision draws. The gate
    is fail-closed: the routed signal ``-vRPE`` must be Spearman-significant
    (p < alpha) AND positively correlated with ``needs_verify`` on *every*
    independent B2 seed (``B2_REQUIRED_FRACTION`` = 1.0). A single fragile or
    borderline draw can never license reading a KILL/SURVIVED.

    Reported scalars are conservative: median ρ and the *worst* (max) p across
    the band.
    """
    rhos: list[float] = []
    pvals: list[float] = []
    per_seed_pass: list[bool] = []
    for seed in _b2_seeds():
        task = _make_task(seed)
        dopa_route = -signed_vrpe(handle, task)
        needs_verify = (task.policy_correct == 0).astype(np.float64)
        if float(np.std(dopa_route)) < 1e-12 or float(np.std(needs_verify)) < 1e-12:
            per_seed_pass.append(False)
            continue
        res = stats.spearmanr(dopa_route, needs_verify)
        rho_s = float(res.statistic)
        p_s = float(res.pvalue)
        rhos.append(rho_s)
        pvals.append(p_s)
        per_seed_pass.append(p_s < cfg.VRPE_TRUTH_CORR_ALPHA and rho_s > 0.0)

    n = len(_b2_seeds())
    frac_pass = (sum(per_seed_pass) / n) if n else 0.0
    signal_truth_corr = frac_pass >= cfg.B2_REQUIRED_FRACTION
    return {
        "signed_vrpe_truth_correlation": (float(np.median(rhos)) if rhos else None),
        "signed_vrpe_truth_corr_p": (float(max(pvals)) if pvals else None),
        "signal_is_truth_correlated": signal_truth_corr,
        "b2_seeds_passing": sum(per_seed_pass),
        "b2_seeds_total": n,
    }


# --------------------------------------------------------------------------
# Step D — routing under equal budget
# --------------------------------------------------------------------------
def _route_score(scores: FloatArray, task: TaskDraw) -> int:
    """Spend the budget on the top-scored items; benefit = policy errors fixed.

    The verifier is always correct, so a verified item that the policy got
    wrong is one unit of recovered verification benefit.
    """
    k = max(1, int(round(cfg.BUDGET_FRACTION * cfg.N_ITEMS)))
    chosen = np.argsort(-scores, kind="stable")[:k]
    return int((task.policy_correct[chosen] == 0).sum())


def policy_scores_for_seed(handle: DopamineHandle, seed: int) -> dict[str, int]:
    task = _make_task(seed)
    vrpe = signed_vrpe(handle, task)
    rng = np.random.default_rng(seed ^ 0x5DEECE66)

    uncertainty = task.policy_margin.copy()  # larger gap -> less trustworthy
    margin_only = -task.policy_margin.copy()  # no-vRPE control: trust the margin

    # Directional hypothesis: a more *negative* signed vRPE (worse-than-
    # expected outcome) flags an item worth verifying. Routed on the SIGNED
    # value, so the sign-flip control is non-degenerate.
    dopa = -vrpe
    # TRUE sign flip of the routing signal (vRPE -> -vRPE), NOT a |vRPE|
    # complement: negate the signed dopa score itself.
    dopa_inverted = np.negative(dopa)

    return {
        "dopa_signed_vrpe": _route_score(dopa, task),
        "uncertainty_only": _route_score(uncertainty, task),
        "no_vRPE": _route_score(margin_only, task),
        "signed_vrpe_inverted": _route_score(dopa_inverted, task),
        "random_gate": _route_score(rng.random(cfg.N_ITEMS), task),
        "verify_all": int((task.policy_correct == 0).sum()),
    }


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def _repro_hash(payload: dict[str, Any]) -> str:
    """Bind the *conclusion* (verdict + every decision input), not just a number.

    RETRACTION critique: "the repro hash protects a number, not the
    conclusion." Here the verdict and all gate outputs enter the digest.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run() -> dict[str, Any]:
    cfg_hash = cfg.config_hash()
    data_hash = task_data_hash()

    base: dict[str, Any] = {
        "claim": cfg.CLAIM,
        "boundary": cfg.BOUNDARY,
        "dnca_signal_source": f"{cfg.DNCA_SIGNAL_MODULE}.{cfg.DNCA_SIGNAL_SYMBOL}",
        "dopamine_signal_source": (
            f"{cfg.DNCA_SIGNAL_MODULE}.{cfg.DNCA_SIGNAL_SYMBOL}"
            f".modulate()['{cfg.SIGNED_VRPE_FIELD}']"
        ),
        "signed_vrpe_definition": SIGNED_VRPE_DEFINITION,
        "verified_closure_definition": VERIFIED_CLOSURE_DEFINITION,
        "config_hash": cfg_hash,
        "data_hash": data_hash,
    }

    def finalize(
        verdict: str,
        verifier_admissibility: dict[str, Any],
        majority: float,
        random_b: float,
        policy_scores: dict[str, float | None],
        delta: float | None,
        p_value: float | None,
        effect: float | None,
        negative_control: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(base)
        result.update(
            verdict=verdict,
            verifier_admissibility=verifier_admissibility,
            majority_baseline=majority,
            random_baseline=random_b,
            policy_scores=policy_scores,
            delta_dopa_vs_uncertainty=delta,
            p_value=p_value,
            effect_size=effect,
            negative_control_result=negative_control,
        )
        result["repro_hash"] = _repro_hash(
            {
                "verdict": verdict,
                "config_hash": cfg_hash,
                "data_hash": data_hash,
                "verifier_admissibility": verifier_admissibility,
                "majority_baseline": majority,
                "random_baseline": random_b,
                "policy_scores": policy_scores,
                "delta_dopa_vs_uncertainty": delta,
                "p_value": p_value,
                "effect_size": effect,
                "negative_control_result": negative_control,
            }
        )
        return result

    # Baselines and the verification action are properties of the task, not of
    # the DNCA signal — always computable, so the artifact never carries a fake
    # zero baseline even when Step A fails.
    task0 = _make_task(cfg.SEED)
    majority = majority_baseline(task0)
    random_b = random_baseline(task0)
    _, verifier_acc_pre = run_verifier(task0)

    # ---- Step A -------------------------------------------------------
    handle = load_dopamine_operator()
    if handle is None:
        return finalize(
            cfg.VERDICT_INADMISSIBLE_NO_SIGNAL,
            {
                "verifier_accuracy": verifier_acc_pre,
                "beats_majority": verifier_acc_pre > majority,
                "beats_random": verifier_acc_pre > random_b,
                "signed_vrpe_truth_correlation": None,
                "signed_vrpe_truth_corr_p": None,
                "signal_is_truth_correlated": False,
                "b2_seeds_passing": 0,
                "b2_seeds_total": cfg.N_B2_SEEDS,
            },
            majority,
            random_b,
            dict.fromkeys(cfg.POLICIES),
            None,
            None,
            None,
            {
                "is_true_sign_flip": True,
                "inverted_loses_advantage": None,
                "detail": (
                    "DNCA DopamineOperator not executable in this environment; signal NOT faked"
                ),
            },
        )

    # ---- Step B1 — verifier above majority AND random -----------------
    _, verifier_acc = run_verifier(task0)
    beats_majority = verifier_acc > majority
    beats_random = verifier_acc > random_b

    # Step B2 — routed-signal truth-correlation, evaluated independently and
    # fail-closed across a seed band disjoint from the Step-D decision draws
    # (RETRACTION precondition #3: shown truth-correlated independently, before
    # any routing read; review P1 fixed the sign — this hardens the gate so a
    # single borderline draw cannot license a KILL).
    b2 = b2_truth_correlation(handle)
    signal_truth_corr = bool(b2["signal_is_truth_correlated"])

    verifier_admissibility = {
        "verifier_accuracy": verifier_acc,
        "beats_majority": beats_majority,
        "beats_random": beats_random,
        "signed_vrpe_truth_correlation": b2["signed_vrpe_truth_correlation"],
        "signed_vrpe_truth_corr_p": b2["signed_vrpe_truth_corr_p"],
        "signal_is_truth_correlated": signal_truth_corr,
        "b2_seeds_passing": b2["b2_seeds_passing"],
        "b2_seeds_total": b2["b2_seeds_total"],
    }

    if not (beats_majority and beats_random):
        return finalize(
            cfg.VERDICT_INADMISSIBLE_WEAK_VERIFIER,
            verifier_admissibility,
            majority,
            random_b,
            dict.fromkeys(cfg.POLICIES),
            None,
            None,
            None,
            {
                "is_true_sign_flip": True,
                "inverted_loses_advantage": None,
                "detail": "verification action does not beat majority/random",
            },
        )

    # Step B2 gate: an uninformative routing signal is a weak instrument.
    # Pre-registered: vRPE must be truth-correlated BEFORE any routing read.
    if not signal_truth_corr:
        return finalize(
            cfg.VERDICT_INADMISSIBLE_WEAK_VERIFIER,
            verifier_admissibility,
            majority,
            random_b,
            dict.fromkeys(cfg.POLICIES),
            None,
            None,
            None,
            {
                "is_true_sign_flip": True,
                "inverted_loses_advantage": None,
                "detail": (
                    "signed vRPE is NOT truth-correlated with verification "
                    "benefit (RETRACTION precondition #3 unmet); routing "
                    "comparison would be an invalid instrument"
                ),
            },
        )

    # ---- Step C — VCR must not collapse to plain accuracy -------------
    verified_correct, _ = run_verifier(task0)
    k = max(1, int(round(cfg.BUDGET_FRACTION * cfg.N_ITEMS)))
    vcr = float(min(k, cfg.N_ITEMS)) / float(cfg.N_ITEMS)  # closure-event rate
    policy_accuracy = float(task0.policy_correct.mean())
    if abs(vcr - policy_accuracy) < 1e-9 or float(verified_correct.mean()) == policy_accuracy:
        return finalize(
            cfg.VERDICT_INADMISSIBLE_METRIC_COLLAPSE,
            verifier_admissibility,
            majority,
            random_b,
            dict.fromkeys(cfg.POLICIES),
            None,
            None,
            None,
            {
                "is_true_sign_flip": True,
                "inverted_loses_advantage": None,
                "detail": "VCR numerically collapses onto policy accuracy",
            },
        )

    # ---- Step D — 6-policy routing test, paired across seeds ----------
    per_seed: list[dict[str, int]] = [
        policy_scores_for_seed(handle, cfg.SEED + s) for s in range(cfg.N_SEEDS)
    ]
    agg: dict[str, float] = {
        pol: float(np.mean([d[pol] for d in per_seed])) for pol in cfg.POLICIES
    }

    dopa_arr = np.array([d["dopa_signed_vrpe"] for d in per_seed], dtype=np.float64)
    unc_arr = np.array([d["uncertainty_only"] for d in per_seed], dtype=np.float64)
    inv_arr = np.array([d["signed_vrpe_inverted"] for d in per_seed], dtype=np.float64)
    ceiling = np.array([d["verify_all"] for d in per_seed], dtype=np.float64)

    recoverable = float(np.mean(ceiling)) or 1.0
    delta = float((np.mean(dopa_arr) - np.mean(unc_arr)) / recoverable)

    diffs = dopa_arr - unc_arr
    if np.allclose(diffs, 0.0):
        p_value = 1.0
        effect = 0.0
    else:
        w = stats.wilcoxon(dopa_arr, unc_arr, zero_method="zsplit")
        p_value = float(w.pvalue)
        # rank-biserial effect size from paired differences
        pos = float((diffs > 0).sum())
        neg = float((diffs < 0).sum())
        effect = (pos - neg) / max(1.0, pos + neg)

    inverted_loses = bool(np.mean(inv_arr) < np.mean(dopa_arr))
    negative_control = {
        "is_true_sign_flip": True,
        "inverted_loses_advantage": inverted_loses,
        "detail": "negative control = -vRPE (sign negation), routed on signed value",
    }

    survived = (
        delta >= cfg.DELTA_MIN
        and p_value < cfg.ALPHA
        and inverted_loses
        and beats_majority
        and beats_random
    )
    verdict = cfg.VERDICT_SURVIVED if survived else cfg.VERDICT_KILLED

    policy_scores: dict[str, float | None] = dict(agg)
    return finalize(
        verdict,
        verifier_admissibility,
        majority,
        random_b,
        policy_scores,
        delta,
        p_value,
        effect,
        negative_control,
    )


def _write_artifacts(result: dict[str, Any]) -> list[str]:
    cfg.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    written = [str(cfg.RESULT_PATH)]
    cfg.RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    verdict = result["verdict"]
    if verdict.startswith("INADMISSIBLE"):
        cfg.INADMISSIBLE_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        written.append(str(cfg.INADMISSIBLE_PATH))
    elif verdict == cfg.VERDICT_KILLED:
        scoped = dict(result)
        scoped["kill_id"] = "KILL-0979B_DNCA_DOPA_ROUTING"
        scoped["scope"] = (
            "Scoped kill of THIS implementation only. DOPA-CLOSURE the theory "
            "remains UNTESTED (see evidence/dopa_closure/RETRACTION.md)."
        )
        cfg.KILL_PATH.write_text(json.dumps(scoped, indent=2, sort_keys=True) + "\n")
        written.append(str(cfg.KILL_PATH))
    elif verdict == cfg.VERDICT_SURVIVED:
        cfg.SURVIVED_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        written.append(str(cfg.SURVIVED_PATH))
    return written


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def main() -> None:
    result = run()
    artifacts = _write_artifacts(result)
    va = result["verifier_admissibility"]
    nc = result["negative_control_result"]
    scores = result["policy_scores"]

    print("STATUS: scaffold executed")
    print(f"VERDICT: {result['verdict']}")
    print(f"WHY: {nc['detail']}")
    print(f"DNCA SIGNAL: {result['dnca_signal_source']}")
    print(f"DOPAMINE/vRPE: {result['dopamine_signal_source']}")
    print(f"VERIFIER: accuracy={_fmt(va['verifier_accuracy'])}")
    print(f"MAJORITY BASELINE: {_fmt(result['majority_baseline'])}")
    print(f"RANDOM BASELINE: {_fmt(result['random_baseline'])}")
    print(f"VCR DEFINITION: {result['verified_closure_definition']}")
    print(f"POLICY SCORES: {json.dumps(scores, sort_keys=True)}")
    print(f"P-VALUE: {_fmt(result['p_value'])}")
    print(f"EFFECT SIZE: {_fmt(result['effect_size'])}")
    print(
        "NEGATIVE CONTROL: true_sign_flip="
        f"{nc['is_true_sign_flip']} inverted_loses={nc['inverted_loses_advantage']}"
    )
    print(f"REPRO HASH: {result['repro_hash']}")
    print(f"ARTIFACTS: {', '.join(artifacts)}")
    print(f"CLAIM BOUNDARY: {result['boundary']}")
    if result["verdict"].startswith("INADMISSIBLE"):
        print(
            "NEXT ACTION: satisfy the unmet RETRACTION precondition before any "
            "routing read; a clean INADMISSIBLE is the designed success mode"
        )
    elif result["verdict"] == cfg.VERDICT_KILLED:
        print("NEXT ACTION: KILL-0979B is scoped to this instrument; theory stays UNTESTED")
    else:
        print("NEXT ACTION: replicate SURVIVED_INITIAL under independent task families")


if __name__ == "__main__":
    main()
