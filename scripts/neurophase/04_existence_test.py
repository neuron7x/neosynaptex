#!/usr/bin/env python3
"""Stage 04 — H1 existence test (NP-RUN1-S04-v1.1).

Tests whether pre-response θ-phase (ITPC_theta at FCz/Fz/Cz cluster) carries
INCREMENTAL information about next-trial win-stay/lose-shift adaptation beyond
a behavior-only baseline. Epistemic scope: incremental predictive value,
NOT universal causality (see contracts/neurophase_run1.yaml:epistemic_scope).

Statistical protocol (pre-registered, NP-RUN1-VERDICT-v1.1):
  - Per subject: logistic regression, β₁ on ITPC_theta with covariates
    (running_acc, prev_correct, RT, trial_num, condition).
  - Permutation null: within-condition-block shuffle of ITPC_theta,
    n_permutations=1000, seed=42. Subject p-value is one-tailed.
  - Permutation-validity guard: degenerate distributions (std < 1e-6 or
    > 25% NaN refits) → subject flagged, excluded from aggregation.
  - FDR-BH across subjects via scipy.stats.false_discovery_control(method='bh').
  - Group-level: one-sample t on Fisher-z(β₁). Effect size: Cohen's d.
  - CI: BCa bootstrap n=10000 via scipy.stats.bootstrap(method='BCa').
  - Bonferroni across 3 bands: group-level α=0.017 (θ primary; α/β reported
    only — do not contribute to H1 verdict).
  - MDE guard: if verdict would be REJECTED but |d| < 0.28, downgrade to
    INCONCLUSIVE_UNDERPOWERED (see power_analysis in VERDICT template).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

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
    import statsmodels.api as sm
    from scipy import stats
except ImportError as e:
    sys.exit(f"[FAIL-CLOSED] dependency missing: {e}")

MDE_COHENS_D = 0.28  # minimum detectable effect @ 80% power, n=122, Bonferroni α=0.017
N_PERMUTATIONS = 1000
BOOTSTRAP_N = 10000


def _fdr_bh(pvals: np.ndarray, q: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Return (pass_mask, q_values). Uses scipy.stats.false_discovery_control if
    available (scipy ≥ 1.11); falls back to a manual BH implementation."""
    p = np.asarray(pvals, dtype=float)
    if p.size == 0:
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=float)
    fdc = getattr(stats, "false_discovery_control", None)
    if fdc is not None:
        qvals = fdc(p, method="bh")
        return qvals < q, qvals
    # Manual BH fallback
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    qvals = np.minimum.accumulate((ranked * n / np.arange(1, n + 1))[::-1])[::-1]
    qvals = np.clip(qvals, 0, 1)
    out_q = np.empty_like(qvals)
    out_q[order] = qvals
    return out_q < q, out_q


def _bca_bootstrap_ci(data: np.ndarray, n_resamples: int, seed: int,
                       alpha: float = 0.05) -> tuple[float, float, str]:
    """Return (lo, hi, method). Prefers scipy.stats.bootstrap method='BCa';
    falls back to percentile if scipy version lacks it or sample is degenerate."""
    if data.size < 2:
        return (float(data.mean() if data.size else 0.0),
                float(data.mean() if data.size else 0.0), "degenerate")
    try:
        res = stats.bootstrap((data,), np.mean, n_resamples=n_resamples,
                              method="BCa", random_state=seed, vectorized=False)
        lo, hi = float(res.confidence_interval.low), float(res.confidence_interval.high)
        return lo, hi, "BCa"
    except Exception:
        rng = np.random.default_rng(seed)
        boots = np.array([rng.choice(data, size=data.size, replace=True).mean()
                          for _ in range(n_resamples)])
        return (float(np.quantile(boots, alpha / 2)),
                float(np.quantile(boots, 1 - alpha / 2)),
                "percentile_fallback")


def _wsls_target(correct: np.ndarray) -> np.ndarray:
    """Per-spec: next trial is correct (covers win-stay and lose-shift-correct).
    Returns integer array with -1 for the last trial (undefined)."""
    nxt = np.roll(correct, -1)
    nxt[-1] = 0
    y = (nxt == 1).astype(int)
    y[-1] = -1
    return y


