# DOPA-CLOSURE — Minimal Verdict

## 1. Claim tested

vRPE-gated routing achieves higher Verified Closure Rate (VCR) than
`uncertainty_only` (the no-vRPE ablation) on a real claim-verification benchmark
under equal budget, and the advantage disappears under the inverted-vRPE
negative control.

## 2. Dataset

SciFact (allenai), binary SUPPORT (1) / CONTRADICT (0), NOINFO dropped.
505 train items, 188 dev items, deterministic, offline, no LLM judge.

## 3. Equal-budget condition

Budget unit = one bootstrap-model prediction call. `dopa_vrpe` spends a fixed
total of extra calls per seed; `uncertainty_only` and `random_gate` are capped at
≤ that total. All policies share one identical stochastic substrate per seed.

## 4. Policy scores (mean VCR, 10-seed sweep)

| policy | VCR |
|---|---|
| fixed_full (verify all, reference) | 0.5250 |
| uncertainty_only (no_vRPE ablation) | 0.5229 |
| **dopa_vrpe** | **0.5160** |
| random_gate | 0.5059 |
| dopa_vrpe_inverted | 0.5037 |
| cheap_only (0 budget) | 0.4947 |

Majority-class baseline (reference): 0.660.

## 5. Negative control result

`dopa_vrpe_inverted` (0.5037) < `dopa_vrpe` (0.5160): the control is well-formed
(conditions 3 and 4 of the predicate pass). The kill is driven by conditions 1
and 2, not by a degenerate control.

## 6. Verdict

**KILLED.** Δ(dopa_vrpe − uncertainty_only) = −0.0069 (required ≥ +0.02);
sign_fraction = 0.00 (dopa_vrpe did not exceed the no-vRPE ablation on any of the
10 seeds). Pre-registered survival predicate not met under equal budget.

## 7. What this proves

Under a real claim-verification dataset, equal budget, identical stochastic
substrate, and a frozen predicate, the vRPE signal carries no routing advantage
over ranking by raw classifier margin. Selective verification-budgeting (any
policy) does not beat verifying everything; `fixed_full ≥ all selective policies`.
The dopamine-like prediction-error gate is, on this benchmark, not functional —
consistent with the earlier synthetic-benchmark kill (PR #198).

## 8. What this does not prove

It does not show that no verification action can improve claim verification. The
TF-IDF cheap predictor and its bootstrap ensemble score below the majority-class
baseline (0.66); the kill is therefore scoped to a weak deterministic verifier
and a relative routing comparison. It makes no statement about biological
dopamine, cognition, or stronger verifiers.

## 9. Next required falsification

Any restart must, before re-testing any gate, independently pre-register: (a) a
verification action shown to exceed the majority-class baseline on the target
dataset, and (b) a vRPE estimator shown to be more budget-efficient than margin
ranking. No gate can rescue a verifier that is itself uninformative. Until then,
KILL-0979 stands as a valid, reproducible negative artifact.
