# Phase 3 — Null Screen Protocol (frozen)

> Status: canonical protocol shipped with the Phase 3 PR.
> Version: 3.0.0 (corresponds to `tools.phase_3.PHASE_3_VERSION`).
> Source plan: `docs/audit/PHASE_3_NULL_SCREEN_PLAN.md`.
> Smoke result that motivated this protocol: `docs/audit/PHASE_3_SMOKE_RESULT.md`.

## 0. Verdict ceiling (absolute, frozen)

**Phase 3 cannot promote any substrate above `SUPPORTED_BY_NULLS`.
`VALIDATED` remains frozen** — the freeze lives in
`evidence/ledger_schema.py::CANON_VALIDATED_FROZEN` and is not
toggleable from any Phase 3 code path. Every `ledger_update` block in
a Phase 3 output JSON is a **proposal only** (`status_proposed`,
`downgrade_reason_proposed`); the actual ledger mutation requires a
separate human-reviewed PR.

This is a structural rule, not a stylistic one. Removing it from this
document is in scope only when accompanied by a Phase 6+ Lemma and a
canonical raw-data Merkle binding (Phase 8) — not before.

## 1. The empirical question

For each substrate `S` with a γ-emitting adapter:

* observed: `γ̂(S)` on real data (Theil–Sen on `log C → log K`)
* null distribution: `γ̂(S; surrogate_k)` for `k = 1 … M` per
  registered null family `F_j`
* per-family p-value: `p_j = (1 + #{|γ̂_null − μ_null| ≥ |γ̂_obs − μ_null|}) / (M + 1)`
  i.e. two-sided permutation tail with the null mean as the
  reference point. Reject when `γ̂_obs` is in the tail of the null
  distribution under H_0 = "the surrogated data carries no K↔C
  scaling structure".

Bonferroni-corrected per-family threshold: `α / k` where
`k = number of registered families`, `α = 0.05`.

## 2. Verdict ladder (closed set, no softening words)

A run emits exactly one of:

| verdict | meaning | proposed ladder status |
|---|---|---|
| `SIGNAL_SEPARATES_FROM_NULL` | every runnable family rejects null at α/k AND window sweep stable AND γ̂_obs non-degenerate | `SUPPORTED_BY_NULLS` |
| `NULL_NOT_REJECTED` | at least one runnable family fails to reject AND the estimator is non-pathological | `EVIDENCE_CANDIDATE_NULL_FAILED` |
| `ESTIMATOR_ARTIFACT_SUSPECTED` | window-sweep `Δγ_max > 0.05` (estimator depends on which sub-window of the trajectory it sees) | `INCONCLUSIVE` |
| `INCONCLUSIVE` | input data degenerate (constant series, insufficient samples) OR every requested family was non-applicable | `INCONCLUSIVE` |

No other verdicts. No "PROBABLY", "BORDERLINE", "MARGINAL",
"WEAKLY SUPPORTS", "SUGGESTS" anywhere in the output. The
`tests/test_phase_3_null_screen.py::test_no_softening_words_in_output`
adversarial test is a structural guard against drift here.

## 3. Substrate × family pinning

Each registered substrate names its family list explicitly in
`tools/phase_3/family_router.py`. There is no default surrogate.

| substrate | families | `n_families` | Bonferroni α |
|---|---|---|---|
| `serotonergic_kuramoto` | `kuramoto_iaaft`, `linear_matched`, `iaaft_surrogate` | 3 | 0.0167 |
| `hrv_fantasia` | `iaaft_surrogate`, `constrained_randomization`, `linear_matched` | 3 | 0.0167 |
| `eeg_resting` | `iaaft_surrogate`, `wavelet_phase`, `linear_matched` | 3 | 0.0167 |
| `synthetic_white_noise` | `iaaft_surrogate`, `linear_matched` | 2 | 0.0250 |
| `synthetic_power_law` | `iaaft_surrogate`, `linear_matched` | 2 | 0.0250 |
| `synthetic_constant` | `iaaft_surrogate`, `linear_matched` | 2 | 0.0250 |

Family applicability is dynamic: `linear_matched` requires
`n_signal ≥ 64` for the AR(8) Yule–Walker fit; if the trajectory is
shorter, that family is recorded as `verdict: NOT_APPLICABLE` and
excluded from the rejection quorum. `NOT_APPLICABLE` does **not**
silently advance a substrate to `SIGNAL_SEPARATES_FROM_NULL`.

