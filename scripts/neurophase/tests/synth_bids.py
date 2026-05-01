#!/usr/bin/env python3
"""Synthetic BIDS dataset generator — ds003474 mimic for pipeline self-test.

Generates a tiny (N subjects, configurable) BIDS EEG dataset with:
  - Compliant dataset_description.json / participants.tsv / task-pst_eeg.json
  - Per subject: sub-{N}/eeg/*_task-pst_eeg.set+.fdt, *_events.tsv, *_channels.tsv
  - Planted incremental θ-phase → next-trial-correct coupling for "positive"
    subjects (a specifiable subset); pure-noise for negative controls.

The planted coupling is designed to be INCREMENTAL over a behavioral baseline:
the neural signal adds information that shuffling breaks, even when running
accuracy is controlled for.

Usage:
  python3 scripts/neurophase/tests/synth_bids.py --out_dir /tmp/synth_ds --n_subjects 4
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

try:
    import mne
    mne.set_log_level("ERROR")
except ImportError:
    raise SystemExit("mne required: pip install mne")


# Standard 10-20 64ch subset — names MNE recognizes
CH_NAMES = [
    "Fp1", "Fp2", "AF3", "AF4", "F7", "F5", "F3", "F1", "Fz", "F2", "F4", "F6", "F8",
    "FT7", "FC5", "FC3", "FC1", "FCz", "FC2", "FC4", "FC6", "FT8",
    "T7", "C5", "C3", "C1", "Cz", "C2", "C4", "C6", "T8",
    "TP7", "CP5", "CP3", "CP1", "CPz", "CP2", "CP4", "CP6", "TP8",
    "P7", "P5", "P3", "P1", "Pz", "P2", "P4", "P6", "P8",
    "PO7", "PO3", "POz", "PO4", "PO8", "O1", "Oz", "O2",
    "AF7", "AF8", "F9", "F10", "FT9", "FT10", "TP9", "TP10",
]  # 64 channels


def _write_root_files(root: Path, n_subjects: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "dataset_description.json").write_text(json.dumps({
        "Name": "synth_ds003474_mimic",
        "BIDSVersion": "1.6.0",
        "DatasetType": "raw",
        "License": "CC0",
        "Authors": ["synthetic harness"],
    }, indent=2))
    (root / "task-pst_eeg.json").write_text(json.dumps({
        "TaskName": "pst",
        "SamplingFrequency": 500,
        "EEGReference": "Cz",
        "PowerLineFrequency": 50,
        "SoftwareFilters": "n/a",
        "EEGChannelCount": 64,
    }, indent=2))
    with (root / "participants.tsv").open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["participant_id", "age", "sex"])
        for i in range(1, n_subjects + 1):
            w.writerow([f"sub-{i:03d}", 25 + (i % 10), "M" if i % 2 else "F"])


def _gen_events(rng: np.random.Generator, n_trials: int, sfreq: float) -> list[dict]:
    """Generate events.tsv rows. Trials spaced ~3s apart."""
    rows = []
    t = 5.0
    for i in range(n_trials):
        rt = float(rng.uniform(0.35, 1.6))
        # Induce learning: AB accuracy rises from 0.4 → 0.85 over session
        progress = i / max(1, n_trials - 1)
        baseline_acc = 0.4 + 0.45 * progress
        # trial_type alternates AB, CD, EF
        tt = ["AB", "CD", "EF"][i % 3]
        correct = int(rng.uniform() < baseline_acc)
        feedback = "gain" if correct else "loss"
        rows.append({
            "onset": round(t, 3),
            "duration": round(rt, 3),
            "trial_type": tt,
            "response_time": round(rt, 3),
            "correct": correct,
            "feedback": feedback,
            "block": (i // 60) + 1,
        })
        t += rt + rng.uniform(2.5, 3.5)
    return rows


def _inject_incremental_coupling(events: list[dict], rng: np.random.Generator,
                                  strength: float) -> np.ndarray:
    """Return per-trial θ-phase angle that is predictive of NEXT-trial correct
    *beyond* the running-accuracy trend baked into events. strength ∈ [0, 1]."""
    n = len(events)
    correct_next = np.array([events[i + 1]["correct"] if i + 1 < n else 0 for i in range(n)])
    # Baseline phase: uniform random on [-π, π]
    phase = rng.uniform(-np.pi, np.pi, size=n)
    # Add a preferred phase for trials whose NEXT-trial is correct
    target_phase = 0.3  # rad
    kappa = 4.0 * strength  # concentration parameter proxy
    for i in range(n):
        if correct_next[i] == 1:
            # Pull phase toward target with strength kappa (von-Mises-ish approximation)
            noise = rng.normal(0, 1.0 / (kappa + 0.1))
            phase[i] = np.mod(target_phase + noise + np.pi, 2 * np.pi) - np.pi
    return phase


def _build_raw(rng: np.random.Generator, events: list[dict], sfreq: float,
               planted_phase: np.ndarray | None) -> mne.io.RawArray:
    total_dur = events[-1]["onset"] + events[-1]["duration"] + 5.0
    n_samples = int(total_dur * sfreq)
    n_ch = len(CH_NAMES)
    data = rng.normal(0, 15e-6, size=(n_ch, n_samples))  # 15 μV noise

    if planted_phase is not None:
        # Inject a 6 Hz oscillation in [-200, 0] ms window pre-response at FCz/Fz/Cz
        theta_freq = 6.0
        theta_amp = 8e-6
        window_samp = int(0.2 * sfreq)
        fcz_idx = CH_NAMES.index("FCz")
        fz_idx = CH_NAMES.index("Fz")
        cz_idx = CH_NAMES.index("Cz")
        for i, ev in enumerate(events):
            resp_time = ev["onset"] + ev["response_time"]
            end = int(resp_time * sfreq)
            start = end - window_samp
            if start < 0:
                continue
            t = np.arange(window_samp) / sfreq
            wave = theta_amp * np.sin(2 * np.pi * theta_freq * t + planted_phase[i])
            data[fcz_idx, start:end] += wave
            data[fz_idx, start:end] += wave * 0.8
            data[cz_idx, start:end] += wave * 0.7

    info = mne.create_info(ch_names=list(CH_NAMES), sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose="ERROR")
    try:
        raw.set_montage("standard_1020", on_missing="warn", match_case=False, verbose="ERROR")
    except Exception:
        pass
    return raw


def _write_channels_tsv(path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["name", "type", "units", "sampling_frequency", "status", "status_description"])
        for ch in CH_NAMES:
            w.writerow([ch, "EEG", "V", 500, "good", "n/a"])


def _write_events_tsv(path: Path, rows: list[dict]) -> None:
    fields = ["onset", "duration", "trial_type", "response_time", "correct", "feedback", "block"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def generate(out_dir: Path, n_subjects: int, positive_fraction: float, seed: int, n_trials: int) -> None:
    root = out_dir
    _write_root_files(root, n_subjects)
    sfreq = 500.0
    for i in range(1, n_subjects + 1):
        sub_id = f"sub-{i:03d}"
        rng = np.random.default_rng(seed + i)
        events = _gen_events(rng, n_trials, sfreq)
        is_positive = (i - 1) < int(round(n_subjects * positive_fraction))
        strength = 0.8 if is_positive else 0.0
        planted = _inject_incremental_coupling(events, rng, strength) if is_positive else None
        raw = _build_raw(rng, events, sfreq, planted)

        eeg_dir = root / sub_id / "eeg"
        eeg_dir.mkdir(parents=True, exist_ok=True)
        set_path = eeg_dir / f"{sub_id}_task-pst_eeg.set"
        raw.export(str(set_path), fmt="eeglab", overwrite=True, verbose="ERROR")
        _write_events_tsv(eeg_dir / f"{sub_id}_task-pst_events.tsv", events)
        _write_channels_tsv(eeg_dir / f"{sub_id}_task-pst_channels.tsv")

        print(f"  {sub_id}: {'POSITIVE' if is_positive else 'NEGATIVE'} | "
              f"{len(events)} trials | {raw.n_times} samples | strength={strength}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True, type=Path)
    ap.add_argument("--n_subjects", type=int, default=4)
    ap.add_argument("--positive_fraction", type=float, default=0.75)
    ap.add_argument("--n_trials", type=int, default=240)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    print(f"[synth_bids] generating {args.n_subjects} subjects at {args.out_dir} "
          f"(positive_fraction={args.positive_fraction}, n_trials={args.n_trials})")
    generate(args.out_dir, args.n_subjects, args.positive_fraction, args.seed, args.n_trials)
    print("[synth_bids] done.")


if __name__ == "__main__":
    main()
