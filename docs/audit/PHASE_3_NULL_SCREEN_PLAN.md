# Phase 3 — Null Screen Plan (research-only, pre-merge of Phase 2.1)

> Status: DRAFT — not committed to the canonical PR. Lives only on the
> Phase 2.1 work-tree until Phase 2.1 (#160) merges. Phase 3 is the
> first PR that actually asks the empirical question:
>
> > Does γ ≈ 1.0 separate the substrate signal from null/surrogate
> > controls, or is it an estimator artefact?

## 1. Question, framed as falsifiable

For each substrate `S` with γ-emitting data:

* observed: γ̂(S) on real data
* null distribution: γ̂(S; surrogate_k) for `k = 1 … M` per null family
* one-sided p_value(family) = P(|γ̂_null| ≥ |γ̂_obs − 1| + |γ̂_null − 1|)
  — i.e. permutation distance from γ = 1.

**PASS rule (substrate may move beyond `EVIDENCE_CANDIDATE`):**

* `min_family p_value < α/k` (Bonferroni; α = 0.05; k = number of families)
* AND `|γ̂_obs − γ̂_obs(window_swept)| ≤ 0.05` for every window in sweep
* AND `rerun_command` reproduces `result_hash` byte-identical
* AND `claim_status: derived` (machine, not assigned)

**FAIL rule:**

* `min_family p_value ≥ α/k`
  → ladder: `EVIDENCE_CANDIDATE_NULL_FAILED`
  → reason: `NULL_NOT_REJECTED`
  → `verdict: NULL_NOT_REJECTED` (P7 already enforces)
  → no softening of language; no removal of the failure record

## 2. Substrates in scope (initial)

| substrate | priority | data on disk? | adapter ready? | prior null result |
|---|---|---|---|---|
| `serotonergic_kuramoto` | 1 | synthetic (deterministic seed) | ✓ `substrates/serotonergic_kuramoto/adapter.py` | p=1.0 documented; needs structured re-run |
| `hrv_fantasia`          | 1 | manifest+wfdb (PhysioNet pull) | ✓ `substrates/hrv_fantasia/adapter.py` | p=0.946 documented; needs structured re-run |
| `eeg_resting`           | 2 | manifest+mne (PhysioNet pull) | ✓ `substrates/eeg_resting/adapter.py` | none yet |
| `lemma_1_kuramoto_dense`| 3 | analytical, deterministic | `experiments/lemma_1_verification/verify_kuramoto_gamma_unity.py` | not_applicable_analytical (skip) |

`zebrafish_wt`, `gray_scott`, `kuramoto`, `eeg_physionet`, `hrv_physionet`
have `data_sha256 = null` or external-only data; null screen requires
a separate data-acquisition phase first. Out of scope for Phase 3 v1.

## 3. Null families

Reuse the registered families from `core/nulls/__init__.py::FAMILIES`:

| family | preserves | breaks | applicable |
|---|---|---|---|
| `constrained_randomization` | autocorrelation lags ≤ τ_max | higher-order structure | all substrates |
| `wavelet_phase`             | wavelet amplitude spectrum  | inter-band phase coherence | EEG, HRV |
| `linear_matched`            | mean, variance, ACF (AR(p))  | nonlinear regularities | all substrates |

Plus from `core/iaaft.py`:

| family | preserves | breaks | applicable |
|---|---|---|---|
| `iaaft_surrogate` | full PSD + amplitude distribution | phase coherence beyond linear | univariate signals |
| `kuramoto_iaaft`  | per-oscillator phase distribution | inter-oscillator timing | Kuramoto-class |

For Kuramoto-class (`serotonergic_kuramoto`): use `kuramoto_iaaft` +
`linear_matched`. Two families, Bonferroni α/2 = 0.025.

For HRV (`hrv_fantasia`): use `iaaft_surrogate` (RR series is
univariate) + `constrained_randomization` + `linear_matched`.
Three families, Bonferroni α/3 ≈ 0.0167.

For EEG (`eeg_resting`): use `iaaft_surrogate` (per-channel) +
`wavelet_phase` + `linear_matched`. Three families.

## 4. Sample-size discipline

* `M ≥ 1000` surrogates per family (gates the p-value precision floor at
  `1 / (M+1)`).
* Recommended: `M = 10000` for the canonical run; `M = 1000` is the
  CI-time smoke run.
* Per-substrate seed: `seed = sha256(substrate_id || "phase_3" || M).hexdigest()[:16]` — deterministic.

## 5. Output schema (per substrate)

To go into a new `evidence/phase_3_null_screen/<substrate>.json`:

```json
{
  "substrate": "<sid>",
  "observed_gamma": <float>,
  "observed_gamma_ci95": [<lo>, <hi>],
  "n_surrogates_per_family": 10000,
  "alpha": 0.05,
  "bonferroni_alpha": <alpha / n_families>,
  "families": {
    "<family_name>": {
      "n_surrogates": 10000,
      "null_gamma_mean": <float>,
      "null_gamma_std":  <float>,
      "null_gamma_quantiles": {"q025": ..., "q500": ..., "q975": ...},
      "p_value_distance_from_one": <float>,
      "effect_size_cohen_d":      <float>,
      "verdict": "REJECTED | NOT_REJECTED"
    }
  },
  "window_sweep": {
    "windows": [...],
    "gammas": [...],
    "delta_gamma_max": <float>,
    "stable": <bool>
  },
  "rerun_command": "python -m tools.phase_3.run_null_screen --substrate <sid> --M 10000 --seed <hex>",
  "result_hash": "<sha256 of canonicalised result.json>",
  "global_verdict": "SIGNAL_SEPARATES_FROM_NULL | NULL_NOT_REJECTED | ESTIMATOR_ARTIFACT_SUSPECTED | INCONCLUSIVE",
  "ledger_update": {
    "status_proposed": "SUPPORTED_BY_NULLS | EVIDENCE_CANDIDATE_NULL_FAILED | INCONCLUSIVE",
    "downgrade_reason_proposed": "NULL_NOT_REJECTED | null"
  }
}
```

The `ledger_update` block is a **proposal only** — the actual ledger
mutation is a separate human-reviewed PR. Phase 3 never auto-promotes.

## 6. Tools to ship in Phase 3

```
tools/phase_3/
  __init__.py
  run_null_screen.py           # CLI: --substrate, --M, --seed, --families, --out
  estimator.py                  # γ from K~C^(-γ) Theil–Sen — ONE canonical impl
  family_router.py              # routes substrate → list[family_name] per §3
  effect_size.py                # Cohen's d + bootstrap CI of d
  stability.py                  # window_sweep helper
  result_hash.py                # canonicalised JSON → sha256
.github/workflows/
  phase_3_null_screen.yml       # smoke run with M=200 on PR; M=10000 on main
tests/
  test_phase_3_null_screen.py   # adversarial tests (see §7)
docs/audit/
  PHASE_3_PROTOCOL.md           # frozen prose protocol
```

## 7. Adversarial tests (must ship with Phase 3)

1. Synthetic IAAFT-of-pure-Gaussian-noise → `verdict: NULL_NOT_REJECTED`.
   (If we accept random noise as signal, the gate is broken.)
2. Synthetic γ = 1.0 generator with structured power-law data → `verdict:
   SIGNAL_SEPARATES_FROM_NULL`. (Positive control.)
3. Substrate adapter returning constant series → `verdict: INCONCLUSIVE`
   or `ESTIMATOR_ARTIFACT_SUSPECTED`. (Degenerate input must not pass.)
4. Surrogate generator returning the original data unchanged → must be
   detected and FAIL the run (sanity check on the null itself).
5. `M < 1000` → run refuses to start (precision floor too high).
6. Result-hash drift between two reruns with the same seed → FAIL.
7. Window-sweep with `Δγ_max > 0.05` → `ESTIMATOR_ARTIFACT_SUSPECTED`.
8. Forging ledger update without `result_hash` → schema rejects (already
   covered by Phase 2.1 binding gate).

## 8. CI gating

* PR-time job runs `M = 200` smoke on each in-scope substrate (≈ 2 min).
* `merge_group` and `push: main` runs `M = 10000` canonical screen
  (≈ 30 min on a single core; can parallelise per-substrate).
* CI fails closed if:
  * any `--families` requested family is not in the registry;
  * any `result_hash` drifts from the stored canonical run;
  * any substrate's `ledger_update.status_proposed` would advance the
    ladder past `SUPPORTED_BY_NULLS` (which is the most this PR can
    legitimately propose; `VALIDATED` remains frozen by Phase 2.1 P6).

## 9. Honest expected outcome

Both currently-tested substrates (`serotonergic_kuramoto`,
`hrv_fantasia`) **already documented null failure** in Phase 2.1. The
expected Phase 3 v1 outcome is:

* `serotonergic_kuramoto`: `NULL_NOT_REJECTED` confirmed at `M = 10000`
  with structured per-family p-values. **No promotion.**
* `hrv_fantasia`: same.
* `eeg_resting`: unknown — first principled null screen for this
  substrate.

If all three return `NULL_NOT_REJECTED`, the canonical answer for the
γ ≈ 1.0 universality claim is **the hypothesis is not falsifiable in its
current form on these substrates** — and Phase 4 must rewrite the
hypothesis or change the estimator.

## 10. What Phase 3 explicitly does NOT do

* Does **not** change `CANON_VALIDATED_FROZEN`.
* Does **not** add raw-file Merkle (`size_bytes`); that is Phase 8 / a
  separate PR.
* Does **not** build the out-of-process attestor (A5 strict); pure-Python
  language guarantees still hold.
* Does **not** soften the existing two failed null screens.
* Does **not** promote any substrate above `SUPPORTED_BY_NULLS`.

`claim_status: derived` — Phase 3 derives a structured null-screen
result per substrate from the existing infrastructure; it does not
make any new positive measurement claim.
