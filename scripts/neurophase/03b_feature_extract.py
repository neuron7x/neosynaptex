#!/usr/bin/env python3
"""Stage 03b — Feature extraction → frozen HDF5 store.

Per subject writes features/sub-{N}_features.h5 with:
  /eeg/itpc_theta|alpha|beta   shape (n_epochs, n_channels)
  /eeg/phase_theta             shape (n_epochs, n_channels)  single-trial phase at t=0
  /erp/frn, /erp/p300          shape (n_epochs,)
  /behavior/*                  correct, rt, prev_correct, running_acc, trial_num, condition

On completion: writes FEATURE_STORE_MANIFEST.json with SHA-256 per file.
Analyst must then manually `chmod -R a-w features/` (see docs/neurophase/RUN1_EXECUTION.md).
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
    load_config,
    load_contract,
    load_qc_summary,
    parse_std_args,
    require_provenance_freeze,
    set_global_seed,
    sha256_file,
    utc_now_iso,
    write_json,
)

try:
    import h5py
    import mne
    from mne.time_frequency import tfr_morlet
except ImportError as e:
    sys.exit(f"[FAIL-CLOSED] dependency missing: {e}")


def _single_trial_phase(epochs: mne.Epochs, freqs: np.ndarray, n_cycles,
                        window_s: tuple[float, float]) -> np.ndarray:
    """Return per-trial phase averaged over the ITPC window, per channel at band-mean freq.
    n_cycles may be scalar or array; if scalar, a frequency-adaptive array is built
    that caps wavelet length at the epoch length (n_cycles_i = max(3, freq/2))."""
    sfreq = float(epochs.info["sfreq"])
    n_times = int(epochs.times.size)
    # MNE wavelet length ≈ 2 * n_cycles * sfreq / freq (two-sided Gaussian).
    # Require wavelet strictly shorter than epoch signal; keep 20% margin.
    max_cycles_per_freq = 0.4 * n_times * freqs / sfreq
    if np.isscalar(n_cycles):
        candidate = np.full_like(freqs, float(n_cycles), dtype=float)
    else:
        candidate = np.asarray(n_cycles, dtype=float)
    n_cycles_arr = np.minimum(candidate, max_cycles_per_freq)
    n_cycles_arr = np.maximum(n_cycles_arr, np.minimum(2.0, max_cycles_per_freq))
    tfr = tfr_morlet(epochs, freqs=freqs, n_cycles=n_cycles_arr, return_itc=False,
                     average=False, output="phase", verbose="ERROR")
    # tfr.data: (n_epochs, n_ch, n_freq, n_times)
    t = tfr.times
    mask = (t >= window_s[0]) & (t <= window_s[1])
    phase = tfr.data[..., mask].mean(axis=-1)  # → (epochs, ch, freq)
    return phase


def _itpc_from_phase(phase: np.ndarray) -> np.ndarray:
    """ITPC per (channel, freq) across epochs. phase: (epochs, ch, freq) → (ch, freq)."""
    return np.abs(np.exp(1j * phase).mean(axis=0))


def _band_mean_freqs(bands_cfg: dict, all_freqs: list[float]) -> dict[str, np.ndarray]:
    out = {}
    for name, (lo, hi) in bands_cfg.items():
        sel = np.array([f for f in all_freqs if lo <= f <= hi])
        out[name] = sel
    return out


def _erp_peak(epochs: mne.Epochs, chs: list[str], tmin: float, tmax: float, kind: str = "neg") -> np.ndarray:
    present = [c for c in chs if c in epochs.ch_names]
    if not present:
        return np.full(len(epochs), np.nan)
    picks = mne.pick_channels(epochs.ch_names, include=present)
    data = epochs.get_data(picks=picks).mean(axis=1)
    t = epochs.times
    mask = (t >= tmin) & (t <= tmax)
    seg = data[:, mask]
    return seg.min(axis=1) if kind == "neg" else seg.max(axis=1)


def _behavior_block(events_df: pd.DataFrame) -> dict[str, np.ndarray]:
    df = events_df.copy()
    df["correct"] = pd.to_numeric(df["correct"], errors="coerce").fillna(0).astype(int)
    df["rt"] = pd.to_numeric(df["response_time"], errors="coerce")
    df["prev_correct"] = df["correct"].shift(1).fillna(0).astype(int)
    df["running_acc"] = df["correct"].rolling(5, min_periods=1).mean()
    df["trial_num"] = np.arange(len(df))
    cond_map = {v: i for i, v in enumerate(sorted(df["trial_type"].astype(str).unique()))}
    df["condition"] = df["trial_type"].astype(str).map(cond_map).fillna(-1).astype(int)
    return {
        "correct": df["correct"].to_numpy(),
        "rt": df["rt"].to_numpy(),
        "prev_correct": df["prev_correct"].to_numpy(),
        "running_acc": df["running_acc"].to_numpy(),
        "trial_num": df["trial_num"].to_numpy(),
        "condition": df["condition"].to_numpy(),
    }, cond_map


def _extract_one(sub_id: str, epo_path: Path, events_path: Path, cfg: dict, contract: dict, out_path: Path) -> dict:
    epochs = mne.read_epochs(epo_path, preload=True, verbose="ERROR")
    feat = cfg["features"]
    freqs_all = [float(x) for x in feat["wavelet"]["freqs_hz"]]
    n_cycles = float(feat["wavelet"]["n_cycles"])
    win = tuple(feat["itpc_window_s"])

    bands = _band_mean_freqs(feat["bands"], freqs_all)
    for bname, farr in bands.items():
        if farr.size == 0:
            raise RuntimeError(f"no wavelet freqs cover band {bname}")

    freqs_np = np.array(freqs_all)
    phase = _single_trial_phase(epochs, freqs_np, n_cycles, win)  # (ep, ch, freq)

    # Per-band single-trial phase (mean angle across band freqs, via circular mean)
    def circ_mean(arr: np.ndarray, axis: int) -> np.ndarray:
        z = np.exp(1j * arr).mean(axis=axis)
        return np.angle(z)

    def band_idx(name: str) -> np.ndarray:
        return np.array([i for i, f in enumerate(freqs_all) if bands[name].min() <= f <= bands[name].max()])

    # ITPC per channel per band: group trials then across-trials magnitude
    itpc_by_band = {}
    phase_by_band = {}
    for bname in ("theta", "alpha", "beta"):
        idx = band_idx(bname)
        band_phase = circ_mean(phase[:, :, idx], axis=2)  # (ep, ch)
        phase_by_band[bname] = band_phase
        itpc_by_band[bname] = np.abs(np.exp(1j * band_phase).mean(axis=0))  # (ch,)

    # Per-trial "ITPC proxy" = rolling resultant across last 5 trials (from spec PLV proxy)
    def rolling_plv(bp: np.ndarray, k: int) -> np.ndarray:
        n, ch = bp.shape
        out = np.zeros_like(bp, dtype=float)
        for i in range(n):
            s = max(0, i - k + 1)
            out[i] = np.abs(np.exp(1j * bp[s:i + 1]).mean(axis=0))
        return out

    plv_k = int(feat["plv_rolling_trials"])
    itpc_theta_trial = rolling_plv(phase_by_band["theta"], plv_k)
    itpc_alpha_trial = rolling_plv(phase_by_band["alpha"], plv_k)
    itpc_beta_trial = rolling_plv(phase_by_band["beta"], plv_k)

    frn_chs = ["Fz", "FCz"]
    p300_chs = ["Pz"]
    fmin, fmax = feat["frn_window_s"]
    pmin, pmax = feat["p300_window_s"]
    frn = _erp_peak(epochs, frn_chs, fmin, fmax, kind="neg")
    p300 = _erp_peak(epochs, p300_chs, pmin, pmax, kind="pos")

    # Behavior: align to surviving epochs via selection (events onset index ↔ epoch order)
    events_df = pd.read_csv(events_path, sep="\t")
    behav, cond_map = _behavior_block(events_df)
    sel = epochs.selection
    if sel is None or len(sel) != len(epochs):
        sel = np.arange(len(epochs))
    sel = np.asarray(sel).astype(int)
    sel = sel[sel < len(behav["correct"])]
    n_ep = len(sel)

    with h5py.File(out_path, "w") as h:
        g_eeg = h.create_group("eeg")
        g_eeg.create_dataset("itpc_theta", data=itpc_theta_trial[:n_ep], compression="gzip")
        g_eeg.create_dataset("itpc_alpha", data=itpc_alpha_trial[:n_ep], compression="gzip")
        g_eeg.create_dataset("itpc_beta", data=itpc_beta_trial[:n_ep], compression="gzip")
        g_eeg.create_dataset("phase_theta", data=phase_by_band["theta"][:n_ep], compression="gzip")
        # Group-level ITPC per channel per band (subject-level summary)
        g_eeg.create_dataset("itpc_theta_group", data=itpc_by_band["theta"])
        g_eeg.create_dataset("itpc_alpha_group", data=itpc_by_band["alpha"])
        g_eeg.create_dataset("itpc_beta_group", data=itpc_by_band["beta"])
        g_eeg.attrs["ch_names"] = np.array(epochs.ch_names, dtype="S")
        g_eeg.attrs["freqs_hz"] = np.array(freqs_all)

        g_erp = h.create_group("erp")
        g_erp.create_dataset("frn", data=frn[:n_ep])
        g_erp.create_dataset("p300", data=p300[:n_ep])

        g_bh = h.create_group("behavior")
        for k, arr in behav.items():
            g_bh.create_dataset(k, data=arr[sel[:n_ep]])
        g_bh.attrs["condition_map"] = json.dumps(cond_map)

        m = h.create_group("meta")
        m.attrs["subject_id"] = sub_id
        m.attrs["n_epochs"] = n_ep
        m.attrs["extraction_timestamp"] = utc_now_iso()
        m.attrs["contract_sha256"] = contract["_contract_sha256"]
        m.attrs["config_sha256"] = cfg["_config_sha256"]

    return {"subject_id": sub_id, "n_epochs": int(n_ep), "file": str(out_path.resolve())}


def main() -> None:
    args = parse_std_args("03b_feature_extract")
    cfg = load_config(args.config)
    contract = load_contract(cfg)
    set_global_seed(cfg["random_seed"])

    _ = require_provenance_freeze(cfg)
    _ = load_qc_summary(cfg)  # requires analyst_lock: true

    features_dir = REPO_ROOT / cfg["paths"]["features_dir"]
    features_dir.mkdir(parents=True, exist_ok=True)
    preproc_dir = REPO_ROOT / cfg["paths"]["preproc_dir"]
    qc_dir = REPO_ROOT / cfg["paths"]["qc_dir"]

    prep_agg_path = qc_dir / "preprocess_aggregate.json"
    if not prep_agg_path.exists():
        sys.exit(f"[FAIL-CLOSED] run stage 03 first; missing {prep_agg_path}")
    epo_qc = {r["subject_id"]: r for r in json.loads(prep_agg_path.read_text())}
    manifest_obj = json.loads((qc_dir / "ingestion_manifest.json").read_text())
    manifest = {e["subject_id"]: e for e in manifest_obj["subjects"]}

    extracted: list[dict] = []
    for sub_id, rep in epo_qc.items():
        if rep.get("status") != "ok" or rep.get("under_total_min"):
            continue
        epo_path = Path(rep["epo_path"])
        events_path = Path(manifest[sub_id]["events_path"])
        out_path = features_dir / f"{sub_id}_features.h5"
        if args.dry_run:
            print(f"[dry-run] would extract {sub_id}")
            continue
        try:
            r = _extract_one(sub_id, epo_path, events_path, cfg, contract, out_path)
            extracted.append(r)
        except Exception as e:
            print(f"[WARN] extraction failed for {sub_id}: {e}", file=sys.stderr)

    if args.dry_run:
        return

    manifest_hashes = [{"subject_id": r["subject_id"], "file": r["file"], "n_epochs": r["n_epochs"],
                        "sha256": sha256_file(r["file"])} for r in extracted]
    manifest_obj = {
        "run_id": cfg["run_id"],
        "contract_sha256": contract["_contract_sha256"],
        "config_sha256": cfg["_config_sha256"],
        "timestamp": utc_now_iso(),
        "n_subjects": len(manifest_hashes),
        "subjects": manifest_hashes,
    }
    manifest_path = features_dir / "FEATURE_STORE_MANIFEST.json"
    write_json(manifest_path, manifest_obj)

    append_ledger(cfg, {
        "stage": "03b_feature_extract",
        "output": {"features_dir": str(features_dir),
                   "manifest": str(manifest_path),
                   "manifest_sha256": sha256_file(manifest_path),
                   "n_subjects": len(manifest_hashes)},
        "status": "ok",
    })
    print(f"[03b_feature_extract] ok — {len(manifest_hashes)} subjects")
    print(f"  MANUAL: verify {manifest_path} and then `chmod -R a-w {features_dir}` to freeze.")


if __name__ == "__main__":
    main()
