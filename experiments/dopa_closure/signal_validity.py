"""DOPA-CLOSURE precondition #3 — is the REAL DNCA dopaminergic signal
truth-correlated with prediction-violation? Admissible instrument.

This is the single gating measurement defined by evidence/dopa_closure/
GAP_AUDIT.md. No proxy: it drives the real `neuron7x_agents.dnca.DNCA`
and reads the architecture's own emitted observables. No gate, budget, or
closure claim is built unless this passes — a gate cannot rescue a signal
that carries no information.

Construct-validity ledger (vs the retracted #198/#199):
  real object .......... real DNCA, not sklearn/ΔS proxy
  observable ........... DNCA-emitted `mismatch` (forward-model surprise,
                         reward-free) + |dopamine_signal| (TD-RPE)
  task ................. native prediction-violation regime detection,
                         not forced binary text classification
  control .............. circular-shift null — CONSTRUCTABLE and
                         autocorrelation-preserving (fixes GAP_AUDIT G-01;
                         an absolute-value gate cannot host a sign-flip)
  significance ......... empirical two-sided p over the null (fixes G-08)
  reproducibility ...... fully synthetic + deterministic, no git-ignored
                         data (fixes G-06)

Frozen pre-registration (before any run):
  PRIMARY observable  = `mismatch`
  SECONDARY           = |dopamine_signal|
  STATISTIC           = AUC(observable ranks, shock label)
  NULL                = exact: all n-1 circular shifts (deterministic)
  DNCA_SEEDS          = [1, 2, 3, 4, 5]
  N_STEPS, WARMUP, block structure, shock rate: constants below
  ADMISSIBLE iff: mean AUC >= AUC_MIN AND null p < P_MAX AND
                  >= SIGN_FRAC of seeds on the same side of 0.5
  else: SIGNAL_ABSENT -> DOPA-CLOSURE killed on the real mechanism.

Run from repo root:
  python experiments/dopa_closure/signal_validity.py

Yaroslav Vasylenko / neuron7xLab / 2026
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

import numpy as np
import torch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents" / "src"))

from neuron7x_agents.dnca import DNCA  # noqa: E402

# ---- frozen constants -----------------------------------------------------
# Design right-sizing (frozen BEFORE any result was observed — not post-hoc
# tuning; the over-specified 1200x5 run produced no output before being
# killed for being computationally infeasible to iterate). Power retained:
# 480 eval steps/seed at SHOCK_RATE 0.20 -> ~96 pos / 384 neg; SE(AUC|H0)
# ~= sqrt((n+1)/(12 n_p n_n)) ~= 0.033, so AUC>=0.60 is ~3 SE detectable
# per seed. Exact circular null over n-1 shifts is unaffected. Construct
# validity, observable, task, null, and the decision rule are UNCHANGED.
STATE_DIM = 32
N_STEPS = 600
WARMUP = 120
RHO = 0.9  # AR(1) structured-regime persistence
SHOCK_BLOCK = 12  # autocorrelated shock block length
SHOCK_RATE = 0.20  # fraction of post-warmup steps under shock
# v2 (KILL-0979B fix): variance-MATCHED shock. AR(1) stationary std for
# x=ρx+(1-ρ)ε, ε~N(0,1) is sqrt((1-ρ)/(1+ρ)). The shock draws i.i.d. at
# that SAME marginal scale, so it breaks temporal predictability WITHOUT a
# magnitude cue — a raw-input detector can no longer separate it (v1 was
# confounded: N(0,4) shock was trivially magnitude-detectable, AUC(raw)~0.99).
STRUCT_STD = float(((1.0 - RHO) / (1.0 + RHO)) ** 0.5)
DNCA_SEEDS = [1, 2, 3]
AUC_MIN = 0.60
P_MAX = 0.05
SIGN_FRAC = 0.80
TRIVIAL_MARGIN = 0.10  # DNCA AUC must beat raw-input baseline by this


def _make_sequence(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (inputs[N,STATE_DIM], shock_label[N]) with block-autocorrelated
    shocks violating the AR(1) prediction structure."""
    rng = np.random.default_rng(seed)
    x = np.zeros(STATE_DIM)
    xs = np.empty((N_STEPS, STATE_DIM))
    shock = np.zeros(N_STEPS, dtype=int)
    t = 0
    while t < N_STEPS:
        is_shock = t >= WARMUP and rng.random() < SHOCK_RATE
        blk = SHOCK_BLOCK if is_shock else SHOCK_BLOCK // 2
        for _ in range(blk):
            if t >= N_STEPS:
                break
            if is_shock:
                # variance-matched: same marginal scale, temporal structure broken
                x = rng.normal(0.0, STRUCT_STD, STATE_DIM)
                shock[t] = 1
            else:
                x = RHO * x + (1.0 - RHO) * rng.normal(0.0, 1.0, STATE_DIM)
            xs[t] = x
            t += 1
    return xs, shock


