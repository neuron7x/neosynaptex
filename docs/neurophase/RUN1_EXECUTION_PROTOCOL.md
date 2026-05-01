# NEUROPHASE RUN 1 — EXECUTION PROTOCOL (ds003474)

**STATUS:** PREREGISTERED · FAIL-CLOSED · AUDIT-GRADE
**Document ID:** NP-RUN1-EXEC-v1.0 (canonical, immutable)
**Supersedes:** prose sections of `RUN1_PROTOCOL.md`, `RUN1_EXECUTION.md`
**Binding:** This document is the authoritative execution contract for Run 1.
No changes to code, thresholds, or feature definitions are permitted after
this protocol is frozen in LEDGER.yaml under stage `protocol_frozen`.

---

## 0. META (IMMUTABLE)

Strictly test H1/H2:

* **H1 (existence):** pre-response θ-phase → WSLS
* **H2 (utility):** θ-phase adds predictive value (ΔAUC > 0, LOSO)

No interpretation.
Only: **CONFIRMED / REJECTED / INCONCLUSIVE**

---

## 1. GLOBAL INVARIANTS

1. Pipeline **deterministic** (seed=42)
2. **Fail-closed** at every stage
3. **No code changes after start**
4. `config/neurophase_run1.yaml` — **immutability anchor**
5. All artifacts → SHA-256 → `neurophase/LEDGER.yaml`
6. `neurophase/features/` → **write-once + read-only**
7. **No manual overrides without ledger entry**
8. Null result = valid result

---

## 2. EXECUTION STACK

```
01_ingest_bids              scripts/neurophase/01_ingest_bids.py
02_qc                       scripts/neurophase/02_qc.py
gate_m1_qc_lock             scripts/neurophase/gate_m1_qc_lock.py
03_preprocess               scripts/neurophase/03_preprocess.py
03b_feature_extract         scripts/neurophase/03b_feature_extract.py
gate_m2_freeze_features     scripts/neurophase/gate_m2_freeze_features.py
04_existence_test           scripts/neurophase/04_existence_test.py
05_utility_test             scripts/neurophase/05_utility_test.py
06_robustness               scripts/neurophase/06_robustness.py
07_write_verdict            scripts/neurophase/07_write_verdict.py
gate_m3_verdict_lock        scripts/neurophase/gate_m3_verdict_lock.py
```

---

## 3. STAGE 01 — INGESTION

**Input:** BIDS ds003474 (v1.0.1)
**Output:** `neurophase/qc/ingestion_manifest.json` (chmod a-w), `PROVENANCE_FREEZE.yaml`

### Contract

* Root validation (dataset_description, participants.tsv, task-pst_eeg.json)
* Expected: **122 subjects**
* Per subject: `.set / .fdt / events.tsv / channels.tsv`, SHA-256, size sanity, EOG rules (R01–R03), interpolation rules (R01–R02)

### FAIL

* `|n_dirs − n_participants| > 2` → HALT
* Missing mandatory events columns → subject excluded
* Any missing of (.set, events, channels) → subject excluded

---

## 4. STAGE 02 — QC

**Input:** ingestion_manifest.json
**Output:** `QC_SUMMARY.yaml`, per-subject JSON, `qc_aggregate.json`

### Channel QC

* flat < 0.5 μV → bad
* noisy |z| > 3.5 → bad
* bad_fraction > 0.15 → EXCLUDE

### Behavioral QC

* missing_response > 0.20 → EXCLUDE
* AB accuracy last 50 ∉ [0.55, 0.95] → EXCLUDE

### Epoch viability (preview, no preprocessing yet)

* surviving total < 100 → EXCLUDE
* per condition < 20 → EXCLUDE

### Audit rules (deterministic, no heuristic branching)

* EOG mislabeling (R01–R03)
* interpolation detection (R01–R02)

### FAIL

* > 30% excluded → HALT

---

## 5. GATE M1 — QC LOCK

Programmatic assertion contract, ≥ 7 checks:

1. QC_SUMMARY.yaml present
2. EXCLUDED_SUBJECTS.yaml present
3. PROVENANCE_FREEZE.yaml present + `provenance_lock: true`
4. contract SHA matches across summary + freeze
5. analyst_lock currently False (not already set)
6. LEDGER has `01_ingest_bids` + `02_qc` with `status: ok`
7. exclusion fraction ≤ 0.30
8. at least 1 subject candidate for preprocessing

→ `CONFIRM` (stdin) or `--auto_confirm --operator=<id>`

---

## 6. STAGE 03 — PREPROCESS

Immutable chain (deviation = pipeline invalidation):

1. Load EEGLAB .set
2. Apply standard_1020 montage
3. Annotate bad channels from Stage 02
4. Bandpass 0.1–40 Hz (FIR, hamming)
5. Notch 50 Hz + 100 Hz
6. Interpolate bad channels (spherical spline)
7. Average reference
8. ICA fit on 1–40 Hz copy (FastICA, 20 components, seed=42)
9. Ocular detect (EOG corr > 0.8, Fp1/Fp2 proxy)
10. Remove ≤ 3 ocular components
11. Epoch [-0.5, 1.0] s response-locked
12. Baseline correction [-0.2, 0] s
13. Reject (PTP > 150 μV, EOG proxy > 100 μV, muscle HF)
14. Save epo.fif + ica.fif (audit trail)

Resume: existing epo.fif + ica.fif per subject → skipped without reprocessing.

### FAIL

* `analyst_lock: false` → HALT
* surviving epochs < 100 → EXCLUDE subject
* > 20% subjects failed → HALT

---

## 7. STAGE 03b — FEATURE STORE

**Output:** `neurophase/features/sub-{N}_features.h5` + `FEATURE_STORE_MANIFEST.json`

### A — Phase

* ITPC θ/α/β per channel (band circular mean across wavelet freqs)
* single-trial phase (θ at FCz cluster)
* rolling PLV (5-trial window) per channel

### B — ERP

* FRN peak amplitude (200–350 ms, Fz/FCz, negative peak)
* P300 peak amplitude (300–600 ms, Pz, positive peak)

### C — Behavior

* running_acc (5-trial rolling), prev_correct, RT, trial_num, condition (int-encoded)

### Invariants

* order preserved (epoch order = behavior alignment order)
* SHA-256 per file recorded in manifest
* `chmod a-w` applied at Gate M2

---

## 8. GATE M2 — FEATURE FREEZE

Programmatic assertion contract, ≥ 8 checks:

1. features_dir exists
2. FEATURE_STORE_MANIFEST.json exists
3. no untracked `*_features.h5`
4. no manifest entries missing on disk
5. per-subject: SHA-256 on disk matches manifest (N checks, one per subject)

→ `CONFIRM` or `--auto_confirm`
→ `freeze_file(path)` on all `.h5` + manifest

---

## 9. STAGE 04 — H1 (EXISTENCE)

Per-subject model:

```
y = WSLS (next trial correct, binary)
X = [ITPC_theta_cluster(FCz,Fz,Cz), running_acc, prev_correct, RT, trial_num, condition]
```

* Logistic regression (statsmodels.Logit, no regularization — returns β + SE)
* β₁ = coefficient on ITPC_theta_cluster

### Null

* 1000 permutations, shuffle ITPC_theta **within condition blocks** (preserves autocorr)
* Subject p = fraction(|perm β| ≥ |observed β|), one-tailed signed
* Validity guard: ≥ 75% of 1000 refits must succeed; distribution std ≥ 1e-6

### Group

* FDR-BH via `scipy.stats.false_discovery_control`
* One-sample t on Fisher-z(clip(β, -0.999, 0.999)), Bonferroni α=0.017
* Cohen's d + BCa bootstrap CI n=10000 via `scipy.stats.bootstrap`
* sign_consistency = fraction(β > 0)
* MDE guard: if would-reject and |d| < 0.28 → `INCONCLUSIVE_UNDERPOWERED`

### Verdict

