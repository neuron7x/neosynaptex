#!/usr/bin/env python3
"""Stage 03 — Preprocessing (NP-RUN1-S03-v1.1).

Preprocessing chain (immutable order; deviation = pipeline invalidation):
  1. Load raw EEGLAB .set (MNE)
  2. Apply standard_1020 montage
  3. Annotate bad channels from Stage 02 output
  4. Bandpass 0.1–40 Hz (FIR, hamming, order=auto)
  5. Notch 50 Hz + 100 Hz (EU power line)
  6. Interpolate bad channels (spherical spline)
  7. Average reference
  8. ICA fit on 1–40 Hz copy (FastICA, 20 comps, seeded)
  9. Identify ocular components via Fp1/Fp2 correlation; ≤ 3 removed
 10. Apply ICA to 0.1–40 Hz filtered signal
 11. Epoch response-locked [-0.5, 1.0] s; baseline [-0.2, 0] s
 12. Epoch rejection: PTP > 150 μV, EOG proxy > 100 μV, muscle HF
 13. Save response-locked epo.fif + ICA weights per subject

Reads:   neurophase/qc/ingestion_manifest.json (frozen)
         neurophase/qc/qc_aggregate.json
         neurophase/qc/QC_SUMMARY.yaml (analyst_lock: true)
Writes:  neurophase/preproc/sub-{N}_task-pst_response-locked-epo.fif
         neurophase/qc/ica/sub-{N}_ica.fif
         neurophase/qc/preprocess_aggregate.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from _common import (
    REPO_ROOT,
    append_ledger,
    enforce_pipeline_halt_fraction,
    load_config,
    load_contract,
    load_qc_summary,
    parse_std_args,
    require_provenance_freeze,
    set_global_seed,
    setup_logging,
    sha256_file,
    utc_now_iso,
    write_json,
    write_yaml,
)

try:
    import mne
    from mne.preprocessing import ICA
    mne.set_log_level("ERROR")
except ImportError:
    sys.exit("[FAIL-CLOSED] mne not installed; pip install mne")


def _preprocess_one(ingest_rec: dict, qc_rec: dict, cfg: dict, out_dir: Path, ica_dir: Path, log) -> dict:
    sid = ingest_rec["subject_id"]
    pre = cfg["preprocessing"]
    ica_cfg = cfg["ica"]
    epoch_qc = cfg["epoch_qc"]
    seed = int(cfg["random_seed"])

    raw = mne.io.read_raw_eeglab(ingest_rec["eeg_set_path"], preload=True, verbose="ERROR")
    try:
        raw.set_montage(pre["montage"], match_case=False, on_missing="warn")
    except Exception as e:
        return {"status": "error", "subject_id": sid, "reason": f"montage: {e}"}

    bad_channels = list((qc_rec.get("channel") or {}).get("bad_channels", []))
    raw.info["bads"] = [b for b in bad_channels if b in raw.ch_names]

    raw.filter(l_freq=pre["bandpass_hz"][0], h_freq=pre["bandpass_hz"][1], verbose="ERROR")
    nyq = raw.info["sfreq"] / 2
    notch_freqs = [f for f in (pre["notch_hz"], 2 * pre["notch_hz"]) if f < nyq]
    if notch_freqs:
        raw.notch_filter(freqs=notch_freqs, verbose="ERROR")

    if raw.info["bads"]:
        raw.interpolate_bads(reset_bads=True, verbose="ERROR")
    raw.set_eeg_reference(pre["reference"], verbose="ERROR")

    raw_ica = raw.copy().filter(l_freq=ica_cfg["fit_band_hz"][0], h_freq=ica_cfg["fit_band_hz"][1], verbose="ERROR")
    ica = ICA(n_components=int(ica_cfg["n_components"]), method="fastica",
              random_state=seed, max_iter="auto")
    ica.fit(raw_ica, verbose="ERROR")

    eog_chs = [c for c in ("Fp1", "Fp2") if c in raw.ch_names]
    excl_ic: list[int] = []
    if eog_chs:
        try:
            eog_inds, _ = ica.find_bads_eog(raw, ch_name=eog_chs[0],
                                             threshold=ica_cfg["eog_correlation_threshold"],
                                             verbose="ERROR")
            excl_ic = list(eog_inds)[: int(ica_cfg["max_components_removed"])]
        except Exception:
            excl_ic = []
    ica.exclude = excl_ic
    ica.save(ica_dir / f"{sid}_ica.fif", overwrite=True)
    raw_clean = ica.apply(raw.copy(), verbose="ERROR")

    events_df = pd.read_csv(ingest_rec["events_path"], sep="\t")
    sfreq = raw_clean.info["sfreq"]
    onset = pd.to_numeric(events_df["onset"], errors="coerce")
    rt = pd.to_numeric(events_df["response_time"], errors="coerce")
    valid = onset.notna() & rt.notna() & (rt > 0)
    resp_s = (onset + rt).where(valid)
    samp = (resp_s.dropna().values * sfreq).astype(int)
    trial_type = events_df.loc[resp_s.notna(), "trial_type"].astype(str).values
    ev_id_map: dict[str, int] = {t: i + 1 for i, t in enumerate(sorted(set(trial_type)))}
    events = np.column_stack([samp, np.zeros_like(samp),
                              np.array([ev_id_map[t] for t in trial_type])]).astype(int)

    tmin, tmax = pre["epoch_window_s"]
    bmin, bmax = pre["baseline_window_s"]
    epochs = mne.Epochs(raw_clean, events, event_id=ev_id_map, tmin=tmin, tmax=tmax,
                        baseline=(bmin, bmax), preload=True, reject=None, verbose="ERROR")

    ptp_uv = epoch_qc["peak_to_peak_uV_max"] * 1e-6
    d = epochs.get_data()
    ptp = d.max(axis=2) - d.min(axis=2)
    reject_ptp = (ptp > ptp_uv).any(axis=1)

    reject_eog = np.zeros(len(epochs), dtype=bool)
    for ch in ("Fp1", "Fp2"):
        if ch in epochs.ch_names:
            idx = epochs.ch_names.index(ch)
            reject_eog |= (np.abs(d[:, idx, :]).max(axis=1) > epoch_qc["eog_proxy_amp_uV_max"] * 1e-6)

    mlo, mhi = epoch_qc["muscle_hf_band_hz"]
    reject_muscle = np.zeros(len(epochs), dtype=bool)
    if mhi < sfreq / 2:
        try:
            psd = epochs.compute_psd(method="multitaper", fmin=mlo, fmax=mhi, verbose="ERROR")
            hf_power = psd.get_data().mean(axis=(1, 2))
            mu, sd = hf_power.mean(), hf_power.std() + 1e-30
            reject_muscle = (hf_power - mu) / sd > epoch_qc["muscle_sigma_multiple"]
        except Exception:
            pass

    keep = ~(reject_ptp | reject_eog | reject_muscle)
    epochs_clean = epochs[keep]

    n_kept = len(epochs_clean)
    cond_counts = {k: int(np.sum(epochs_clean.events[:, 2] == v)) for k, v in ev_id_map.items()}
    under_any = any(c < cfg["epoch_qc"]["min_epochs_per_condition"] for c in cond_counts.values() if c > 0)
    under_total = n_kept < cfg["epoch_qc"]["min_epochs_total"]

    out_path = out_dir / f"{sid}_task-pst_response-locked-epo.fif"
    epochs_clean.save(out_path, overwrite=True)

    return {
        "status": "ok",
        "subject_id": sid,
        "n_epochs_total": int(len(epochs)),
        "n_epochs_kept": int(n_kept),
        "rejected_ptp": int(reject_ptp.sum()),
        "rejected_eog": int(reject_eog.sum()),
        "rejected_muscle": int(reject_muscle.sum()),
        "cond_counts": cond_counts,
        "under_condition_min": bool(under_any),
        "under_total_min": bool(under_total),
        "ica_removed": [int(x) for x in excl_ic],
        "ica_n_removed": len(excl_ic),
        "ica_flagged_over_max": len(excl_ic) >= int(ica_cfg["max_components_removed"]),
        "bad_channels_used": list(raw.info["bads"]) if raw.info["bads"] else bad_channels,
        "epo_path": str(out_path.resolve()),
        "timestamp": utc_now_iso(),
    }


def main() -> None:
    args = parse_std_args("03_preprocess")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])
    _ = require_provenance_freeze(cfg)
    _ = load_qc_summary(cfg)
    log = setup_logging("03_preprocess", cfg)

    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]
    preproc_dir = REPO_ROOT / cfg["paths"]["preproc_dir"]
    preproc_dir.mkdir(parents=True, exist_ok=True)
    ica_dir = qc_dir / "ica"
    ica_dir.mkdir(parents=True, exist_ok=True)

    manifest_obj = json.loads((qc_dir / "ingestion_manifest.json").read_text())
    qc_agg = json.loads((qc_dir / "qc_aggregate.json").read_text())
    manifest = {r["subject_id"]: r for r in manifest_obj["subjects"]}
    qc_by_sub = {r["subject_id"]: r for r in qc_agg}

    candidates = [sid for sid, qc in qc_by_sub.items() if qc.get("exclude_stage") is None]
    log.info("=" * 72)
    log.info(f"Stage 03 — preprocess | candidates={len(candidates)}")
    log.info("=" * 72)

    reports: list[dict] = []
    exclusions: list[dict] = []
    for sid in candidates:
        if manifest[sid]["status"] != "ok":
            continue
        out_path = preproc_dir / f"{sid}_task-pst_response-locked-epo.fif"
        ica_path = ica_dir / f"{sid}_ica.fif"
        if out_path.exists() and ica_path.exists():
            log.info(f"{sid}: RESUME — epoch + ICA already present, skipping preprocess")
            try:
                ep = mne.read_epochs(out_path, preload=False, verbose="ERROR")
                cond_counts = {k: int((ep.events[:, 2] == v).sum()) for k, v in ep.event_id.items()}
                r = {"status": "ok", "subject_id": sid, "resumed": True,
                     "n_epochs_kept": len(ep), "cond_counts": cond_counts,
                     "under_total_min": len(ep) < cfg["epoch_qc"]["min_epochs_total"],
                     "under_condition_min": any(c < cfg["epoch_qc"]["min_epochs_per_condition"]
                                                 for c in cond_counts.values()),
                     "epo_path": str(out_path.resolve()),
                     "timestamp": utc_now_iso()}
            except Exception as e:
                log.warning(f"{sid}: resume read failed ({e}); reprocessing")
                r = None
            if r is not None:
                reports.append(r)
                if r.get("under_total_min"):
                    exclusions.append({"subject_id": sid, "stage": "preprocessing",
                                       "reason": f"kept={r['n_epochs_kept']} < min_total"})
                continue
        log.info(f"{sid}: preprocessing …")
        try:
            r = _preprocess_one(manifest[sid], qc_by_sub[sid], cfg, preproc_dir, ica_dir, log)
        except Exception as e:
            r = {"status": "error", "subject_id": sid, "reason": str(e)}
        reports.append(r)
        if r["status"] != "ok" or r.get("under_total_min"):
            exclusions.append({"subject_id": sid, "stage": "preprocessing",
                               "reason": r.get("reason", f"kept={r.get('n_epochs_kept', 0)} < min_total")})

    if args.dry_run:
        log.info(f"DRY RUN — {len(reports)} subjects processed (virtually).")
        return

    agg_path = qc_dir / "preprocess_aggregate.json"
    write_json(agg_path, reports)

    excl_path = qc_dir / "EXCLUDED_SUBJECTS.yaml"
    existing = yaml.safe_load(excl_path.read_text()) if excl_path.exists() else {}
    existing = existing or {}
    existing["preprocessing_exclusions"] = exclusions
    write_yaml(excl_path, existing)

    n_ok = sum(1 for r in reports if r["status"] == "ok" and not r.get("under_total_min"))
    enforce_pipeline_halt_fraction(len(exclusions), len(reports), limit=0.20,
                                    cfg=cfg, stage="03_preprocess", logger=log)

    # Update QC_SUMMARY with final preprocessing counts
    summary_path = qc_dir / "QC_SUMMARY.yaml"
    summary = yaml.safe_load(summary_path.read_text()) or {}
    summary["n_subjects_preprocessed"] = n_ok
    summary["n_preprocessing_exclusions"] = len(exclusions)
    summary["preprocessing_completion_timestamp"] = utc_now_iso()
    write_yaml(summary_path, summary)

    append_ledger(cfg, {"stage": "03_preprocess",
                        "output": {"aggregate": str(agg_path), "sha256": sha256_file(agg_path),
                                   "preproc_dir": str(preproc_dir),
                                   "n_ok": n_ok, "n_excluded": len(exclusions)},
                        "status": "ok"})
    log.info(f"[03_preprocess] ok — final cohort size: {n_ok} (excluded at preprocess: {len(exclusions)})")


if __name__ == "__main__":
    main()
