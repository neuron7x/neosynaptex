#!/usr/bin/env python3
"""Stage 02 — Unified QC: channel + behavioral + epoch-preview (NP-RUN1-S02-v1.1).

Reads ingestion_manifest.json (frozen by Stage 01). Processes ok+flagged
subjects. Does NOT modify raw data. Does NOT preprocess (no filtering,
no ICA — those belong to Stage 03).

For each subject:
  - Channel QC (MNE-based): flat (std < 0.5 μV), noisy (|z| > 3.5 variance),
    unioned with upstream-bad from provenance
  - Behavioral QC: missing-response fraction, RT bounds, AB last-50 accuracy
  - Epoch-preview: count of response-locked epochs within valid RT that would
    survive amplitude rejection; per-condition counts
  - Per-subject sub-{N}_qc.json written

Aggregation:
  - QC_SUMMARY.yaml with analyst_lock: false (must be set true manually)
  - EXCLUDED_SUBJECTS.yaml updated with QC-stage exclusions
  - HALT if > 30% subjects excluded across QC stages (configurable)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from _common import (
    REPO_ROOT,
    SEV_ERROR,
    SEV_FLAG,
    SEV_WARN,
    append_ledger,
    enforce_pipeline_halt_fraction,
    evaluate_rules,
    load_config,
    load_contract,
    parse_std_args,
    require_provenance_freeze,
    set_global_seed,
    setup_logging,
    sha256_file,
    utc_now_iso,
    write_json,
    write_yaml,
    write_ledger_halt,
)

try:
    import mne
    mne.set_log_level("ERROR")
except ImportError:
    sys.exit("[FAIL-CLOSED] mne not installed; pip install mne")


BEHAVIORAL_RULES = [
    {"rule_id": "BH-R01", "description": "Missing response fraction > 0.20",
     "severity": SEV_ERROR, "detail_key": "missing_frac", "threshold": 0.20, "operator": "gt"},
    {"rule_id": "BH-R02", "description": "AB last-50 accuracy < 0.55 (non-learner)",
     "severity": SEV_ERROR, "detail_key": "ab_last50_below_floor", "threshold": 0, "operator": "gt"},
    {"rule_id": "BH-R03", "description": "AB last-50 accuracy > 0.95 (ceiling — suspect data)",
     "severity": SEV_ERROR, "detail_key": "ab_last50_above_ceiling", "threshold": 0, "operator": "gt"},
    {"rule_id": "BH-R04", "description": "AB pair has < 50 trials — learning curve unverifiable",
     "severity": SEV_FLAG, "detail_key": "ab_trials_under_50", "threshold": 0, "operator": "gt"},
]

CHANNEL_RULES = [
    {"rule_id": "CH-R01", "description": "Bad channel fraction > 0.15 — subject excluded",
     "severity": SEV_ERROR, "detail_key": "bad_frac", "threshold": 0.15, "operator": "gt"},
    {"rule_id": "CH-R02", "description": "Cz reference electrode absent in raw",
     "severity": SEV_WARN, "detail_key": "cz_absent", "threshold": 0, "operator": "gt"},
    {"rule_id": "CH-R03", "description": "Fewer than 60 channels — topography sparse",
     "severity": SEV_WARN, "detail_key": "few_channels", "threshold": 0, "operator": "gt"},
]


def _behavioral_qc(events_path: Path, cfg: dict, sub_id: str, log) -> dict:
    b = cfg["behavioral_qc"]
    df = pd.read_csv(events_path, sep="\t")
    n_trials = len(df)

    # Missing response: response_time NaN or out of bounds
    rt_s = pd.to_numeric(df.get("response_time", pd.Series([np.nan] * n_trials)), errors="coerce")
    missing = rt_s.isna() | (rt_s < b["rt_min_ms"] / 1000) | (rt_s > b["rt_max_ms"] / 1000)
    miss_frac = float(missing.mean()) if n_trials else 0.0

    # AB pair accuracy (last 50)
    ab_mask = df.get("trial_type", pd.Series([""] * n_trials)).astype(str).str.upper().str.contains("AB")
    ab_trials = df[ab_mask]
    if len(ab_trials) >= 50:
        acc = float(pd.to_numeric(ab_trials["correct"], errors="coerce").tail(50).mean())
    else:
        acc = None

    below_floor = int(acc is not None and acc < b["ab_accuracy_last50_min"])
    above_ceil = int(acc is not None and acc > b["ab_accuracy_last50_max"])
    ab_under_50 = int(0 < len(ab_trials) < 50)

    values = {
        "missing_frac": miss_frac,
        "ab_last50_below_floor": below_floor,
        "ab_last50_above_ceiling": above_ceil,
        "ab_trials_under_50": ab_under_50,
    }
    fired = evaluate_rules(BEHAVIORAL_RULES, values, log, sub_id)
    exclude = any(f["severity"] == SEV_ERROR for f in fired)

    cond_counts = Counter(df["trial_type"].astype(str)) if "trial_type" in df.columns else Counter()
    return {
        "n_trials": int(n_trials),
        "missing_response_fraction": miss_frac,
        "ab_accuracy_last50": acc,
        "ab_n_trials": int(len(ab_trials)),
        "conditions_present": sorted(cond_counts.keys()),
        "n_per_condition": dict(cond_counts),
        "rules_fired": fired,
        "exclude": exclude,
        "exclusion_reason": "; ".join(f["description"] for f in fired if f["severity"] == SEV_ERROR) or None,
    }


def _channel_qc(eeg_set: Path, cfg: dict, sub_id: str, channels_audit: dict, log) -> dict:
    chn = cfg["channel_qc"]
    try:
        raw = mne.io.read_raw_eeglab(str(eeg_set), preload=True, verbose="ERROR")
    except Exception as e:
        log.error(f"{sub_id}: MNE load failure: {e}")
        return {"exclude": True, "exclusion_reason": f"MNE load failure: {e}", "rules_fired": []}

    ch_names = list(raw.ch_names)
    sfreq = float(raw.info["sfreq"])
    data = raw.get_data()
    stds = data.std(axis=1) * 1e6  # μV

    flat = [c for c, s in zip(ch_names, stds) if s < chn["flat_threshold_uV"]]
    ch_var = (stds ** 2)
    z = (ch_var - ch_var.mean()) / (ch_var.std() + 1e-12)
    noisy = [c for c, zz in zip(ch_names, z) if abs(zz) > chn["noise_zscore"]]
    upstream_bad = list(channels_audit.get("bad_channels_upstream", [])) if channels_audit else []
    upstream_interp = list(channels_audit.get("interpolated_channels", [])) if channels_audit else []
    bad = sorted(set(flat) | set(noisy) | set(upstream_bad) | set(upstream_interp))
    bad_frac = len(bad) / max(1, len(ch_names))

    values = {
        "bad_frac": bad_frac,
        "cz_absent": int("Cz" not in ch_names),
        "few_channels": int(len(ch_names) < 60),
    }
    fired = evaluate_rules(CHANNEL_RULES, values, log, sub_id)
    exclude = any(f["severity"] == SEV_ERROR for f in fired)

    return {
        "n_channels_raw": len(ch_names),
        "sampling_rate_hz": sfreq,
        "duration_sec": float(raw.n_times / sfreq),
        "flat_channels": flat,
        "noisy_channels": noisy,
        "upstream_bad": upstream_bad,
        "upstream_interpolated": upstream_interp,
        "bad_channels": bad,
        "n_bad_channels": len(bad),
        "bad_fraction": round(bad_frac, 4),
        "cz_present": ("Cz" in ch_names),
        "rules_fired": fired,
        "exclude": exclude,
        "exclusion_reason": "; ".join(f["description"] for f in fired if f["severity"] == SEV_ERROR) or None,
    }


def _epoch_preview(eeg_set: Path, events_path: Path, cfg: dict, sub_id: str, log) -> dict:
    """Count likely-surviving response-locked epochs (no filtering applied).
    This is a feasibility preview — real preprocessing happens in Stage 03.
    """
    try:
        raw = mne.io.read_raw_eeglab(str(eeg_set), preload=True, verbose="ERROR")
    except Exception as e:
        return {"exclude": True, "exclusion_reason": f"load failure: {e}"}

    b = cfg["behavioral_qc"]
    epoch_qc = cfg["epoch_qc"]
    sfreq = float(raw.info["sfreq"])

    df = pd.read_csv(events_path, sep="\t")
    onset = pd.to_numeric(df.get("onset"), errors="coerce")
    rt = pd.to_numeric(df.get("response_time"), errors="coerce")
    valid = onset.notna() & rt.notna() & (rt >= b["rt_min_ms"] / 1000) & (rt <= b["rt_max_ms"] / 1000)
    resp_s = (onset + rt).where(valid)
    n_valid = int(valid.sum())

    tmin, tmax = cfg["preprocessing"]["epoch_window_s"]
    pre_samp = int(abs(tmin) * sfreq)
    post_samp = int(abs(tmax) * sfreq)
    n_times = raw.n_times

    survive = 0
    ptp_thresh = epoch_qc["peak_to_peak_uV_max"] * 1e-6
    data = raw.get_data()
    idx_samp = (resp_s.dropna().values * sfreq).astype(int)
    for s in idx_samp:
        lo, hi = s - pre_samp, s + post_samp
        if lo < 0 or hi >= n_times:
            continue
        seg = data[:, lo:hi]
        ptp = seg.max(axis=1) - seg.min(axis=1)
        if (ptp <= ptp_thresh).all():
            survive += 1

    cond = df.loc[valid & resp_s.notna(), "trial_type"].astype(str)
    cond_counts = Counter(cond.values)

    under_total = survive < epoch_qc["min_epochs_total"]
    under_cond = any(c < epoch_qc["min_epochs_per_condition"] for c in cond_counts.values())

    return {
        "n_valid_events": n_valid,
        "n_preview_surviving": int(survive),
        "preview_cond_counts": dict(cond_counts),
        "under_total_min": bool(under_total),
        "under_condition_min": bool(under_cond),
        "exclude": bool(under_total),
        "exclusion_reason": f"preview_surviving={survive} < min_epochs_total" if under_total else None,
    }


def main() -> None:
    args = parse_std_args("02_qc")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])
    _ = require_provenance_freeze(cfg)
    log = setup_logging("02_qc", cfg)

    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]
    manifest_path = qc_dir / "ingestion_manifest.json"
    if not manifest_path.exists():
        sys.exit(f"[FAIL-CLOSED] run stage 01 first; missing {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    subjects = manifest["subjects"]
    log.info("=" * 72)
    log.info(f"Stage 02 — unified QC | n_manifest_subjects={len(subjects)}")
    log.info("=" * 72)

    per_subject: list[dict] = []
    for rec in subjects:
        sid = rec["subject_id"]
        if rec["status"] != "ok":
            log.info(f"{sid}: skipped (ingestion status={rec['status']})")
            continue

        ch_audit = rec.get("channels_audit") or {}
        log.info(f"{sid}: running QC …")

        bh = _behavioral_qc(Path(rec["events_path"]), cfg, sid, log)
        if bh["exclude"]:
            out = {"subject_id": sid, "behavioral": bh, "channel": None, "epoch_preview": None,
                   "qc_timestamp": utc_now_iso(), "exclude_stage": "behavioral",
                   "exclusion_reason": bh["exclusion_reason"]}
            write_json(qc_dir / f"{sid}_qc.json", out)
            per_subject.append(out)
            continue

        ch = _channel_qc(Path(rec["eeg_set_path"]), cfg, sid, ch_audit, log)
        if ch.get("exclude"):
            out = {"subject_id": sid, "behavioral": bh, "channel": ch, "epoch_preview": None,
                   "qc_timestamp": utc_now_iso(), "exclude_stage": "channel",
                   "exclusion_reason": ch.get("exclusion_reason")}
            write_json(qc_dir / f"{sid}_qc.json", out)
            per_subject.append(out)
            continue

        ep = _epoch_preview(Path(rec["eeg_set_path"]), Path(rec["events_path"]), cfg, sid, log)
        out = {
            "subject_id": sid, "behavioral": bh, "channel": ch, "epoch_preview": ep,
            "qc_timestamp": utc_now_iso(),
            "exclude_stage": ("epoch_preview" if ep.get("exclude") else None),
            "exclusion_reason": ep.get("exclusion_reason"),
        }
        write_json(qc_dir / f"{sid}_qc.json", out)
        per_subject.append(out)

    if args.dry_run:
        log.info(f"DRY RUN — processed {len(per_subject)} subjects, no aggregation written.")
        return

    agg_path = qc_dir / "qc_aggregate.json"
    write_json(agg_path, per_subject)

    excl_path = qc_dir / "EXCLUDED_SUBJECTS.yaml"
    existing = yaml.safe_load(excl_path.read_text()) if excl_path.exists() else {}
    existing = existing or {}

    behavioral_excl = [{"subject_id": r["subject_id"], "reason": r["exclusion_reason"]}
                       for r in per_subject if r.get("exclude_stage") == "behavioral"]
    channel_excl = [{"subject_id": r["subject_id"], "reason": r["exclusion_reason"]}
                    for r in per_subject if r.get("exclude_stage") == "channel"]
    epoch_excl = [{"subject_id": r["subject_id"], "reason": r["exclusion_reason"]}
                  for r in per_subject if r.get("exclude_stage") == "epoch_preview"]

    existing["behavioral_exclusions"] = behavioral_excl
    existing["channel_exclusions"] = channel_excl
    existing["epoch_preview_exclusions"] = epoch_excl
    write_yaml(excl_path, existing)

    n_ingested_ok = sum(1 for s in subjects if s["status"] == "ok")
    n_final_pre_preproc = sum(1 for r in per_subject if r.get("exclude_stage") is None)

    summary = {
        "run_id": cfg["run_id"],
        "stage": "02_qc",
        "contract_sha256": contract["_contract_sha256"],
        "config_sha256": cfg["_config_sha256"],
        "n_subjects_ingested_ok": n_ingested_ok,
        "n_excluded_behavioral": len(behavioral_excl),
        "n_excluded_channel": len(channel_excl),
        "n_excluded_epoch_preview": len(epoch_excl),
        "n_subjects_candidate_for_preprocessing": n_final_pre_preproc,
        "exclusion_log": str(excl_path.resolve()),
        "qc_completion_timestamp": utc_now_iso(),
        "analyst_lock": False,
    }
    summary_path = qc_dir / "QC_SUMMARY.yaml"
    write_yaml(summary_path, summary)

    enforce_pipeline_halt_fraction(
        n_ingested_ok - n_final_pre_preproc, n_ingested_ok,
        limit=0.30, cfg=cfg, stage="02_qc", logger=log,
    )

    append_ledger(cfg, {
        "stage": "02_qc",
        "input": {"manifest_sha256": sha256_file(manifest_path)},
        "output": {"aggregate": str(agg_path), "aggregate_sha256": sha256_file(agg_path),
                   "summary": str(summary_path), "summary_sha256": sha256_file(summary_path),
                   "n_candidate_preproc": n_final_pre_preproc,
                   "n_excluded_behavioral": len(behavioral_excl),
                   "n_excluded_channel": len(channel_excl),
                   "n_excluded_epoch_preview": len(epoch_excl)},
        "status": "ok",
    })
    log.info(f"[02_qc] DONE — candidate_for_preproc={n_final_pre_preproc}")
    log.info(f"  MANUAL: review {summary_path} and set analyst_lock: true before stage 03.")


if __name__ == "__main__":
    main()
