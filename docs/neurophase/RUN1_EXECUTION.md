# Run 1 Execution Runbook

Complementary to `RUN1_PROTOCOL.md`. This is the operator's checklist.

## 0. Environment check

```bash
python3 -c "import mne, h5py, sklearn, statsmodels, numpy, scipy, pandas, yaml; print('ok')"
```

Required packages (minimum): mne ≥ 1.10, h5py ≥ 3, sklearn ≥ 1.3, statsmodels ≥ 0.14, scipy ≥ 1.11 (for `false_discovery_control` + BCa bootstrap).

Currently validated on this host:
- mne 1.11.0, h5py 3.16.0, sklearn 1.8.0, statsmodels 0.14.6, scipy ≥ 1.17 — OK.
- `eeglabio` installed (used by the synthetic BIDS generator for self-test).

Optional: `mne-bids`, `openneuro-py` (dataset download helper).

## 1. Acquire ds003474

The pipeline expects the dataset at `data/ds003474/` (relative to repo root) unless overridden with `--bids_root <path>`.

- `openneuro-py`: `pip install openneuro-py && python -c "import openneuro; openneuro.download(dataset='ds003474', target_dir='data/ds003474', tag='1.0.1')"`
- `datalad`: `datalad install https://github.com/OpenNeuroDatasets/ds003474.git data/ds003474 && (cd data/ds003474 && datalad get .)`
- Direct: https://openneuro.org/datasets/ds003474/versions/1.0.1

Expected on-disk: ~50–80 GB. Keep ≥ 150 GB free for preprocessing byproducts.

## 2. Run the ladder (fully formalized — no manual file edits)

All three previously-manual gates are now `scripts/neurophase/gate_m{1,2,3}_*.py` — assertion-contract CLIs that require the operator to type `CONFIRM` on stdin (or `--auto_confirm` for CI).

```bash
# Stage 01 — ingestion + PROVENANCE FREEZE
python3 scripts/neurophase/01_ingest_bids.py

# Stage 02 — unified QC (channel + behavioral + epoch-preview)
python3 scripts/neurophase/02_qc.py

# Gate M1 — QC lock (programmatic)
#   Runs assertion contract. If any assertion fails, the CONFIRM prompt
#   is suppressed. On pass, operator types 'CONFIRM' to set analyst_lock=true.
python3 scripts/neurophase/gate_m1_qc_lock.py
# Or for CI: python3 scripts/neurophase/gate_m1_qc_lock.py --auto_confirm --operator=ci-bot

# Stage 03 — preprocessing (response-locked epochs, ICA)
#   Resumes completed subjects automatically (looks for epo.fif + ica.fif).
python3 scripts/neurophase/03_preprocess.py

# Stage 03b — feature extraction → HDF5 store
python3 scripts/neurophase/03b_feature_extract.py

# Gate M2 — feature store freeze (programmatic)
#   Verifies every manifest hash against disk; refuses to freeze on mismatch.
python3 scripts/neurophase/gate_m2_freeze_features.py

# Stage 04 — H1 existence test (incremental predictive value)
python3 scripts/neurophase/04_existence_test.py

# Stage 05 — H2 utility (LOSO ΔAUC)
python3 scripts/neurophase/05_utility_test.py

# Stage 06 — Robustness (full topography + artifact/specificity criteria)
python3 scripts/neurophase/06_robustness.py

# Stage 07 — Verdict synthesizer (populates RUN1_VERDICT.yaml results)
python3 scripts/neurophase/07_write_verdict.py

# Gate M3 — verdict lock (programmatic)
#   Verifies report hashes, LEDGER coverage, and ceiling assignment.
python3 scripts/neurophase/gate_m3_verdict_lock.py
```

## 3. Self-test on synthetic data (no ds003474 required)

A synthetic BIDS generator produces a tiny ds003474 mimic with PLANTED
incremental θ-phase → WSLS coupling (positive-control subjects) and
pure-noise subjects (negative control). This lets us verify the pipeline
recovers a known signal and fails cleanly on noise — the gold standard
for a falsification harness.

```bash
python3 scripts/neurophase/tests/synth_bids.py --out_dir /tmp/synth_ds --n_subjects 4 --n_trials 240
python3 scripts/neurophase/01_ingest_bids.py --bids_root /tmp/synth_ds
python3 scripts/neurophase/02_qc.py
python3 scripts/neurophase/gate_m1_qc_lock.py --auto_confirm --operator=selftest
python3 scripts/neurophase/03_preprocess.py
python3 scripts/neurophase/03b_feature_extract.py
python3 scripts/neurophase/gate_m2_freeze_features.py --auto_confirm --operator=selftest
python3 scripts/neurophase/04_existence_test.py
python3 scripts/neurophase/05_utility_test.py
python3 scripts/neurophase/06_robustness.py
python3 scripts/neurophase/07_write_verdict.py
python3 scripts/neurophase/gate_m3_verdict_lock.py --auto_confirm --operator=selftest
```

## 4. Dry runs

Most stages accept `--dry_run` which validates preconditions and prints
what WOULD be written without modifying state.

## 5. Ledger inspection

```bash
cat neurophase/LEDGER.yaml
```

Every stage + gate appends one entry with input/output SHA-256 hashes and
(for gates) the operator identifier and confirmation mode (CONFIRM /
AUTO_CONFIRM). Any stage failure halts the pipeline; inspect the last
entry for diagnostics.

## 6. Resuming after a halt

- Stage 03 resumes by detecting pre-existing epo.fif + ica.fif per subject.
- Other stages are idempotent at the run level; they overwrite their own
  outputs. To restart a pipeline from scratch, delete `neurophase/qc/`,
  `neurophase/preproc/`, `neurophase/features/`, and re-run Stage 01.
- Do NOT paper over failures by editing outputs. Restart with a new
  `run_id` in `config/neurophase_run1.yaml` instead.