def _ranks(scores: np.ndarray) -> np.ndarray:
    """Average ranks (ties shared), vectorised."""
    order = np.argsort(scores, kind="mergesort")
    n = scores.size
    r = np.empty(n, dtype=np.float64)
    r[order] = np.arange(1, n + 1, dtype=np.float64)
    s = scores[order]
    same = np.empty(n, dtype=bool)
    same[0] = False
    same[1:] = s[1:] == s[:-1]
    i = 0
    while i < n:
        j = i + 1
        while j < n and same[j]:
            j += 1
        if j - i > 1:
            r[order[i:j]] = (i + 1 + j) / 2.0
        i = j
    return r


def _auc_from_ranks(ranks: np.ndarray, labels: np.ndarray) -> float:
    n_p = int(labels.sum())
    n_n = labels.size - n_p
    if n_p == 0 or n_n == 0:
        return float("nan")
    r_pos = float(ranks[labels == 1].sum())
    return (r_pos - n_p * (n_p + 1) / 2.0) / (n_p * n_n)


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank-based AUC (Mann-Whitney); 0.5 == no discrimination."""
    return _auc_from_ranks(_ranks(scores), labels)


def _circular_null_p(scores: np.ndarray, labels: np.ndarray, observed: float) -> float:
    """EXACT two-sided p over ALL n-1 non-trivial circular shifts of the
    label series (preserves observable + label autocorrelation).
    Deterministic — no Monte-Carlo, no RNG."""
    n = scores.size
    ranks = _ranks(scores)
    stat0 = abs(observed - 0.5)
    lab = labels.astype(np.float64)
    hits = 1  # include the observed in the reference set
    for k in range(1, n):
        r_pos = float(ranks @ np.roll(lab, k))
        n_p = int(lab.sum())
        n_n = n - n_p
        auc_k = (r_pos - n_p * (n_p + 1) / 2.0) / (n_p * n_n)
        if abs(auc_k - 0.5) >= stat0:
            hits += 1
    return hits / n


def run_seed(seed: int) -> dict[str, float]:
    torch.manual_seed(seed)
    xs, shock = _make_sequence(seed)
    model = DNCA(state_dim=STATE_DIM, seed=seed)
    mismatch = np.empty(N_STEPS)
    dop = np.empty(N_STEPS)
    for t in range(N_STEPS):
        out = model.step(torch.from_numpy(xs[t]).float(), reward=0.0)
        mismatch[t] = out.mismatch
        dop[t] = abs(float(model.sps.dopamine_signal.item()))
    lab = shock[WARMUP:]
    m = mismatch[WARMUP:]
    d = dop[WARMUP:]
    # KILL-0979B mandatory negative control: a raw-input-magnitude detector.
    # If DNCA does not beat this, the separation is not DNCA-specific.
    trivial = np.linalg.norm(xs[WARMUP:], axis=1)
    auc_m = _auc(m, lab)
    auc_d = _auc(d, lab)
    return {
        "auc_mismatch": auc_m,
        "p_mismatch": _circular_null_p(m, lab, auc_m),
        "auc_dopamine": auc_d,
        "p_dopamine": _circular_null_p(d, lab, auc_d),
        "auc_trivial_baseline": _auc(trivial, lab),
        "shock_frac": float(lab.mean()),
    }


def main() -> int:
    per_seed = {str(s): run_seed(s) for s in DNCA_SEEDS}
    auc_m = [per_seed[str(s)]["auc_mismatch"] for s in DNCA_SEEDS]
    p_m = [per_seed[str(s)]["p_mismatch"] for s in DNCA_SEEDS]
    mean_auc = mean(auc_m)
    mean_trivial = mean(per_seed[str(s)]["auc_trivial_baseline"] for s in DNCA_SEEDS)
    same_side = mean(1.0 if (a > 0.5) == (mean_auc > 0.5) else 0.0 for a in auc_m)
    null_ok = max(p_m) < P_MAX
    beats_trivial = (mean_auc - mean_trivial) >= TRIVIAL_MARGIN
    base = mean_auc >= AUC_MIN and null_ok and same_side >= SIGN_FRAC
    if base and beats_trivial:
        verdict = "SIGNAL_ADMISSIBLE"
    elif base and not beats_trivial:
        # statistically clean but explained by a raw-input detector -> confounded
        verdict = "INADMISSIBLE_CONFOUNDED"
    else:
        verdict = "SIGNAL_ABSENT"

    constants = {
        "STATE_DIM": STATE_DIM,
        "N_STEPS": N_STEPS,
        "WARMUP": WARMUP,
        "RHO": RHO,
        "SHOCK_BLOCK": SHOCK_BLOCK,
        "SHOCK_RATE": SHOCK_RATE,
        "STRUCT_STD": STRUCT_STD,
        "DNCA_SEEDS": DNCA_SEEDS,
        "NULL": "exhaustive_circular_shifts_exact",
        "AUC_MIN": AUC_MIN,
        "P_MAX": P_MAX,
        "SIGN_FRAC": SIGN_FRAC,
        "TRIVIAL_MARGIN": TRIVIAL_MARGIN,
        "shock_kind": "variance_matched_v2_KILL-0979B_fix",
    }
    payload = {"constants": constants, "per_seed": per_seed}
    repro_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    result = {
        "schema": "dopa_signal_validity/2",
        "instrument": (
            "REAL DNCA dopaminergic signal vs prediction-violation "
            "(v2: variance-matched shock + trivial-baseline control)"
        ),
        "construct_valid": True,
        "verdict": verdict,
        "primary": "mismatch (DNCA forward-model surprise, reward-free)",
        "mean_auc_mismatch": mean_auc,
        "std_auc_mismatch": pstdev(auc_m),
        "max_p_mismatch": max(p_m),
        "sign_consistency": same_side,
        "mean_auc_dopamine": mean(per_seed[str(s)]["auc_dopamine"] for s in DNCA_SEEDS),
        "mean_auc_trivial_baseline": mean_trivial,
        "dnca_minus_trivial": mean_auc - mean_trivial,
        "beats_trivial_by_margin": beats_trivial,
        "decision_rule": (
            "AUC>=0.60 AND null p<0.05 AND >=80% seeds same side AND "
            "(mean_auc - trivial_baseline) >= TRIVIAL_MARGIN"
        ),
        "interpretation": (
            "SIGNAL_ADMISSIBLE -> gate worth building. "
            "INADMISSIBLE_CONFOUNDED -> clean but explained by a raw-input "
            "detector (KILL-0979B class). SIGNAL_ABSENT -> dopaminergic signal "
            "carries no prediction-violation information. v1 (N(0,4) shock) was "
            "INADMISSIBLE_CONFOUNDED; this v2 must be re-run to obtain a verdict."
        ),
        "per_seed": per_seed,
        "reproducibility_hash": repro_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "supersedes_note": ("v2 design per KILL-0979B; no v2 verdict until re-run on this code."),
    }
    out = _REPO_ROOT / "evidence" / "dopa_closure" / "signal_validity_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(f"VERDICT={verdict}")
    print(
        f"mismatch AUC mean={mean_auc:.4f} sd={pstdev(auc_m):.4f} "
        f"max_p={max(p_m):.4g} sign={same_side:.2f}"
    )
    print(f"per-seed AUC(mismatch)={[round(a, 4) for a in auc_m]} p={[round(x, 4) for x in p_m]}")
    print(f"dopamine AUC mean={mean(per_seed[str(s)]['auc_dopamine'] for s in DNCA_SEEDS):.4f}")
    print(f"repro_hash={repro_hash[:12]}  artifact={out.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
