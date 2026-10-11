# Canonical cardiac γ-program extraction stack

Single source of truth for the HRV feature-extraction pipeline.
Every downstream claim in the γ-program travels through this stack;
ad-hoc RR extraction, one-off spectral fits, and rogue DFA
implementations are protocol violations.

The live reference lives at `tools/hrv/canonical_stack.py`. This
document mirrors the pipeline prose-style so reviewers have a
non-code artifact.

## Pipeline

| step | artefact | module |
|---|---|---|
| 1 | wfdb annotation → NN-interval series | `tools.data.physionet_cohort.fetch_record` |
| 2 | 4 Hz uniform-grid resample (linear interp) | `tools.hrv.baseline_panel._resample_rr_to_uniform` |
| 3 | spectral features (Welch PSD, VLF/LF/HF/TP) | `tools.hrv.baseline_panel._power_bands` |
| 4 | DFA α₁ / α₂ (Peng 1995) | `tools.hrv.baseline_panel.dfa_alpha` |
| 5 | sample entropy (Richman & Moorman 2000) | `tools.hrv.baseline_panel.sample_entropy` |
| 6 | Poincaré SD1 / SD2 (Brennan 2001) | `tools.hrv.baseline_panel._sd1_sd2_ms` |
| 7 | five-layer null suite | `tools.hrv.null_suite.compute_null_suite` |
| 8 | blind external validation | `tools.hrv.blind_validation.validation_report` |

## Frozen parameters

| parameter | value | constant |
|---|---|---|
| RR clip range (s) | [0.3, 2.0] | `RR_CLIP_RANGE_S` |
| Resample rate (Hz) | 4.0 | `FS_RESAMPLE_HZ` |
| Welch nperseg (s) | 256.0 | `WELCH_NPERSEG_S` |
| Welch overlap | 0.5 | `WELCH_OVERLAP` |
| DFA short scales (beats) | (4, 16) | `DFA_SCALES_SHORT` |
| DFA long scales (beats) | (16, 64) | `DFA_SCALES_LONG` |
| SampEn m | 2 | `SAMPEN_M` |
| SampEn r fraction of σ | 0.2 | `SAMPEN_R_FRAC` |
| SampEn N cap | 5000 | `SAMPEN_MAX_N` |
| Null-suite surrogates per layer | 200 | `NULL_SURROGATES_PER_LAYER` |
| Null-suite beat cap | 10 000 | `NULL_BEATS_CAP` |

## Change discipline

Every constant in the table above is review-gated. Changing any of
them requires rotating `CANONICAL_STACK_VERSION` (currently `1.0.0`)
in the same PR and writing a rationale in the PR body. The test
`tests/test_canonical_stack.py::test_canonical_params_have_not_drifted`
enforces this at CI time.

## Relationship to other extractors

- **`substrates/hrv_physionet/adapter.py`**, **`substrates/hrv_fantasia/adapter.py`**
  predate this stack and ship their own private DFA and γ-fit code.
  They remain wired to the existing `evidence/gamma_ledger.json` for
  historical claims (`substrate_id = hrv_physionet` / `hrv_fantasia`).
  A follow-up PR may migrate these adapters to consume the canonical
  stack; this is an internal refactor and must preserve the existing
  γ-ledger entries byte-for-byte.
- **`substrates/physionet_hrv/`** (merged via #101) is a pilot adapter
  for the NSR cohort γ-fit. Its `fetch_rr_intervals` is functionally
  equivalent to `tools.data.physionet_cohort.fetch_record`. A
  consolidation PR will replace the local function with a re-export
  once Task 5 (evidence-branch split) has landed.
