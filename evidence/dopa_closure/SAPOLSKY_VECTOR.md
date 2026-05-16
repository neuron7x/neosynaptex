# SAPOLSKY VECTOR — first-principles audit lens for cognitive/neuro AI claims

Distilled from Robert Sapolsky's published scientific positions
(*Behave*, *Determined*, *Why Zebras Don't Get Ulcers*, Stanford Human
Behavioral Biology lectures). This is a **transform**, not a corpus: each
axis is an operational invariant a claim must pass, with the failure it
catches. No book text is reproduced; page-level citation would only sharpen,
not change, these invariants.

Apply as: `claim → SV[1..8] → {PASS | VIOLATES + required redesign}`.

| # | Sapolsky first principle | Operational invariant | DOPA-CLOSURE verdict |
|---|--------------------------|-----------------------|----------------------|
| SV1 | Dopamine = anticipation / pursuit / *wanting*, uncertainty-ramped (peak at p≈0.5), not reward, not a scalar | Any "dopamine" variable must carry anticipation + effort + uncertainty structure, not a single error magnitude | **VIOLATES** — `vRPE` is a 1-D error-magnitude scalar; misses Fiorillo uncertainty ramp & wanting/effort |
| SV2 | No single cause; behavior is explained only across all timescales (1 s → sensory → hormonal → developmental → genetic → ecological → evolutionary) | Mechanism claims must declare which timescale(s) they cover and not generalize beyond them | **VIOLATES** — tests one context-free, ahistorical mechanism and spoke of "the theory" globally |
| SV3 | Allostasis / stress nonlinearly reshapes dopamine & PFC; chronic stress collapses prefrontal control | A cognitive-resource model must contain an arousal/stress state variable with nonlinear effect | **VIOLATES** — no arousal/allostatic axis; stationary controller |
| SV4 | No homunculus; behavior is fully determined, there is no executive "decider" (*Determined*) | Architecture must not smuggle an agentic chooser; "decision" must reduce to determined antecedents | **VIOLATES** — "agent/gate decides/chooses/allocates" language is homuncular |
| SV5 | Biology is inverted-U, not monotone (Yerkes–Dodson) | Control/response functions should admit a degrading regime at high drive, not a monotone σ | **VIOLATES** — gate is monotone σ(\|vRPE\|); no degradation regime |
| SV6 | Reductive materialist **but anti-essentialist**: a label is not the thing | A proxy may never be named as the construct it stands for | **VIOLATED then CORRECTED** — sklearn/ΔS called "DNCA" (#198/#199), retracted; now construct-gated |
| SV7 | Epistemic humility: distrust clean, confident brain stories; "it's complicated" is a stance | No confident/closed claim from an unvalidated or significant-but-void instrument | **VIOLATED then CORRECTED** — "closure complete" / significant-void number, retracted |
| SV8 | Categorical/bucket thinking distorts continua | Don't binarize inherently graded signals without justifying the boundary | **PARTIAL** — SUPPORT/CONTRADICT binarization and τ threshold imposed on continua without grounding |

## Vector residual (what the lens leaves intact)

Sapolsky-**compatible** core: dopamine as allocation-of-learning under
prediction error (Schultz/Montague line he teaches approvingly) and
falsification-first / kill-your-darlings. The violation is never the
*direction*; it is the **scalar, stationary, agentic, monotone,
context-free, label-as-thing** operationalization.

## Required redesign to pass the Sapolsky Vector (feeds reverse-cycle L5)

1. Replace scalar vRPE with an (anticipation, uncertainty@0.5, effort) triple.
2. Add an explicit arousal/allostatic state with an inverted-U transfer.
3. Strip agentic vocabulary; express routing as a determined function of
   antecedent state, audited as such.
4. Declare the single timescale covered; forbid "the theory" generalization.
5. Keep the construct-validity gate (SV6) and humility gate (SV7) as
   permanent preconditions, not afterthoughts.

This vector is now a standing precondition layer for any DOPA-CLOSURE
restart, alongside GAP_AUDIT.md and RETRACTION.md.