def _fit_subject(h5_path: Path, cluster: list[str], seed: int, log) -> dict:
    """Fit subject-level logit + within-condition permutation null."""
    with h5py.File(h5_path, "r") as h:
        ch_names = [s.decode() for s in h["eeg"].attrs["ch_names"]]
        itpc_theta = h["eeg/itpc_theta"][:]  # (n_ep, n_ch)
        correct = h["behavior/correct"][:]
        rt = h["behavior/rt"][:]
        prev_correct = h["behavior/prev_correct"][:]
        running_acc = h["behavior/running_acc"][:]
        trial_num = h["behavior/trial_num"][:]
        cond = h["behavior/condition"][:]

    idx = [ch_names.index(c) for c in cluster if c in ch_names]
    if not idx:
        return {"status": "error", "reason": f"cluster channels {cluster} absent"}

    x_neural = itpc_theta[:, idx].mean(axis=1)
    y = _wsls_target(correct)
    mask = y >= 0

    n_ok_trials = int(mask.sum())
    if n_ok_trials < 40:
        return {"status": "skipped", "reason": f"too few trials ({n_ok_trials})"}

    X = np.column_stack([x_neural[mask], running_acc[mask], prev_correct[mask],
                         rt[mask], trial_num[mask], cond[mask]])
    X = sm.add_constant(X, has_constant="add")
    y_ = y[mask]

    pos = int(y_.sum())
    neg = len(y_) - pos
    if pos < 10 or neg < 10:
        return {"status": "skipped", "reason": f"class imbalance pos={pos} neg={neg}"}

    try:
        model = sm.Logit(y_, X).fit(disp=0, maxiter=100)
        beta1 = float(model.params[1])
        se = float(model.bse[1])
    except Exception as e:
        return {"status": "error", "reason": f"fit failure: {e}"}

    rng = np.random.default_rng(seed)
    null_beta = np.full(N_PERMUTATIONS, np.nan)
    x0 = X[:, 1].copy()
    cond_vec = cond[mask]
    unique_conds = np.unique(cond_vec)
    for i in range(N_PERMUTATIONS):
        shuffled = x0.copy()
        for c in unique_conds:
            idxc = np.where(cond_vec == c)[0]
            shuffled[idxc] = rng.permutation(shuffled[idxc])
        Xp = X.copy()
        Xp[:, 1] = shuffled
        try:
            m = sm.Logit(y_, Xp).fit(disp=0, maxiter=50)
            null_beta[i] = m.params[1]
        except Exception:
            pass

    null_valid_mask = ~np.isnan(null_beta)
    n_null_valid = int(null_valid_mask.sum())
    null_valid = null_beta[null_valid_mask]
    degeneracy_flags: list[str] = []
    if n_null_valid < int(0.75 * N_PERMUTATIONS):
        degeneracy_flags.append(f"null_refits_valid={n_null_valid}/{N_PERMUTATIONS} (<75%)")
    if n_null_valid >= 2 and null_valid.std(ddof=1) < 1e-6:
        degeneracy_flags.append("null_distribution_std < 1e-6 (degenerate)")

    if n_null_valid < 100:
        return {"status": "error", "reason": f"permutation degenerate; n_valid={n_null_valid}",
                "degeneracy_flags": degeneracy_flags}

    p_perm = float((null_valid >= beta1).mean()) if beta1 >= 0 else float((null_valid <= beta1).mean())

    return {
        "status": "ok",
        "beta1": beta1,
        "se": se,
        "p_perm": p_perm,
        "n_trials": int(len(y_)),
        "class_balance": float(y_.mean()),
        "permutation_null_valid": len(degeneracy_flags) == 0,
        "n_null_valid": n_null_valid,
        "null_std": float(null_valid.std(ddof=1)) if n_null_valid >= 2 else 0.0,
        "degeneracy_flags": degeneracy_flags,
    }


