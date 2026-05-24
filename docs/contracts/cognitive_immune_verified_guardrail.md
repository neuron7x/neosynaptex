# Cognitive Immune OS verified guardrail

claim_status: derived

## Principle

Critical invariants must be derived, not declared.

## Runtime boundary

This document specifies a fail-closed runtime verification layer for PR #208.

It is not a court, legal engine, moral oracle, or theorem-level proof system.

## Executability contract

A proposed conflict action is executable only when all derived checks pass:

```text
Executable(action) =
  provenance_integrity
  AND observation_entropy_bound
  AND role_symmetry
  AND innocence_protection
  AND proportionality
  AND human_value_preservation
  AND distal_self_consistency
  AND memory_consistency
  AND adversarial_pressure_bound
  AND critical_quorum
```

## Non-admissible inputs

The runtime must not trust agent-supplied semantic flags for critical invariants.

These values must be reconstructed from evidence, memory, and action semantics:

- role symmetry
- target status
- proportionality
- target value preservation
- distal self consistency
- adversarial pressure

## Fail-closed rule

Unknown critical state is not executable. It is quarantined or resynchronized.

## Resolution outputs

The verified guardrail may return:

- `ALLOW`
- `HARD_BLOCK`
- `QUARANTINE`
- `REQUEST_RESYNC`
- `DEESCALATE`
- `BOUNDARY_WITHOUT_ERASURE`
- `ESCALATE_TO_HUMAN_REVIEW`
