# DOPA-CLOSURE Death-Test — Adversarial Audit

Job: attack the evidence before it is trusted. Not protect the claim.

Inputs: `experiments/dopa_closure_death_test.py`,
`configs/dopa_closure/death_test.yaml`,
`evidence/dopa_closure/death_test_result.json`,
`tests/test_dopa_closure_death_test.py`.

Observed result: **KILLED**. dopa=0.5160, uncertainty_only=0.5229,
inverted=0.5037, random=0.5059, cheap=0.4947, fixed_full=0.5250;
Δ(dopa−unc)=−0.0069, sign_frac=0.00 over 10 seeds; N=188 dev / 505 train.

## Audit questions

1. **Does dopa_vrpe get more budget than uncertainty_only?** No — the opposite is
   structurally guaranteed. `dopa` spends `B`; budget-matched policies spend `≤ B`
   (`test_equal_budget_invariant`). dopa is, if anything, slightly advantaged on
   budget and still loses. Attack strengthens the kill.
2. **Thresholds tuned after results?** No. All constants frozen in the contract +
   `death_test.yaml`; `config_hash` pins them; result was generated once and the
   kill condition was pre-registered.
3. **Is inverted_vRPE a true negative control?** Yes — different verify set is
   asserted in `test_inverted_is_true_negative_control`; conditions 3 & 4 both
   pass (dopa>random, inverted<dopa−EPS), i.e. the control behaves as designed.
   The kill comes from conditions 1 & 2 (no advantage over no_vRPE), not a broken
   control.
4. **Does VCR reduce to plain accuracy?** It *is* per-item correctness against gold
   — but the predicate is purely *relative* (dopa vs uncertainty_only at equal
   budget on identical items), so absolute accuracy level cannot manufacture or
   hide the routing effect. Reduction is acknowledged and harmless to the verdict.
5. **Label leakage into routing?** No. Routing uses only `margin` and the
   probe/cheap agreement; gold labels enter only at final scoring. Train/dev
   disjoint; cheap model never sees dev.
6. **Does the dataset test claim verification?** Yes — SciFact SUPPORT/CONTRADICT
   with cited abstracts, real human annotations.
7. **Identical examples for all policies?** Yes — one shared `Substrate` per seed;
   policies are pure functions over it.
8. **Deterministic seeds?** Yes — `test_determinism` asserts run_seed
   reproducibility; fixed `SEED_SWEEP`; `reproducibility_hash` stable across reruns.
9. **Survives category breakdown?** Not separately computed; not required by the
   single predicate. Flagged as a limitation, not a blocker — the kill is global.
10. **Would a random router look competitive?** Yes, damningly: `random_gate`
    (0.5059) ≈ `dopa` (0.5160) ≈ `uncertainty_only` (0.5229), and `fixed_full`
    (0.5250) ≥ all selective policies. Selective verification-budgeting buys
    essentially nothing here. This is the core of the kill.

## Material limitation (must travel with the result)

All policies sit at ~0.49–0.53 while the **majority-class baseline is 124/188 ≈
0.66**. The TF-IDF cheap predictor (and its bootstrap ensemble) is *below
majority-class* on SUPPORT-vs-CONTRADICT — lexically near-identical classes. The
relative predicate is still valid and deterministic, but the boundary is narrow:
this kills *the routing-advantage claim under a weak deterministic verifier*. It
does **not** establish that no verification action could ever help — only that
the chosen one, gated by vRPE, does not beat margin ranking at equal budget.

## Audit verdict

**PASS_WITH_LIMITATIONS** — the kill is sound, fairly budgeted, leak-free,
deterministic, and adversarially robust (random/inverted/cheap controls all
expose it). The single limitation (weak base verifier, no category breakdown)
constrains the *scope* of the kill but does not weaken it; it is recorded in the
result boundary and the minimal verdict.
