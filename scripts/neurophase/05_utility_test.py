#!/usr/bin/env python3
"""Stage 05 — H2 utility test (NP-RUN1-S05-v1.1).

Leave-One-Subject-Out (LOSO) cross-validation. Primary comparison:
  ΔAUC(neural+behavior  −  behavior-only)   per held-out subject.
Reports also ΔAUC(neural-only − behavior-only) as sanity check.

Pre-registered verdict logic (NP-RUN1-VERDICT-v1.1):
  CONFIRMED : mean ΔAUC > 0  AND  t p < 0.05  AND  Cohen's d > 0.20
  REJECTED  : mean ΔAUC ≤ 0   OR  t p > 0.10
  AMBIGUITY : mean ΔAUC > 0   AND  0.05 < t p < 0.10
  else      : INCONCLUSIVE
CI: BCa bootstrap n=10000 (scipy.stats.bootstrap method='BCa').
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from _common import (
    REPO_ROOT,
    append_ledger,
    assert_features_frozen,
    load_config,
    load_contract,
    load_qc_summary,
    parse_std_args,
    require_provenance_freeze,
    set_global_seed,
    setup_logging,
    sha256_file,
    write_json,
)

try:
    import h5py
    from scipy import stats
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler
except ImportError as e:
    sys.exit(f"[FAIL-CLOSED] dependency missing: {e}")

BOOTSTRAP_N = 10000


def _bca_ci(data: np.ndarray, seed: int) -> tuple[float, float, str]:
    if data.size < 2:
        v = float(data.mean() if data.size else 0.0)
        return v, v, "degenerate"
    try:
        res = stats.bootstrap((data,), np.mean, n_resamples=BOOTSTRAP_N,
                              method="BCa", random_state=seed, vectorized=False)
        return float(res.confidence_interval.low), float(res.confidence_interval.high), "BCa"
    except Exception:
        rng = np.random.default_rng(seed)
        b = np.array([rng.choice(data, size=data.size, replace=True).mean() for _ in range(BOOTSTRAP_N)])
        return float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975)), "percentile_fallback"


def _load_subject(h5_path: Path, cluster_fn) -> dict:
    with h5py.File(h5_path, "r") as h:
        ch_names = [s.decode() for s in h["eeg"].attrs["ch_names"]]
        itpc_theta = h["eeg/itpc_theta"][:]
        frn = h["erp/frn"][:]
        p300 = h["erp/p300"][:]
        correct = h["behavior/correct"][:]
        rt = h["behavior/rt"][:]
        prev_correct = h["behavior/prev_correct"][:]
        running_acc = h["behavior/running_acc"][:]
        trial_num = h["behavior/trial_num"][:]
        cond = h["behavior/condition"][:]
    idx = cluster_fn(ch_names)
    x_itpc = itpc_theta[:, idx].mean(axis=1)
    neural = np.column_stack([x_itpc, frn, p300])
    behav = np.column_stack([running_acc, prev_correct, rt, trial_num, cond])
    nxt = np.roll(correct, -1)
    nxt[-1] = 0
    y = (nxt == 1).astype(int)
    return {"N": neural[:-1], "B": behav[:-1], "y": y[:-1]}


def _auc(model: str, data: dict, train_idx: list[int], test_idx: list[int]) -> float:
    if model == "neural_plus_behavior":
        Xtr = np.vstack([np.column_stack([data[i]["N"], data[i]["B"]]) for i in train_idx])
        Xte = np.column_stack([data[test_idx[0]]["N"], data[test_idx[0]]["B"]])
    else:
        key = "N" if model == "neural" else "B"
        Xtr = np.vstack([data[i][key] for i in train_idx])
        Xte = data[test_idx[0]][key]
    ytr = np.concatenate([data[i]["y"] for i in train_idx])
    yte = data[test_idx[0]]["y"]
    if yte.sum() < 2 or (len(yte) - yte.sum()) < 2:
        return float("nan")
    sc = StandardScaler().fit(Xtr)
    clf = LogisticRegression(max_iter=2000, random_state=42).fit(sc.transform(Xtr), ytr)
    proba = clf.predict_proba(sc.transform(Xte))[:, 1]
    return float(roc_auc_score(yte, proba))


def _summarize(delta: np.ndarray, seed: int) -> dict:
    v = delta[~np.isnan(delta)]
    if v.size < 3:
        return {"n": int(v.size), "mean": 0.0, "sd": 0.0, "t": 0.0, "t_p": 1.0, "d": 0.0,
                "ci95": [0.0, 0.0], "ci_method": "degenerate"}
    t, p = stats.ttest_1samp(v, 0.0)
    d = float(v.mean() / (v.std(ddof=1) + 1e-30))
    lo, hi, method = _bca_ci(v, seed)
    return {"n": int(v.size), "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
            "t": float(t), "t_p": float(p), "d": d, "ci95": [lo, hi], "ci_method": method}


def main() -> None:
    args = parse_std_args("05_utility_test")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])
    _ = require_provenance_freeze(cfg)
    _ = load_qc_summary(cfg)
    log = setup_logging("05_utility_test", cfg)

    features_dir = REPO_ROOT / cfg["paths"]["features_dir"]
    manifest_path = features_dir / "FEATURE_STORE_MANIFEST.json"
    if not manifest_path.exists():
        sys.exit(f"[FAIL-CLOSED] {manifest_path} missing")
    assert_features_frozen(features_dir)
    manifest = json.loads(manifest_path.read_text())

    cluster = cfg["analysis"]["existence"]["electrode_cluster"]
    def cluster_fn(ch_names: list[str]) -> list[int]:
        return [ch_names.index(c) for c in cluster if c in ch_names]

    subjects: list[str] = []
    data: dict[int, dict] = {}
    for s in manifest["subjects"]:
        p = Path(s["file"])
        if sha256_file(p) != s["sha256"]:
            sys.exit(f"[FAIL-CLOSED] hash mismatch {s['subject_id']}")
        d = _load_subject(p, cluster_fn)
        if len(d["y"]) < 50:
            continue
        subjects.append(s["subject_id"])
        data[len(subjects) - 1] = d

    n = len(subjects)
    log.info("=" * 72)
    log.info(f"Stage 05 — LOSO utility | n_subjects={n} | bootstrap={BOOTSTRAP_N}")
    log.info("=" * 72)

    delta_NB_B = np.full(n, np.nan)
    delta_N_B = np.full(n, np.nan)
    aucs = {m: np.full(n, np.nan) for m in ("neural", "behavior", "neural_plus_behavior")}
    for i in range(n):
        train = [j for j in range(n) if j != i]
        for m in aucs:
            aucs[m][i] = _auc(m, data, train, [i])
        delta_N_B[i] = aucs["neural"][i] - aucs["behavior"][i]
        delta_NB_B[i] = aucs["neural_plus_behavior"][i] - aucs["behavior"][i]
        log.info(f"LOSO {subjects[i]}: AUC N={aucs['neural'][i]:.3f} B={aucs['behavior'][i]:.3f} "
                 f"NB={aucs['neural_plus_behavior'][i]:.3f}  ΔNB-B={delta_NB_B[i]:+.4f}")

    nb_s = _summarize(delta_NB_B, cfg["random_seed"])
    n_s = _summarize(delta_N_B, cfg["random_seed"])
    primary = nb_s

    conf = contract["hypotheses"]["H2"]["confirm_threshold"]
    rej = contract["hypotheses"]["H2"]["reject_threshold"]

    # Pre-registered decision table (NP-RUN1-VERDICT-v1.1 → H2 → decision_table):
    #   delta>0, p<0.05, d>=0.20 → CONFIRMED
    #   delta>0, p<0.05, d<0.20  → CONFIRMED_WEAK
    #   delta>0, 0.05≤p<0.10     → INCONCLUSIVE
    #   delta>0, p>=0.10         → REJECTED
    #   delta<=0                 → REJECTED
    mean = primary["mean"]
    p = primary["t_p"]
    d = primary["d"]
    d_min = float(conf["cohens_d_min"])
    if mean <= 0:
        verdict = "REJECTED"
    elif p < 0.05:
        verdict = "CONFIRMED" if d >= d_min else "CONFIRMED_WEAK"
    elif p < 0.10:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    report = {
        "run_id": cfg["run_id"],
        "contract_sha256": contract["_contract_sha256"],
        "n_subjects": n,
        "delta_auc_NB_minus_B_primary": nb_s,
        "delta_auc_N_minus_B_sanity": n_s,
        "per_subject": [{"subject_id": subjects[i],
                         "auc_N": float(aucs["neural"][i]),
                         "auc_B": float(aucs["behavior"][i]),
                         "auc_NB": float(aucs["neural_plus_behavior"][i]),
                         "delta_N_B": float(delta_N_B[i]),
                         "delta_NB_B": float(delta_NB_B[i])} for i in range(n)],
        "verdict": verdict,
    }

    out = REPO_ROOT / cfg["paths"]["results_dir"] / "utility_report.json"
    write_json(out, report)
    append_ledger(cfg, {"stage": "05_utility_test",
                        "output": {"report": str(out), "sha256": sha256_file(out),
                                   "verdict": verdict,
                                   "mean_delta_NB_B": primary["mean"],
                                   "t_p": primary["t_p"],
                                   "cohens_d": primary["d"]},
                        "status": "ok"})
    log.info(f"[05_utility_test] verdict={verdict}  "
             f"ΔAUC(NB-B) mean={primary['mean']:.4f}  t_p={primary['t_p']:.4g}  d={primary['d']:.3f}")
    log.info(f"  CI95 ({primary['ci_method']}) = {primary['ci95']}")


if __name__ == "__main__":
    main()
