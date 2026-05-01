# neurophase · Run 1 Research Execution Protocol (NP-RUN1-v1.0)

**Dataset:** OpenNeuro `ds003474` v1.0.1 (Cavanagh et al., probabilistic selection task, 122 subjects, 64-ch ActiCHamp, 500 Hz).
**Mode:** FAIL-CLOSED. Null result is a valid output.
**Integration ceiling:** existence-only → witness; existence+utility(held-out) → candidate adapter; independent replication → integration-ready.

This document is the **authoritative preregistered analysis plan**. Any deviation must be logged in `neurophase/LEDGER.yaml` with rationale. Deviations do not invalidate results but must be disclosed in the verdict.

## QC-first ordering (non-negotiable)

Execution MUST start with BIDS ingestion and QC provenance freeze. Feature extraction and analysis stages are **blocked by hard gates** and will refuse to run without:

1. `neurophase/qc/PROVENANCE_FREEZE.yaml` (written by Stage 01, contains contract SHA-256)
2. `neurophase/qc/QC_SUMMARY.yaml` with `analyst_lock: true` (set manually after review)
3. `neurophase/features/FEATURE_STORE_MANIFEST.json` + read-only feature files (`chmod -R a-w`)

### Known ds003474 risks addressed by provenance capture

| Risk | Capture | Stage |
|---|---|---|
| Mislabeled / swapped EOG channels | `channel_provenance.json` flags `mislabeled_eog`, `suspicious_eog` from channels.tsv `type` vs name heuristics | 01 |
| Pre-existing upstream interpolations | `interpolated_channels_upstream` from `status_description` tokens | 01 |
| Upstream-bad channels (dataset maintainer flags) | `bad_channels_upstream` — unioned into 02's bad list | 01 → 02 |
| Unstable subjects (non-learners / ceiling) | Behavioral QC: AB last-50 accuracy bounds [0.55, 0.95] | 03 |
| Missing mandatory event columns | Hard ingestion exclusion | 01 |

## Hypotheses (contract)

- **H1 (existence):** Pre-response θ-phase (–200..0 ms, FCz cluster) carries information about next-trial adaptation (WSLS target) beyond behavioral baseline.
- **H2 (utility):** That neural signal improves LOSO out-of-sample AUC versus behavior-only.

**Confirm thresholds** (from `contracts/neurophase_run1.yaml`):
- H1: sign-consistency ≥ 0.60 AND group t p < 0.05 (permutation, FDR-BH q=0.05)
- H2: mean ΔAUC > 0 AND t p < 0.05 AND Cohen's d > 0.2

**Reject thresholds:**
- H1: sign-consistency ≤ 0.50 OR group t p > 0.20
- H2: mean ΔAUC ≤ 0 OR t p > 0.10

In between: INCONCLUSIVE (defer to Run 2 on ds004295).

## Ladder

| Stage | Script | Gate required before this stage | Artifact |
|---|---|---|---|
| 01 | `scripts/neurophase/01_ingest_bids.py` | BIDS root present | `qc/PROVENANCE_FREEZE.yaml` |
| 02 | `scripts/neurophase/02_channel_qc.py` | provenance freeze | `qc/channel_qc_aggregate.json` |
| 03 | `scripts/neurophase/03_preprocess.py` | provenance freeze | `qc/QC_SUMMARY.yaml` (`analyst_lock: false`) |
| **M1** | *MANUAL REVIEW* | set `analyst_lock: true` | — |
| 03b | `scripts/neurophase/03b_feature_extract.py` | provenance freeze + analyst_lock | `features/FEATURE_STORE_MANIFEST.json` |
| **M2** | *MANUAL REVIEW* | `chmod -R a-w features/` | — |
| 04 | `scripts/neurophase/04_existence_test.py` | provenance freeze + analyst_lock + frozen features | `results/existence_report.json` |
| 05 | `scripts/neurophase/05_utility_test.py` | same as 04 | `results/utility_report.json` |
| 06 | `scripts/neurophase/06_robustness.py` | same as 04 | `results/robustness_report.json` |
| **M3** | *MANUAL REVIEW* | complete `results/RUN1_VERDICT.yaml`, set `verdict_locked: true` | — |

## Integration ceiling enforcement (automated)

The verdict file is built by manual review against `contracts/neurophase_run1.yaml` `integration_ceiling:` block. See contract for the branching logic.

## Reproducibility

- `RANDOM_SEED = 42` is set at every stage entry (see `config/neurophase_run1.yaml` → `_common.set_global_seed`).
- All stochastic steps (ICA, permutations, bootstrap CIs) use seeded generators.
- Every stage appends to `neurophase/LEDGER.yaml` with input/output SHA-256 hashes.
- Contract + config SHA-256 are stored in the provenance freeze — any drift across stages hard-halts.

## Failure modes

See `contracts/neurophase_run1.yaml` failure_modes section; mirrored in `docs/neurophase/RUN1_EXECUTION.md` runbook.