def main() -> None:
    args = parse_std_args("04_existence_test")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])
    _ = require_provenance_freeze(cfg)
    _ = load_qc_summary(cfg)
    log = setup_logging("04_existence_test", cfg)

    features_dir = REPO_ROOT / cfg["paths"]["features_dir"]
    if not features_dir.exists():
        sys.exit(f"[FAIL-CLOSED] features dir missing: {features_dir}")
    manifest_path = features_dir / "FEATURE_STORE_MANIFEST.json"
    if not manifest_path.exists():
        sys.exit(f"[FAIL-CLOSED] FEATURE_STORE_MANIFEST.json missing")
    assert_features_frozen(features_dir)

    manifest = json.loads(manifest_path.read_text())
    cluster = cfg["analysis"]["existence"]["electrode_cluster"]
    log.info("=" * 72)
    log.info(f"Stage 04 — H1 existence test | n_subjects_manifest={len(manifest['subjects'])}")
    log.info(f"cluster={cluster} | n_perm={N_PERMUTATIONS} | bootstrap_n={BOOTSTRAP_N}")
    log.info("=" * 72)

    per_sub: list[dict] = []
    for s in manifest["subjects"]:
        p = Path(s["file"])
        if sha256_file(p) != s["sha256"]:
            sys.exit(f"[FAIL-CLOSED] feature hash mismatch for {s['subject_id']}")
        rep = _fit_subject(p, cluster, cfg["random_seed"], log)
        rep["subject_id"] = s["subject_id"]
        per_sub.append(rep)
        if rep.get("degeneracy_flags"):
            for flag in rep["degeneracy_flags"]:
                log.warning(f"{s['subject_id']}: PERMUTATION-DEGENERACY {flag}")

    ok = [r for r in per_sub if r.get("status") == "ok"]
    betas = np.array([r["beta1"] for r in ok], dtype=float)
    pvals = np.array([r["p_perm"] for r in ok], dtype=float)
    any_degenerate = any(r.get("degeneracy_flags") for r in per_sub)

    if betas.size == 0:
        log.critical("no subjects with valid β₁ — cannot issue verdict")
        append_ledger(cfg, {"stage": "04_existence_test", "status": "HALT",
                            "reason": "no_valid_subjects", "n_total": len(per_sub)})
        sys.exit(2)

    # Fisher-z transform (variance stabilizer) with explicit clip to avoid arctanh(±1)=±inf
    # Per pre-registered protocol: clip beta to [-0.999, 0.999] before arctanh.
    z_betas = np.arctanh(np.clip(betas, -0.999, 0.999))
    t_stat, group_p = stats.ttest_1samp(z_betas, 0.0)

    sign_consistency = float((betas > 0).mean())
    fdr_pass, qvals = _fdr_bh(pvals, q=0.05)

    cohens_d = float(betas.mean() / (betas.std(ddof=1) + 1e-30)) if betas.size > 1 else 0.0
    ci_lo, ci_hi, ci_method = _bca_bootstrap_ci(betas, BOOTSTRAP_N, cfg["random_seed"])

    thresholds = contract["hypotheses"]["H1"]["confirm_threshold"]
    reject = contract["hypotheses"]["H1"]["reject_threshold"]

    if sign_consistency >= thresholds["sign_consistency_min"] and group_p < thresholds["group_t_pvalue_max"]:
        verdict = "CONFIRMED"
    elif sign_consistency <= reject["sign_consistency_max"] or group_p > reject["group_t_pvalue_min"]:
        if abs(cohens_d) < MDE_COHENS_D:
            verdict = "INCONCLUSIVE_UNDERPOWERED"
        else:
            verdict = "REJECTED"
    else:
        verdict = "INCONCLUSIVE"

    effect_direction = ("positive" if (betas > 0).mean() > 0.6
                        else ("negative" if (betas < 0).mean() > 0.6 else "mixed"))
    permutation_valid_group = (not any_degenerate) and all(r.get("permutation_null_valid", False) for r in ok)

    report = {
        "run_id": cfg["run_id"],
        "contract_sha256": contract["_contract_sha256"],
        "config_sha256": cfg["_config_sha256"],
        "n_subjects_ok": len(ok),
        "n_subjects_excluded": len(per_sub) - len(ok),
        "sign_consistency": sign_consistency,
        "beta_mean": float(betas.mean()),
        "beta_sd": float(betas.std(ddof=1)) if betas.size > 1 else 0.0,
        "beta_ci95_bootstrap": [ci_lo, ci_hi],
        "beta_ci_method": ci_method,
        "group_t_statistic": float(t_stat),
        "group_t_pvalue": float(group_p),
        "group_bonferroni_alpha": 0.017,
        "cohens_d": cohens_d,
        "mde_cohens_d_threshold": MDE_COHENS_D,
        "power_constraint_active": bool(abs(cohens_d) < MDE_COHENS_D),
        "effect_direction": effect_direction,
        "permutation_null_valid": permutation_valid_group,
        "n_fdr_pass": int(fdr_pass.sum()),
        "fdr_qvalues": qvals.tolist(),
        "verdict": verdict,
        "per_subject": per_sub,
    }

    out = REPO_ROOT / cfg["paths"]["results_dir"] / "existence_report.json"
    write_json(out, report)
    append_ledger(cfg, {"stage": "04_existence_test",
                        "output": {"report": str(out), "sha256": sha256_file(out),
                                   "verdict": verdict, "cohens_d": cohens_d,
                                   "sign_consistency": sign_consistency,
                                   "group_p": float(group_p),
                                   "power_constraint_active": bool(abs(cohens_d) < MDE_COHENS_D)},
                        "status": "ok"})
    log.info(f"[04_existence_test] verdict={verdict}")
    log.info(f"  sign_cons={sign_consistency:.3f}  group_p={group_p:.4g}  d={cohens_d:.3f}")
    log.info(f"  CI95 ({ci_method}) = [{ci_lo:.4f}, {ci_hi:.4f}]  FDR-passed={int(fdr_pass.sum())}/{len(ok)}")


if __name__ == "__main__":
    main()
