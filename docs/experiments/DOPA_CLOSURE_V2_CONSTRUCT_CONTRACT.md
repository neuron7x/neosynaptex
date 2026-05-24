---
semantics: non-truth_routing
---

# DOPA-CLOSURE v2 Construct Contract

claim_status: derived

## Construct
DOPA-CLOSURE v2 is a **verification-budget allocator** for claims. It outputs priority-of-verification for claims, not truth labels.

## What is measured
- Priority-of-verification signal based on prediction_error, uncertainty, novelty, evidence_risk, reversibility, and system load.
- Budget-conserved allocation outcomes for `cheap_triage|verify|escalate|quarantine|reject|close`.

## What is NOT evidence
- Any statement that DOPA-CLOSURE theory is validated, falsified, or killed.
- Accuracy-only benchmark as proof of construct validity.
- Proxy substitution through generic sklearn classifier path.

## Forbidden proxies
- `|vRPE| >= tau` as sole gate.
- Sign-flip control under absolute-value gate.
- Unbudgeted hidden resources in one arm.

## Admissible substrate
Only routes passing construct-validity gate are admissible:
1. Explicit DNCA-compatible substrate declaration.
2. Explicit dopamine-like allocation mechanism implementation.
3. Predictive utility beyond trivial/majority/random baselines.
4. Closure metric not reduced to plain accuracy.
5. No sklearn-only inference proxy.

## Verdicts
- `ADMISSIBLE`
- `INADMISSIBLE`
- `QUARANTINED`
- `CLOSED`
- `REJECTED`
