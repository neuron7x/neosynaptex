# DOPA-VALIDITY-001 — Pre-Registration

Frozen before any result was read. Supersedes nothing in
`evidence/dopa_closure/RETRACTION.md` (authoritative). This pre-registers an
*instrument*, not a theory verdict. Constants live only in
`experiments/dopa_validity_001_config.py` (SSOT); `config_hash` pins them.

## Claim under test

> An *actual* DNCA/dopamine-derived **signed** vRPE predicts verification
> benefit better than uncertainty/margin, under an admissible verifier and a
> true sign-flip negative control.

This is a claim about an *instrument's discriminative validity*, not about
DOPA-CLOSURE. No run of this scaffold can promote or kill the theory.

## What counts as actual DNCA/dopamine signal

`neuron7x_agents.dnca.neuromodulators.dopamine.DopamineOperator`, imported and
forward-run. A sklearn/TF-IDF/logistic proxy is **forbidden** and is not the
signal under any renaming.

## Signed vRPE definition

`vRPE_i = clamp(δ_i, −1, 1)` from `DopamineOperator.modulate(...)["valence"]`,
where `δ = r + γ·V(s_t) − V(s_{t-1})` *before* the Schultz asymmetric gain.
`r` (reward context) is the policy's own confidence — **ground-truth-free**, so
no label leakage. Sign is preserved.

## True sign-flip negative control

