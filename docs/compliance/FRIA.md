# Fundamental Rights Impact Assessment (FRIA)

## System Function
Evidence-gated promotion pipeline for research claims.

## Rights Risk Scenarios
1. False authority claim promoted without sufficient evidence.
2. Boundary expansion claims affecting downstream decisions.
3. Unequal failure handling across protected groups in evaluation datasets.

## Mitigations
- Fail-closed status (`KILLED` / `QUARANTINED`) for insufficient evidence.
- Guardrail revalidation lifecycle with append-only artifacts.
- Mandatory human review for high-impact claims.

## Open Actions
- Add protected-attribute fairness audit dataset.
- Add escalation workflow and accountable owner registry.