```
CONFIRMED                   if sign ≥ 0.60 and group_p < 0.05
REJECTED                    if (sign ≤ 0.50 or group_p > 0.20) and |d| ≥ 0.28
INCONCLUSIVE_UNDERPOWERED   if (sign ≤ 0.50 or group_p > 0.20) and |d| < 0.28
INCONCLUSIVE                otherwise
```

---

## 10. STAGE 05 — H2 (UTILITY)

LOSO cross-validation:

* Model B:  `[running_acc, prev_correct, RT, trial_num, condition]`
* Model NB: `[ITPC_theta_cluster, FRN, P300] + B`
* Metric: ROC-AUC per held-out subject
* ΔAUC = AUC(NB) − AUC(B)

One-sample t on {ΔAUC_s} vs 0, Cohen's d, BCa bootstrap CI n=10000.

### Decision table

```
CONFIRMED        if Δ > 0 and p < 0.05 and d ≥ 0.20
CONFIRMED_WEAK   if Δ > 0 and p < 0.05 and d < 0.20
INCONCLUSIVE     if Δ > 0 and 0.05 ≤ p < 0.10
REJECTED         if Δ > 0 and p ≥ 0.10
REJECTED         if Δ ≤ 0
```

---

## 11. STAGE 06 — ROBUSTNESS

### Artifact flag

```
fraction_channels_positive > 0.90 in ALL of {θ, α, β} → HALT
```

Writes HALT to LEDGER; verdict cannot proceed until preprocessing/ICA re-review.

### Topographic specificity

```
(mean_β₁_FC − mean_β₁_Oc) / SD_across_channels > 0.5
```

FC = {Fz, FCz, Cz}; Oc = {O1, Oz, O2}.
Failure → H1 downgraded to INCONCLUSIVE by Stage 07.

### Full channel sweep

Per (band, channel): β₁ via per-channel logit. Written to `robustness_report.json`.

---

## 12. STAGE 07 — VERDICT

Ceiling rule table (applied deterministically):

```
artifact_flag=True                                  → INVALID
H1=REJECTED                                         → EEG_TRACK_CLOSED
H1=INCONCLUSIVE_UNDERPOWERED                        → UNDERPOWERED_NULL
H1=CONFIRMED and specificity_ok=False               → UNRESOLVED  (H1 downgraded)
H1=CONFIRMED and H2 ∈ {CONFIRMED, CONFIRMED_WEAK}   → CANDIDATE_ADAPTER
H1=CONFIRMED and H2=REJECTED                        → WITNESS_ONLY
H1=CONFIRMED and H2=INCONCLUSIVE                    → WITNESS_PENDING
H1=INCONCLUSIVE                                     → UNRESOLVED
```

---

## 13. GATE M3 — VERDICT LOCK

Programmatic assertion contract, ≥ 14 checks:

1. RUN1_VERDICT.yaml exists
2. verdict_locked currently False
3. H1 result is recognized label
4. H2 result is recognized label
5. integration_ceiling.current_status is recognized label
6–11. existence/utility/robustness reports: present on disk AND SHA-256 stable since write_verdict (2 checks each × 3 reports = 6)
12–15. LEDGER has 04/05/06/07 each with status=ok (4 checks)
16. artifact_flag is not True OR ceiling is INVALID

→ `CONFIRM` or `--auto_confirm`
→ set `verdict_locked: true`, freeze RUN1_VERDICT.yaml (chmod a-w)

---

## 14. CRITICAL PROHIBITIONS

* ❌ change thresholds
* ❌ change feature definitions
* ❌ change statistical model
* ❌ inspect intermediate result and "tune"
* ❌ manual exclusion without ledger entry

---

## 15. SOLE SUCCESS METRIC

Not "find signal".

But:

> **pipeline issues the correct verdict independent of outcome**

---

## 16. FINAL ORDER

```
RUN SYSTEM
RECORD EVERYTHING
CHANGE NOTHING
ACCEPT VERDICT
```

---

**Level:** reproducible falsification experiment, suitable for peer review.
