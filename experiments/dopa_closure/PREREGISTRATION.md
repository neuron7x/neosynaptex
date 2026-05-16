# DOPA-CLOSURE — Kill-Ablation Pre-Registration

**Frozen before any run.** Author: Yaroslav Vasylenko / neuron7xLab. Date: 2026-05-16.

## 0. Scope of claim

This is an **admissibility / engineering** experiment on ONE deterministic benchmark
(`core.hallucination_benchmark.HallucinationBenchmark`, 15 ground-truth scenarios).
It is **not** a science claim about dopamine, cognition, or DOPA-CLOSURE as a general
principle. It tests exactly one falsifiable proposition and is allowed to kill it.

## 1. The single operational definition under test

> DOPA-CLOSURE has content **iff** a verification-prediction-error (vRPE) gate, built on
> top of one cheap probe, allocates a fixed verification budget *better than ranking by
> raw confidence margin alone* (`uncertainty_only`, which is exactly the `no_vRPE`
> ablation) at **equal extra-rollout budget**, and this advantage **collapses** when the
> vRPE sign is inverted.

If the cheap probe carries no information beyond the margin, DOPA ≡ uncertainty_only →
the dopamine-like component is decorative (RFC §13.3 / H0.6).

## 2. Mechanism (frozen)

Per scenario, one mandatory cheap pass → `final_delta_S`, verdict, `margin = final_delta_S − threshold`.

- `confidence = |margin|`
- `Q_expected = sigmoid(K_CONF · confidence)`  ∈ (0.5, 1)
- Cheap probe = **1** perturbation rerun; `Q_observed = 1.0` if probe verdict == cheap
  verdict else `0.0`
- `vRPE = Q_observed − Q_expected`
- Gate: `VERIFY` if `|vRPE| ≥ TAU` else `BYPASS`
- On `VERIFY`: `N_VERIFY` perturbation reruns; final verdict = majority over
  {cheap, probe, N_VERIFY}. On `BYPASS`: final verdict = cheap verdict.

## 3. Frozen constants

```
THRESHOLD     = 0.0      # HallucinationBenchmark default
K_CONF        = 8.0
TAU           = 0.35
N_VERIFY      = 8
NOISE_SCALE   = 0.05
SEED_SWEEP    = [11, 23, 42, 101, 202, 303, 404, 505, 606, 707]   # 10 seeds
DELTA_MIN     = 0.05     # ≈ one scenario-flip averaged
SIGN_FRAC     = 0.70     # delta must be positive in ≥70% of seeds
EPS           = 0.02
```

## 4. Strategies (all share the mandatory cheap pass; budget = EXTRA rollouts)

| strategy            | role                                  |
|---------------------|---------------------------------------|
| `cheap_only`        | floor, 0 extra budget                 |
| `dopa`              | vRPE-gated allocation under test      |
| `uncertainty_only`  | **= no_vRPE ablation**, margin-rank, budget-matched to `dopa` |
| `random_gate`       | random allocation, budget-matched     |
| `dopa_inverted`     | negative control: gate on `|vRPE| < TAU` |
| `fixed_full`        | ceiling, verify all (not budget-matched, labelled) |

Budget match: B = total extra rollouts spent by `dopa` on that seed; `uncertainty_only`
and `random_gate` may spend ≤ B extra rollouts (greedy, N_VERIFY per verified scenario).

## 5. Pre-registered KILL CONDITION (no heroic narrative)

Let mean over SEED_SWEEP of accuracy be `A(·)`.

`SURVIVED` **iff ALL** hold:
1. `A(dopa) − A(uncertainty_only) ≥ DELTA_MIN`
2. sign(`acc(dopa) − acc(uncertainty_only)`) > 0 in ≥ `SIGN_FRAC` of seeds
3. `A(dopa) > A(random_gate)`
4. `A(dopa_inverted) ≤ A(random_gate) + EPS`

Otherwise → `KILLED_OR_RESCOPED`. Object joins the falsification graveyard with a
reproducibility hash. That is a valid, fast, cheap deliverable — not a failure.

## 6. Reproducibility

SHA-256 over the JSON of `{constants, per-seed per-strategy accuracy/precision/recall/cost}`
is written to the artifact. Same code + same SEED_SWEEP must reproduce the hash.
