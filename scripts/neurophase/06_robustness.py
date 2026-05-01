#!/usr/bin/env python3
"""Stage 06 — Electrode × frequency robustness (NP-RUN1-S06-v1.1).

Pre-registered operational criteria (see NP-RUN1-VERDICT-v1.1):

  artifact_flag = TRUE  iff  fraction_channels_positive > 0.90 in ALL of:
                             θ, α, β  simultaneously
  On artifact_flag=TRUE → HALT analysis; mandatory ICA re-review before any
  verdict is issued.

  topographic_specificity (for H1 CONFIRMED):
      frontocentral cluster (Fz, FCz, Cz) mean(β₁)  must exceed
      occipital   cluster (O1, Oz, O2)   mean(β₁)  by > 0.5 × SD(across-channel β₁)
  Failure → H1 downgraded to INCONCLUSIVE (not REJECTED).

This stage WRITES the topographic report. Final downgrade is applied by the
analyst when reconciling RUN1_VERDICT.yaml.
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
    write_ledger_halt,
)

try:
    import h5py
    import statsmodels.api as sm
except ImportError as e:
    sys.exit(f"[FAIL-CLOSED] dependency missing: {e}")

FRONTOCENTRAL = ("Fz", "FCz", "Cz")
OCCIPITAL = ("O1", "Oz", "O2")
ARTIFACT_FRAC_POSITIVE_THRESHOLD = 0.90
SPECIFICITY_SD_MARGIN = 0.5


def _per_subject_beta(h5_path: Path, band_key: str) -> tuple[np.ndarray, list[str]]:
    with h5py.File(h5_path, "r") as h:
        ch_names = [s.decode() for s in h["eeg"].attrs["ch_names"]]
        X = h[f"eeg/{band_key}"][:]  # (n_ep, n_ch)
        correct = h["behavior/correct"][:]
        running_acc = h["behavior/running_acc"][:]
        prev_correct = h["behavior/prev_correct"][:]
        rt = h["behavior/rt"][:]
        trial_num = h["behavior/trial_num"][:]
        cond = h["behavior/condition"][:]
    nxt = np.roll(correct, -1)
    nxt[-1] = 0
    y = (nxt == 1).astype(int)
    mask = np.arange(len(y)) < len(y) - 1
    betas = np.full(X.shape[1], np.nan)
    for ci in range(X.shape[1]):
        Z = np.column_stack([X[mask, ci], running_acc[mask], prev_correct[mask], rt[mask],
                             trial_num[mask], cond[mask]])
        Z = sm.add_constant(Z, has_constant="add")
        try:
            m = sm.Logit(y[mask], Z).fit(disp=0, maxiter=80)
            betas[ci] = m.params[1]
        except Exception:
            pass
    return betas, ch_names


def _cluster_mean(betas: np.ndarray, ch_names: list[str], cluster: tuple[str, ...]) -> float | None:
    idx = [ch_names.index(c) for c in cluster if c in ch_names]
    if not idx:
        return None
    v = betas[idx]
    v = v[~np.isnan(v)]
    return float(v.mean()) if v.size else None


def main() -> None:
    args = parse_std_args("06_robustness")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])
    _ = require_provenance_freeze(cfg)
    _ = load_qc_summary(cfg)
    log = setup_logging("06_robustness", cfg)

    features_dir = REPO_ROOT / cfg["paths"]["features_dir"]
    manifest_path = features_dir / "FEATURE_STORE_MANIFEST.json"
    if not manifest_path.exists():
        sys.exit(f"[FAIL-CLOSED] {manifest_path} missing")
    assert_features_frozen(features_dir)
    manifest = json.loads(manifest_path.read_text())

    bands = ("itpc_theta", "itpc_alpha", "itpc_beta")
    all_betas: dict[str, list[np.ndarray]] = {b: [] for b in bands}
    ref_names: list[str] = []

    log.info("=" * 72)
    log.info(f"Stage 06 — robustness | n_subjects={len(manifest['subjects'])} | bands={bands}")
    log.info(f"artifact_threshold frac_positive > {ARTIFACT_FRAC_POSITIVE_THRESHOLD} in ALL bands")
    log.info(f"specificity margin: frontocentral > occipital + {SPECIFICITY_SD_MARGIN}×SD")
    log.info("=" * 72)

    for s in manifest["subjects"]:
        p = Path(s["file"])
        for b in bands:
            betas, ch_names = _per_subject_beta(p, b)
            all_betas[b].append(betas)
            if not ref_names:
                ref_names = ch_names
        log.info(f"{s['subject_id']}: beta maps computed")

    group_by_band = {b: np.nanmean(np.vstack(all_betas[b]), axis=0) for b in bands}
    frac_positive = {b: float(np.mean(group_by_band[b] > 0)) for b in bands}

    artifact_flag = all(frac_positive[b] > ARTIFACT_FRAC_POSITIVE_THRESHOLD for b in bands)

    theta_group = group_by_band["itpc_theta"]
    fc_mean = _cluster_mean(theta_group, ref_names, FRONTOCENTRAL)
    oc_mean = _cluster_mean(theta_group, ref_names, OCCIPITAL)
    cross_sd = float(np.nanstd(theta_group, ddof=1)) if theta_group.size > 1 else 0.0
    if fc_mean is None or oc_mean is None or cross_sd == 0:
        specificity_ok = None
        specificity_ratio = None
    else:
        margin = fc_mean - oc_mean
        specificity_ratio = margin / (cross_sd + 1e-30)
        specificity_ok = bool(specificity_ratio > SPECIFICITY_SD_MARGIN)

    report = {
        "run_id": cfg["run_id"],
        "contract_sha256": contract["_contract_sha256"],
        "n_subjects": len(manifest["subjects"]),
        "ch_names": ref_names,
        "group_beta_by_band": {b: group_by_band[b].tolist() for b in bands},
        "fraction_positive_by_band": frac_positive,
        "fraction_positive_theta": frac_positive["itpc_theta"],
        "fraction_positive_alpha": frac_positive["itpc_alpha"],
        "fraction_positive_beta": frac_positive["itpc_beta"],
        "artifact_threshold": ARTIFACT_FRAC_POSITIVE_THRESHOLD,
        "artifact_flag": artifact_flag,
        "frontocentral_cluster": list(FRONTOCENTRAL),
        "occipital_cluster": list(OCCIPITAL),
        "frontocentral_mean_theta": fc_mean,
        "occipital_mean_theta": oc_mean,
        "across_channel_sd_theta": cross_sd,
        "frontocentral_vs_occipital_sd_ratio": specificity_ratio,
        "topographic_specificity_ok": specificity_ok,
        "specificity_margin_sd": SPECIFICITY_SD_MARGIN,
        "effect_specific_to_theta_frontocentral": bool(specificity_ok) if specificity_ok is not None else None,
    }

    out = REPO_ROOT / cfg["paths"]["results_dir"] / "robustness_report.json"
    write_json(out, report)

    status = "halt" if artifact_flag else "ok"
    append_ledger(cfg, {"stage": "06_robustness",
                        "output": {"report": str(out), "sha256": sha256_file(out),
                                   "artifact_flag": artifact_flag,
                                   "fraction_positive_by_band": frac_positive,
                                   "topographic_specificity_ok": specificity_ok,
                                   "frontocentral_vs_occipital_sd_ratio": specificity_ratio},
                        "status": status})

    log.info(f"frac_positive: θ={frac_positive['itpc_theta']:.3f}  α={frac_positive['itpc_alpha']:.3f}  "
             f"β={frac_positive['itpc_beta']:.3f}")
    log.info(f"θ frontocentral mean={fc_mean}, occipital mean={oc_mean}, "
             f"FC-OC/SD={specificity_ratio}")
    log.info(f"artifact_flag={artifact_flag}  topographic_specificity_ok={specificity_ok}")

    if artifact_flag:
        write_ledger_halt(cfg, "06_robustness", "artifact_flag_triggered",
                          {"fraction_positive_by_band": frac_positive,
                           "threshold": ARTIFACT_FRAC_POSITIVE_THRESHOLD})
        sys.exit("[FAIL-CLOSED] Robustness: all bands frac_positive > 0.90 — artifact suspected. "
                 "HALT analysis, return to preprocessing, ICA re-review required.")


if __name__ == "__main__":
    main()