`vRPE → −vRPE`, then routed on the signed value. Implemented as
`dopa_inverted = −dopa` with `dopa = −vRPE`. The complement of `|vRPE|` is
**forbidden** (the #199 function substitution). The control is required to be
non-degenerate: it must reorder routing when signs are mixed.

## Admissible verifier criteria

Independent of the policy; deterministic; network disabled; outcome bound to an
evidence hash under a fixed boundary; and **accuracy strictly above both the
majority-class and random baselines** on the target items.

## Verified Closure definition (distinct from accuracy)

A Verified-Closure event = the verifier spent a budgeted action on an item AND
returned a definitive VERIFIED/REFUTED under the fixed boundary. VCR =
events / items. It is **not** policy label accuracy: it counts independent
verifier-confirmed closures regardless of whether the policy's own label was
right. If VCR is numerically equal to policy accuracy → metric collapse.

## Pre-registered thresholds (no post-hoc tuning)

- Step B2 truth-correlation: two-sided Spearman of the **routed score**
  `dopa_route = −vRPE` against `needs_verify`, with `p < VRPE_TRUTH_CORR_ALPHA`
  (= 0.01) **and** `ρ > 0`. The gate is measured on the exact quantity Step D
  routes on (sign cannot contradict the routing direction) and, per RETRACTION
  precondition #3 ("*independently* shown truth-correlated, *before* any
  gate"), it is evaluated **fail-closed and independently**: on a dedicated
  seed band (`B2_SEED_OFFSET`, `N_B2_SEEDS` = 12) **disjoint** from the Step-D
  decision draws, and it must hold on **every** seed
  (`B2_REQUIRED_FRACTION` = 1.0). A single borderline draw never licenses a
  KILL/SURVIVED. Power note: N = 240/seed makes p < 0.01 high-powered for any
  moderate true effect, so unanimity across 12 independent draws is strict but
  not power-starved; it is symmetric (gates KILL and SURVIVED alike).
- Step D advantage: `delta ≥ DELTA_MIN` (= 0.05 of recoverable benefit).
- Step D significance: Wilcoxon signed-rank `p < ALPHA` (= 0.01), `N_SEEDS` = 12.
- Effect size: paired rank-biserial, reported regardless of sign.

Any retuning of these constants invalidates the run; they are hashed.

## Decision rules

- **INADMISSIBLE rule.** If Step A fails →
  `INADMISSIBLE_MISSING_DNCA_EXECUTABLE_SIGNAL`. If the verifier ≤ majority or
  ≤ random, **or** the signed vRPE is not truth-correlated per Step B2 →
  `INADMISSIBLE_WEAK_VERIFIER` (an uninformative routing signal is a weak
  instrument; RETRACTION precondition #3 made executable). If VCR collapses to
  accuracy → `INADMISSIBLE_METRIC_COLLAPSE`. A clean INADMISSIBLE is **success**.
- **Survival rule.** `SURVIVED_INITIAL` iff *all* hold: Steps A/B1/B2/C passed;
  `delta ≥ DELTA_MIN`; Wilcoxon `p < ALPHA`; the true sign-flip control loses
  its advantage; verifier stays above majority and random.
- **Kill rule.** If admissibility (A,B1,B2,C) passed but the survival
  conjunction fails → `KILLED`, written **only** as
  `KILL-0979B_DNCA_DOPA_ROUTING`, scoped strictly to this implementation. The
  theory remains UNTESTED. No unscoped "DOPA-CLOSURE killed" may ever be emitted.
- **No post-hoc tuning rule.** No threshold, seed, feature, or policy may be
  changed after observing any score. The `repro_hash` binds the verdict and all
  decision inputs, not merely a metric.

## Claim status

`claim_status: hypothesized` until a run reaches Step D with measured
policy scores; an INADMISSIBLE or scaffold-only run stays `hypothesized`.

## Amendment log

- **A1 (pre-merge, PR #200 review P1).** Step B2 originally correlated raw
  `vRPE` and required `ρ > 0`, contradicting the routed signal `−vRPE`. This
  was a genuine sign bug: it produced a **false** `INADMISSIBLE_WEAK_VERIFIER`
  by rejecting a signal that *is* weakly routed-correlated
  (`ρ(−vRPE, needs_verify) = +0.175`, `p = 0.0066 < 0.01` on the seed draw).
  Corrected to correlate the routed score `−vRPE` itself. Honest disclosure:
  this **did change the reference verdict**, from a false
  `INADMISSIBLE_WEAK_VERIFIER` to a legitimate scoped **`KILLED`**
  (`KILL-0979B`). The flip is *not* a theory rescue — the opposite: the now-
  admissible instrument shows the DNCA signed-vRPE routing is **worse than
  random** (`dopa ≈ 9.25` vs `uncertainty ≈ 9.17` vs `random ≈ 12.5`,
  `Δ = 0.002 ≪ 0.05`, Wilcoxon `p = 0.65`). All seven RETRACTION preconditions
  hold; the kill is scoped strictly to this implementation; DOPA-CLOSURE the
  theory remains UNTESTED. Constants unchanged; `config_hash` unaffected. No
  threshold was tuned after seeing data — only the gate's sign was aligned to
  the routing direction it had always declared.

- **A2 (pre-merge, frontier-rigor self-audit).** A1's B2 still measured the
  correlation on a *single* draw (`cfg.SEED`), the same family used downstream
  — not "independent", and `p = 0.0066` is a borderline single-draw pass. Per
  RETRACTION precondition #3 a destructive verdict (KILL/SURVIVED) must not
  rest on a fragile, non-independent gate. B2 is now evaluated **fail-closed**
  on an **independent** seed band disjoint from the Step-D draws, requiring
  significance + positive sign on **all 12** seeds. Honest disclosure: this
  **withdrew the A1 `KILLED`**. On 12 independent draws the signal is *not*
  robustly routed-correlated (**0/12 pass**, median `ρ = 0.10`, worst
  `p = 0.64`); the `cfg.SEED` draw was an outlier. Reference verdict returns to
  `INADMISSIBLE_WEAK_VERIFIER` — the correct fail-closed outcome: the prior
  KILL was a single-draw artifact and is **retracted**, not a finding. This is
  the instrument working as designed (it kills its own premature verdict).
  Constants are *added* (`B2_SEED_OFFSET`, `N_B2_SEEDS`, `B2_REQUIRED_FRACTION`),
  pre-registered here before the run; `VRPE_TRUTH_CORR_ALPHA`, `DELTA_MIN`,
  `ALPHA` unchanged. No data-driven tuning: the unanimity rule is a
  principled reading of "independently shown", fixed before observing the
  per-seed outcomes.
