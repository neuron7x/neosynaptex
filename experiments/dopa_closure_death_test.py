"""DOPA-CLOSURE real-dataset death-test (SciFact, deterministic, offline).

Single falsifiable claim (frozen in docs/experiments/DOPA_CLOSURE_DEATH_TEST_CONTRACT.md):

    DOPA-CLOSURE survives iff a vRPE-gated routing policy achieves higher
    Verified Closure Rate (VCR) than `uncertainty_only` (the no-vRPE ablation)
    on a real claim-verification benchmark UNDER EQUAL BUDGET, AND that
    advantage disappears under the inverted-vRPE negative control.

No LLM judge. No network at run time (dataset is fetched once, offline after).
Cheap predictor = TF-IDF + logistic regression. Expensive verification =
bootstrap ensemble (genuinely K x more compute). Budget = bootstrap-model
prediction calls. All policies share an identical stochastic substrate per
seed and differ only in allocation policy.

Run from repo root:  python experiments/dopa_closure_death_test.py

Yaroslav Vasylenko / neuron7xLab / 2026
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCIFACT = _REPO_ROOT / "data" / "scifact" / "data"
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "scifact_smoke.jsonl"

# ---- frozen constants (mirror configs/dopa_closure/death_test.yaml) -------
K_VERIFY = 8
K_CONF = 1.5
TAU = 0.30
SEED_SWEEP = [11, 23, 42, 101, 202, 303, 404, 505, 606, 707]
DELTA_MIN = 0.02
SIGN_FRAC = 0.70
EPS = 0.01
LABEL_MAP = {"SUPPORT": 1, "CONTRADICT": 0}


@dataclass(frozen=True)
class Item:
    """One binary claim-verification example (no NOINFO)."""

    text: str
    label: int  # 1 = SUPPORT, 0 = CONTRADICT


def _claim_label(evidence: object) -> str | None:
    if not isinstance(evidence, dict):
        return None
    votes: list[str] = []
    for anns in evidence.values():
        if not isinstance(anns, list):
            continue
        for a in anns:
            if isinstance(a, dict) and str(a.get("label")) in LABEL_MAP:
                votes.append(str(a.get("label")))
    if not votes:
        return None
    return max(set(votes), key=votes.count)


def _build_items(
    claims: list[dict[str, object]], corpus: dict[int, dict[str, object]]
) -> list[Item]:
    items: list[Item] = []
    for c in claims:
        ev = c.get("evidence") or {}
        if not isinstance(ev, dict):
            continue
        lab = _claim_label(ev)
        if lab is None:
            continue
        doc_id = int(next(iter(ev.keys())))
        doc = corpus.get(doc_id)
        if doc is None:
            continue
        abstract_raw = doc.get("abstract", [])
        sentences = abstract_raw if isinstance(abstract_raw, list) else []
        abstract = " ".join(str(s) for s in sentences)
        title = str(doc.get("title", ""))
        text = f"{c['claim']} [SEP] {title} {abstract}"
        items.append(Item(text=text, label=LABEL_MAP[lab]))
    return items


def load_items() -> tuple[list[Item], list[Item], str]:
    """Return (train, dev, source_tag). Full SciFact if present else fixture."""
    if _SCIFACT.exists():
        corpus = {
            int(json.loads(l)["doc_id"]): json.loads(l)
            for l in (_SCIFACT / "corpus.jsonl").read_text().splitlines()
        }
        tr = [json.loads(l) for l in (_SCIFACT / "claims_train.jsonl").read_text().splitlines()]
        dv = [json.loads(l) for l in (_SCIFACT / "claims_dev.jsonl").read_text().splitlines()]
        return _build_items(tr, corpus), _build_items(dv, corpus), "scifact_full"
    rows = [json.loads(l) for l in _FIXTURE.read_text().splitlines()]
    items = [Item(text=r["text"], label=int(r["label"])) for r in rows]
    cut = len(items) // 2
    return items[:cut], items[cut:], "scifact_smoke_fixture"


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _new_model(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=2000, C=4.0, random_state=seed)),
        ]
    )


@dataclass(frozen=True)
class Substrate:
    """Identical per-seed draws reused by every policy."""

    gold: list[int]
    cheap_pred: list[int]
    margin: list[float]
    probe_pred: list[int]
    ensemble_pred: list[int]  # majority over K bootstrap models


def build_substrate(train: list[Item], dev: list[Item], seed: int) -> Substrate:
    rng = np.random.default_rng(seed)
    xtr = [it.text for it in train]
    ytr = [it.label for it in train]
    xdv = [it.text for it in dev]

    base = _new_model(seed).fit(xtr, ytr)
    cheap_pred = [int(p) for p in base.predict(xdv)]
    dec = base.decision_function(xdv)
    margin = [float(abs(v)) for v in np.atleast_1d(dec)]

    n = len(train)
    boot_preds: list[list[int]] = []
    for k in range(K_VERIFY + 1):  # +1 = cheap probe model
        idx = rng.integers(0, n, size=n)
        bx = [xtr[i] for i in idx]
        by = [ytr[i] for i in idx]
        if len(set(by)) < 2:  # degenerate resample guard
            bx, by = xtr, ytr
        m = _new_model(seed * 131 + k).fit(bx, by)
        boot_preds.append([int(p) for p in m.predict(xdv)])

    probe_pred = boot_preds[0]
    ens = boot_preds[1:]
    ensemble_pred = [
        int(sum(ens[k][i] for k in range(K_VERIFY)) * 2 >= K_VERIFY) for i in range(len(dev))
    ]
    return Substrate(
        gold=[it.label for it in dev],
        cheap_pred=cheap_pred,
        margin=margin,
        probe_pred=probe_pred,
        ensemble_pred=ensemble_pred,
    )


def _vcr(verdicts: list[int], gold: list[int]) -> float:
    return mean(1.0 if v == g else 0.0 for v, g in zip(verdicts, gold))


def _vrpe(margin: float, cheap: int, probe: int) -> float:
    q_expected = _sigmoid(K_CONF * margin)
    q_observed = 1.0 if probe == cheap else 0.0
    return q_observed - q_expected


def policy_cheap_only(s: Substrate) -> tuple[list[int], int]:
    return list(s.cheap_pred), 0


def policy_dopa(s: Substrate, invert: bool) -> tuple[list[int], int]:
    verdicts = list(s.cheap_pred)
    cost = 0
    for i in range(len(s.gold)):
        cost += 1  # probe always paid
        v = _vrpe(s.margin[i], s.cheap_pred[i], s.probe_pred[i])
        surprising = abs(v) >= TAU
        do_verify = (not surprising) if invert else surprising
        if do_verify:
            cost += K_VERIFY
            verdicts[i] = s.ensemble_pred[i]
    return verdicts, cost


def _budgeted(s: Substrate, order: list[int], budget: int) -> tuple[list[int], int]:
    verdicts = list(s.cheap_pred)
    cost = 0
    for idx in order:
        if cost + K_VERIFY > budget:
            continue
        cost += K_VERIFY
        verdicts[idx] = s.ensemble_pred[idx]
    return verdicts, cost


def policy_uncertainty_only(s: Substrate, budget: int) -> tuple[list[int], int]:
    order = sorted(range(len(s.gold)), key=lambda i: s.margin[i])  # least confident first
    return _budgeted(s, order, budget)


def policy_random_gate(
    s: Substrate, budget: int, rng: np.random.Generator
) -> tuple[list[int], int]:
    order = [int(i) for i in rng.permutation(len(s.gold))]
    return _budgeted(s, order, budget)


def policy_fixed_full(s: Substrate) -> tuple[list[int], int]:
    return list(s.ensemble_pred), len(s.gold) * K_VERIFY


def run_seed(train: list[Item], dev: list[Item], seed: int) -> dict[str, float]:
    s = build_substrate(train, dev, seed)
    dopa_v, dopa_b = policy_dopa(s, invert=False)
    inv_v, _ = policy_dopa(s, invert=True)
    cheap_v, _ = policy_cheap_only(s)
    unc_v, _ = policy_uncertainty_only(s, dopa_b)
    rnd_v, _ = policy_random_gate(s, dopa_b, np.random.default_rng(seed ^ 0x5EED))
    full_v, _ = policy_fixed_full(s)
    return {
        "dopa_vrpe": _vcr(dopa_v, s.gold),
        "uncertainty_only": _vcr(unc_v, s.gold),
        "dopa_vrpe_inverted": _vcr(inv_v, s.gold),
        "random_gate": _vcr(rnd_v, s.gold),
        "cheap_only": _vcr(cheap_v, s.gold),
        "fixed_full": _vcr(full_v, s.gold),
        "dopa_extra_budget": float(dopa_b),
        "n_items": float(len(s.gold)),
    }


def main() -> int:
    train, dev, source = load_items()
    per_seed = {str(sd): run_seed(train, dev, sd) for sd in SEED_SWEEP}
    keys = [
        "dopa_vrpe",
        "uncertainty_only",
        "dopa_vrpe_inverted",
        "random_gate",
        "cheap_only",
        "fixed_full",
    ]
    agg = {
        k: {
            "mean": mean(per_seed[str(s)][k] for s in SEED_SWEEP),
            "std": pstdev([per_seed[str(s)][k] for s in SEED_SWEEP]),
        }
        for k in keys
    }
    a_d = agg["dopa_vrpe"]["mean"]
    a_u = agg["uncertainty_only"]["mean"]
    a_i = agg["dopa_vrpe_inverted"]["mean"]
    a_r = agg["random_gate"]["mean"]
    signs = [
        1 if per_seed[str(s)]["dopa_vrpe"] - per_seed[str(s)]["uncertainty_only"] > 0 else 0
        for s in SEED_SWEEP
    ]
    sign_frac = mean(signs)

    cond = {
        "1_delta_vs_uncertainty>=DELTA_MIN": (a_d - a_u) >= DELTA_MIN,
        "2_sign_consistency>=SIGN_FRAC": sign_frac >= SIGN_FRAC,
        "3_dopa>random": a_d > a_r,
        "4_inverted<=dopa-EPS": a_i <= a_d - EPS,
    }
    survived = all(cond.values())
    verdict = "SURVIVED_INITIAL" if survived else "KILLED"

    constants = {
        "K_VERIFY": K_VERIFY,
        "K_CONF": K_CONF,
        "TAU": TAU,
        "SEED_SWEEP": SEED_SWEEP,
        "DELTA_MIN": DELTA_MIN,
        "SIGN_FRAC": SIGN_FRAC,
        "EPS": EPS,
    }
    config_hash = hashlib.sha256(json.dumps(constants, sort_keys=True).encode()).hexdigest()
    dataset_hash = hashlib.sha256(
        json.dumps([[it.text, it.label] for it in (train + dev)], sort_keys=True).encode()
    ).hexdigest()
    payload = {"constants": constants, "per_seed": per_seed, "aggregate": agg}
    repro_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    result = {
        "schema": "dopa_death_test_result/1",
        "artifact_id": str(uuid.uuid4()),
        "dataset_name": "SciFact (allenai) binary SUPPORT/CONTRADICT",
        "dataset_source_tag": source,
        "claim": (
            "vRPE-gated routing beats uncertainty_only (no_vRPE) on Verified "
            "Closure Rate under equal budget, advantage gone under inverted vRPE."
        ),
        "boundary": (
            "Real claim-verification dataset, TF-IDF+logreg cheap predictor, "
            "bootstrap-ensemble expensive verification, deterministic, no LLM. "
            "Admissibility/engineering signal — not a science claim about dopamine."
        ),
        "seed_sweep": SEED_SWEEP,
        "sample_count": int(per_seed[str(SEED_SWEEP[0])]["n_items"]),
        "train_count": len(train),
        "policy_scores": {k: agg[k]["mean"] for k in keys},
        "policy_std": {k: agg[k]["std"] for k in keys},
        "delta_dopa_vs_uncertainty": a_d - a_u,
        "delta_dopa_vs_inverted": a_d - a_i,
        "sign_fraction": sign_frac,
        "equal_budget_extra_calls": mean(per_seed[str(s)]["dopa_extra_budget"] for s in SEED_SWEEP),
        "survival_predicate": cond,
        "verdict": verdict,
        "kill_reason": (
            None if survived else "Pre-registered survival predicate not met under equal budget."
        ),
        "config_hash": config_hash,
        "dataset_hash": dataset_hash,
        "reproducibility_hash": repro_hash,
        "per_seed": per_seed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preregistration": "docs/experiments/DOPA_CLOSURE_DEATH_TEST_CONTRACT.md",
    }

    out = _REPO_ROOT / "evidence" / "dopa_closure"
    out.mkdir(parents=True, exist_ok=True)
    (out / "death_test_result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    if not survived:
        kill = {
            "kill_id": "KILL-0979",
            "killed_claim": result["claim"],
            "dataset": result["dataset_name"],
            "reason": result["kill_reason"],
            "policy_scores": result["policy_scores"],
            "delta_dopa_vs_uncertainty": result["delta_dopa_vs_uncertainty"],
            "sign_fraction": sign_frac,
            "minimal_counterexample": (
                f"dopa_vrpe={a_d:.4f} <= uncertainty_only={a_u:.4f} at equal "
                f"budget across {len(SEED_SWEEP)} seeds (sign_frac={sign_frac:.2f})."
            ),
            "future_guardrail": (
                "On real claim-verification data the vRPE signal carries no "
                "routing advantage over raw classifier-margin ranking. Any "
                "restart must pre-register a vRPE estimator independently shown "
                "to be more budget-efficient than margin BEFORE re-testing."
            ),
            "reproducibility_hash": repro_hash,
            "created_at": result["created_at"],
        }
        (out / "KILL-0979.json").write_text(json.dumps(kill, indent=2, sort_keys=True))

    print(f"VERDICT={verdict}  source={source}  N={result['sample_count']}")
    print(
        "VCR  dopa={:.4f} unc={:.4f} inv={:.4f} rnd={:.4f} cheap={:.4f} full={:.4f}".format(
            a_d, a_u, a_i, a_r, agg["cheap_only"]["mean"], agg["fixed_full"]["mean"]
        )
    )
    print(
        f"delta(dopa-unc)={a_d - a_u:+.4f} delta(dopa-inv)={a_d - a_i:+.4f} "
        f"sign_frac={sign_frac:.2f}"
    )
    print(f"conditions={cond}")
    print(
        f"config_hash={config_hash[:12]} dataset_hash={dataset_hash[:12]} "
        f"repro_hash={repro_hash[:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
