# DOPA-VALIDITY-001 — Construct-Validity Checklist

Each gate is a hard stop. A failed gate yields an INADMISSIBLE verdict, which
is a **success** of the instrument, not a limitation to be softened in prose
(prose de-escalation of an admissibility blocker was itself a flagged #199
failure). Status reflects the seeded reference run on this branch.

| # | Hard gate | Mechanism | Status |
|---|---|---|---|
| 1 | **DNCA signal source exists and is imported** | `load_dopamine_operator()` imports + forward-runs the real `neuron7x_agents…DopamineOperator`; `None` ⇒ `INADMISSIBLE_MISSING_DNCA_EXECUTABLE_SIGNAL` | ✅ executable (torch 2.5.1) |
| 2 | **dopamine/vRPE is signed** | vRPE = pre-asymmetric `valence` = `clamp(δ,−1,1)`; sign preserved, not the ×5.5/×1.0-gained channel | ✅ |
| 3 | **Verifier beats majority AND random** | pure recomputation, deterministic, network-free; `beats_majority ∧ beats_random` else `INADMISSIBLE_WEAK_VERIFIER` | ✅ acc 1.0 > maj ≈0.52 > rand 0.5 |
| 4 | **Signed vRPE truth-correlated (precond. #3)** | Spearman of the **routed** `−vRPE` vs needs-verify, `p<0.01 ∧ ρ>0`, **fail-closed on an independent seed band disjoint from Step-D, all 12 seeds**; else `INADMISSIBLE_WEAK_VERIFIER` | ❌ 0/12 pass (median ρ=0.10, worst p=0.64) ⇒ clean INADMISSIBLE |
| 5 | **VCR is not plain accuracy** | VCR = budgeted closure-event rate ≠ policy label accuracy; equality ⇒ `INADMISSIBLE_METRIC_COLLAPSE` | ✅ definition + numeric guard |
| 6 | **Data/input CI-reproducible** | task synthesised from seeded `np.random.default_rng`; `data_hash` over all arrays; no git-ignored corpus | ✅ |
| 7 | **Negative control is real sign inversion** | `dopa_inverted = −dopa`; test rejects any `\|vRPE\|`-complement; must reorder routing | ✅ enforced by test |
| 8 | **Baselines include uncertainty_only and no_vRPE** | 6 policies: `dopa_signed_vrpe, uncertainty_only, no_vRPE, signed_vrpe_inverted, random_gate, verify_all` under equal budget | ✅ defined (only read at Step D) |
| 9 | **Statistical test exists for the delta** | paired Wilcoxon signed-rank over 12 seeds + rank-biserial effect size; pre-registered `ALPHA`, `DELTA_MIN` | ✅ implemented |
| 10 | **Config/code SSOT (no drift)** | every constant in `dopa_validity_001_config.py`; test asserts the experiment defines none | ✅ enforced |
| 11 | **Repro hash binds the conclusion** | `repro_hash = sha256(verdict ‖ all decision inputs)`; test asserts a mutated verdict changes it | ✅ |
| 12 | **No unscoped theory verdict** | a KILL is only `KILL-0979B…`, scoped; test forbids "DOPA-CLOSURE killed" | ✅ enforced |

## Reference-run verdict

`INADMISSIBLE_WEAK_VERIFIER` — the designed fail-closed success. Step A
genuinely passes (real executable DNCA dopamine signal); Step B1 passes
(verifier 1.0 ≫ baselines); **Step B2 fails closed**: on 12 independent seeds
disjoint from the Step-D decision draws, the routed `−vRPE` is *not* robustly
truth-correlated with verification benefit (**0/12 pass**, median ρ=0.10, worst
p=0.64). The instrument refuses to read the routing comparison.

No kill, no survival, no theory movement. The instrument **retracted its own
premature verdict**: an interim run (amendment A1) reported a scoped `KILLED`,
but that rested on a single non-independent draw (`cfg.SEED`, p=0.0066) — an
outlier. Hardening B2 to an independent, unanimous, fail-closed gate (amendment
A2) is faithful to RETRACTION precondition #3 and correctly withdrew that KILL.
**DOPA-CLOSURE the theory remains UNTESTED.** A clean INADMISSIBLE on a
fragile signal is exactly the failure class this machine exists to enforce.
