# Machine Thinking Checklist — Conceptual & Governance Guide

## Why this exists

The checklist is not a bureaucratic form. It is a **falsification protocol** for engineering claims.
If a team cannot demonstrate checklist closure with evidence, the result is not considered complete.

Core principle:

> Discipline = completed checklist under machine verification.

This guide turns the RESEARCH·ENGINEERING checklist into a high-assurance operating model:

- Human reasoning artifacts stay explicit.
- Machine gate enforces binary closure (`PASS`/`FAIL`) plus structural conformance by profile.
- Governance can audit *why* a claim was accepted.

---

## Conceptual model

Each checklist item is treated as a **testable claim**.

- `[ ]` means claim is *not yet justified*.
- `[x]` means claim is *supported by evidence artifact(s)*.

Machine validator responsibilities:

1. Parse checklist items deterministically.
2. Count checked vs unchecked claims.
3. Return `PASS` only when all claims are checked and at least one claim exists.
4. Return `FAIL` otherwise, with line-level unresolved claims.

This design prevents “empty success” where a file exists but no meaningful closure happened.

---

## Checklist semantics by section

### PRE-WORK
Locks problem framing before implementation so post-hoc rationalization is harder.

### MATH
Ensures numeric/formal substrate is validated before code hides conceptual errors.

### IMPLEMENTATION
Forces responsibility boundaries, explicit state, and side-effect control.

### VALIDATION
Demands contract-level tests, adversarial probing, and reproducibility controls.

### FALSIFICATION
Requires active attempts to disprove your own result and isolate confounders.

### ARTIFACT
Makes outputs operationally consumable (run path, logs, ownership, version truth).

### GOVERNANCE
Bridges technical claim to PR claim, emergency controls, and rollback path.

### FINAL TEST
Imposes architectural minimality: remove/add perturbation should degrade outcome.

---

## Operational workflow

1. Copy the template:
   - `substrates/bn_syn/docs/MACHINE_THINKING_CHECKLIST_TEMPLATE.md`
2. Fill it during execution (do not batch-fill at the end).
3. Link each checked item to evidence in your working notes/PR body.
4. Run machine validation:

```bash
python substrates/bn_syn/scripts/validate_thinking_checklist.py \
  --checklist <your_checklist>.md \
  --json-out proof_bundle/reports/thinking_checklist_report.json
```

5. Treat non-zero exit as release-blocking until unresolved claims are closed.

---

## Governance posture

- `PASS` = structural completion signal (all claims closed).
- `PASS` is **necessary but not sufficient** for scientific truth.
- Reviewers still audit evidence quality and causal validity.

This is intentional: the machine gate verifies discipline; humans evaluate epistemic strength.


## Validation profiles

- `research_v1` (default): requires canonical sections (`PRE-WORK` ... `FINAL TEST`) and at least one checklist item in every section.
- `basic`: checks completion only (at least one item, all checked), without structural constraints.

This profile system enables both strict governance and lightweight local usage.


## Value metrics

Validator emits two complementary signals:

- `completion_ratio`: raw fraction of checked items.
- `value_score`: weighted completion where epistemically critical sections (`VALIDATION`, `FALSIFICATION`, `MATH`) carry higher weight.

Interpretation:
- High `completion_ratio` with low `value_score` means work is cosmetically complete but weak in critical reasoning layers.
- Governance should prioritize unresolved items in high-weight sections first.


## Definitional boundaries (what each signal IS / IS NOT)

Definition = setting the boundary between “this” and “that”.

- `completion_ratio`
  - **IS**: fraction of checked checklist items.
  - **IS NOT**: evidence quality or causal validity.

- `value_score`
  - **IS**: weighted completion emphasizing epistemically critical sections.
  - **IS NOT**: proof of correctness in domain science.

- `capital_index`
  - **IS**: composite operational readiness proxy for governance decisions.
  - **IS NOT**: financial valuation or business revenue forecast.

- `PASS`
  - **IS**: checklist gate satisfied under selected profile and thresholds.
  - **IS NOT**: guarantee that hypotheses are true in reality.

- `research_v1` profile
  - **IS**: strict canonical-structure + closure gate.
  - **IS NOT**: substitute for external replication/review.

- `basic` profile
  - **IS**: lightweight phase gate for draft/iteration loops.
  - **IS NOT**: release-grade assurance by default.