## 4. Determinism contract

* Per-run seed: `seed = sha256(substrate || "phase_3" || str(M)).hexdigest()[:16]`.
* Per-family seed: `family_seed = sha256(seed || "|" || family).hexdigest()[:16]`.
* Two reruns at the same `(substrate, M)` (and library versions)
  return byte-identical `result_hash`. The
  `test_adversarial_6_result_hash_is_deterministic` test enforces
  this.
* Non-deterministic fields (`result_hash`, `generated_at_utc`,
  `runtime_seconds`) are stripped before hashing — see
  `tools/phase_3/result_hash.py::NON_DETERMINISTIC_FIELDS`.

## 5. Sample-size discipline

* `M ≥ 1000` is the precision floor. Below it,
  `1 / (M+1)` is too coarse to clear a typical Bonferroni α.
* The runner refuses to start at `M < 1000` unless `--smoke` is
  passed explicitly. `--smoke` is capped at `M < 1000` itself —
  it is not a back-door past the floor.
* CI:
  * PR-time: `M = 200` per registered substrate (smoke).
  * `push: main` and `merge_group`: `M = 10000` canonical run.

## 6. Window-sweep stability

The `tools/phase_3/stability.window_sweep` helper partitions the
trajectory into `n_windows = 4` overlapping sub-windows and computes
the per-window γ̂. The PASS rule is

    Δγ_max := max_w |γ̂_w − γ̂_full|  ≤  0.05

If the trajectory is too short for `n_windows × _MIN_WINDOW_LEN`
points (e.g. `serotonergic_kuramoto` with its 20-point concentration
sweep), the windows narrow accordingly and the resulting Δγ_max is
typically large — a structural signal that this substrate's
trajectory is too coarse for the sweep test, not a Phase 3 bug.
Such runs report `ESTIMATOR_ARTIFACT_SUSPECTED`.

## 7. Surrogate sanity guard

The `_screen_family` runner counts how often the generator returned
the **original target unchanged** (`np.allclose` on rtol=1e-12,
atol=1e-12). If more than 1 % of `M` draws are unchanged AND the
input has measurable variance, the run raises — the null is not a
null. The 1 % tolerance covers numerical edge cases of the
amplitude rank-remap step in IAAFT.

A constant input automatically disables this guard (a constant
input cannot have a non-trivial surrogate by construction); that
case routes to the `INCONCLUSIVE` verdict via the observed-γ
degeneracy path instead.

## 8. Output schema

The full JSON schema is defined-by-construction in
`tools/phase_3/run_null_screen.py::run_null_screen`. Highlights:

```json
{
  "phase_3_version": "3.0.0",
  "substrate": "<sid>",
  "smoke": <bool>,
  "seed": "<16-hex>",
  "M": <int>,
  "families": [...],
  "n_families": <int>,
  "alpha": 0.05,
  "bonferroni_alpha": <0.05 / n_families>,
  "observed_gamma": <float | null>,
  "observed_gamma_ci95": [<lo | null>, <hi | null>],
  "observed_gamma_n_used": <int>,
  "observed_gamma_degenerate": <bool>,
  "n_surrogates_per_family": <int>,
  "family_results": {
    "<family>": {
      "n_surrogates": <int>,
      "n_finite": <int>,
      "n_degenerate": <int>,
      "n_unchanged": <int>,
      "null_gamma_mean": <float | null>,
      "null_gamma_std": <float | null>,
      "null_gamma_quantiles": {"q025": ..., "q500": ..., "q975": ...},
      "p_value_distance_from_one": <float | null>,
      "effect_size_cohen_d": <float | null>,
      "effect_size_ci95": [<lo | null>, <hi | null>],
      "verdict": "REJECTED | NOT_REJECTED | NOT_APPLICABLE",
      "rejected_at_bonferroni": <bool>,
      "bonferroni_alpha": <float>,
      "notes": [...]
    }
  },
  "window_sweep": {
    "windows": [[start, stop], ...],
    "gammas": [<float>, ...],
    "delta_gamma_max": <float | null>,
    "stable": <bool>,
    "threshold": 0.05
  },
  "global_verdict": "SIGNAL_SEPARATES_FROM_NULL | NULL_NOT_REJECTED | ESTIMATOR_ARTIFACT_SUSPECTED | INCONCLUSIVE",
  "ledger_update": {
    "status_proposed": "SUPPORTED_BY_NULLS | EVIDENCE_CANDIDATE_NULL_FAILED | INCONCLUSIVE",
    "downgrade_reason_proposed": "NULL_NOT_REJECTED | null",
    "note": "PROPOSAL ONLY — ..."
  },
  "rerun_command": "python -m tools.phase_3.run_null_screen ...",
  "runtime_seconds": <float>,
  "trajectory_notes": [...],
  "generated_at_utc": "<iso8601>",
  "result_hash": "<64-hex>"
}
```

