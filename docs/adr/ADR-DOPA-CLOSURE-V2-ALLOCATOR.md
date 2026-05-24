# ADR: DOPA-CLOSURE v2 verification allocator

## Status
Proposed / Experimental

## Context
PR #199 is retained as retraction/guardrail artifact. The new work must avoid theory claims and provide a construct-validity-first verification allocator with conserved budget and auditable artifacts.

## Decision
- Introduce runtime-read SSOT config at `configs/dopa_closure_v2/allocator.yaml`.
- Introduce allocator implementation in `core/eai/dopa_closure_v2.py`.
- Enforce construct contract via `scripts/validate_dopa_closure_v2_contract.py`.
- Emit per-claim artifact and `budget_ledger.json` for every run.
- Use non-monotone inverted-U load gate, not `|vRPE|` threshold.

## Consequences
- Dopamine-like output is explicitly routing priority, not truth.
- CI can validate schema, contract, budget conservation, and artifact generation on full execution path.
- Any missing construct gate yields inadmissible instrument posture.
