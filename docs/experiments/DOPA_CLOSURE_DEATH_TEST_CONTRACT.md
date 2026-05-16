# DOPA-CLOSURE Death-Test Contract (BENCHMARK-CONTRACT-AUDITOR)

**Frozen before results were observed.** No post-hoc threshold tuning is permitted;
changing any constant after seeing numbers voids the artifact.

## 1. Exactly one survival predicate

Let `VCR(p)` = mean over the seed sweep of `correct_final_labels / total_items`
for policy `p`. The claim **SURVIVES_INITIAL iff ALL** hold, else **KILLED**:

1. `mean(VCR(dopa_vrpe)) − mean(VCR(uncertainty_only)) ≥ DELTA_MIN`
2. `sign(VCR(dopa_vrpe) − VCR(uncertainty_only)) > 0` in `≥ SIGN_FRAC` of seeds
3. `mean(VCR(dopa_vrpe)) > mean(VCR(random_gate))`
4. `mean(VCR(dopa_vrpe_inverted)) ≤ mean(VCR(dopa_vrpe)) − EPS`

`DELTA_MIN=0.02`, `SIGN_FRAC=0.70`, `EPS=0.01`, `SEED_SWEEP` = 10 fixed seeds.

## 2. Definitions (no vague metrics, no "quality")

- **Task input**: SciFact item = `claim [SEP] cited_title cited_abstract`.
- **Ground-truth label**: SUPPORT→1, CONTRADICT→0 (NOINFO excluded).
- **Cheap pass** (mandatory, free, identical for all policies): one TF-IDF +
  logistic-regression model fit on the train split; `cheap_pred` + signed
  `decision_function`; `margin = |decision_function|` (the only confidence proxy).
- **Expensive verification action**: majority vote of `K_VERIFY=8` bootstrap
  models (each refit on a bootstrap resample of train) — genuinely 8× compute.
- **Budget unit**: one bootstrap-model prediction call. `cheap_only`=0;
  `dopa_vrpe` pays 1 (probe) per item always + 8 if it routes VERIFY;
  budget-matched policies may spend ≤ the total extra calls `dopa_vrpe` spent.
- **vRPE**: `q_observed − q_expected`, `q_expected = sigmoid(K_CONF·margin)`,
  `q_observed = 1 if probe_model agrees with cheap_pred else 0`.
- **Route decision**: `dopa_vrpe` VERIFY iff `|vRPE| ≥ TAU`; `uncertainty_only`
  VERIFY the lowest-margin items greedily under budget; `dopa_vrpe_inverted`
  VERIFY iff `|vRPE| < TAU` (negative control).
- **Scoring rule**: final label per item = ensemble label if VERIFY else cheap
  label; `VCR` as above.
- **Failure rule / survival rule**: section 1, single predicate, frozen.

## 3. Required policies

`dopa_vrpe`, `uncertainty_only` (= no_vRPE ablation), `dopa_vrpe_inverted`
(negative control). References (not in predicate): `cheap_only`, `random_gate`,
`fixed_full`.

## 4. Result schema

`schemas/dopa_death_test_result.schema.json`. Required fields: `dataset_name`,
`seed_sweep`, `sample_count`, `policy_scores`, `delta_dopa_vs_uncertainty`,
`delta_dopa_vs_inverted`, `verdict ∈ {SURVIVED_INITIAL, KILLED}`, `kill_reason`,
`config_hash`, `dataset_hash`, `reproducibility_hash`.

## 5. Hard constraints

No LLM judge. No network at test time. Deterministic seeds. Identical examples
and identical stochastic substrate for every policy. No extra critic pass or
tool advantage for `dopa_vrpe`. Thresholds are frozen by this document.