## 9. Adversarial guarantees (in `tests/test_phase_3_null_screen.py`)

1. IAAFT-of-pure-Gaussian-noise → not `SIGNAL_SEPARATES_FROM_NULL`.
2. Synthetic γ=1 generator → at least the per-family `iaaft_surrogate`
   p-value is `< 0.05` (positive control).
3. Constant series → `INCONCLUSIVE` or `ESTIMATOR_ARTIFACT_SUSPECTED`.
4. Surrogate-returns-original (mocked) → run raises
   `RuntimeError("null is not a null")`.
5. `M < 1000` without `--smoke` → run raises `ValueError`.
   `--smoke` cap of `M ≤ 999` enforced symmetrically.
6. Two reruns at the same seed → byte-identical `result_hash`.
7. Forced unstable trajectory → `window_sweep.stable = False`,
   `Δγ_max > threshold`, global verdict
   `ESTIMATOR_ARTIFACT_SUSPECTED`.
8. `ledger_update` block uses `_proposed`-suffixed field names only;
   no `status` or `downgrade_reason` direct-write keys; explicit
   `PROPOSAL ONLY` note. Phase 2.1 hash-binding gate continues to
   reject any forged ledger update without a real `result_hash`.

## 10. Honest expected outcome

Both currently-tested substrates (`serotonergic_kuramoto`,
`hrv_fantasia`) **already documented null failure** in Phase 2.1.
The Phase 3 v1 expectation is:

* `serotonergic_kuramoto` at `M = 10000`: an honest mixed result —
  `iaaft_surrogate` and `kuramoto_iaaft` reject the null at
  α/3 ≈ 0.017 (this PR's smoke at `M = 200` already shows
  `p ≈ 0.005` on both), `linear_matched` is `NOT_APPLICABLE`
  on the 20-point concentration sweep, and the
  4-window sweep on n=20 trajectories gives a large `Δγ_max`
  (windows of 8 points cannot stabilise the Theil–Sen fit). The
  practical global verdict is `ESTIMATOR_ARTIFACT_SUSPECTED` —
  **not** a promotion. The interpretation: the substrate's adapter
  produces a 20-point trajectory that is too coarse for window-sweep
  stability; the per-family IAAFT separations are real but cannot be
  promoted past the estimator-stability gate. **No promotion.**
* `hrv_fantasia`: data not provisioned in the v1 PR — adapter
  registered but loader returns `SubstrateDataUnavailableError`.
  Run requires a separate data-provisioning PR.
* `eeg_resting`: same as `hrv_fantasia`.

If the canonical `M = 10000` run on `serotonergic_kuramoto` retains
`ESTIMATOR_ARTIFACT_SUSPECTED`, the canonical answer is **the
γ ≈ 1.0 universality claim is not falsifiable in its current form on
this substrate at this trajectory length** — and Phase 4 must either
extend the trajectory (rerun the adapter at higher `_N_SWEEP`) or
change the estimator (e.g. quantile-pivoted Theil–Sen with sub-window
bagging). Phase 3 does not perform either.

## 11. What Phase 3 explicitly does NOT do

* Does **not** change `CANON_VALIDATED_FROZEN`.
* Does **not** add raw-file Merkle (`size_bytes`); that is Phase 8 / a
  separate PR.
* Does **not** build the out-of-process attestor (A5 strict); pure-Python
  language guarantees still hold.
* Does **not** soften the existing two failed null screens.
* Does **not** promote any substrate above `SUPPORTED_BY_NULLS`.
* Does **not** auto-merge any ledger update — every `ledger_update`
  block is a proposal that requires a separate human-reviewed PR.

`claim_status: derived` — Phase 3 derives a structured null-screen
result per substrate from the existing infrastructure; it does not
make any new positive measurement claim.
