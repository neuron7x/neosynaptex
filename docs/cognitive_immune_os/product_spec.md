# Cognitive Immune OS Product Specification

claim_status: derived

## 1. Product intent

Cognitive Immune OS is a deterministic runtime layer for conflict-driven verified-state evolution.

Its purpose is to convert ambiguous conflict pressure into auditable system transitions through derived evidence, explicit policies, replayable decisions, and deterministic execution programs.

It is not a truth oracle. It is not a scientific claim promotion system. It is an engineering control plane for bounded state evolution under uncertainty.

## 2. Problem statement

Static admission rules can become brittle. A fixed firewall may reject useful signal, admit polished falsehood, or preserve stale claims because no explicit pressure exists to revise state.

The system therefore needs a second layer:

```text
admission control decides what enters;
immune control decides how verified state changes after conflict.
```

The central engineering failure mode is trusting self-reported semantic flags from the same actor that benefits from the decision.

Cognitive Immune OS rejects that pattern.

## 3. Core invariant

```text
Critical invariants must be derived, not declared.
```

A claim may reference evidence, but it cannot authoritatively declare role symmetry, target status, proportionality, memory consistency, or admissibility.

Those properties are reconstructed from evidence graph state, action semantics, memory, and verifier outputs.

## 4. Runtime pipeline

```text
ConflictObject
  -> conflict resolver
  -> VerifiedState transition pressure

AgentClaim
  -> EvidenceGraph
  -> ActionCatalog
  -> SystemMemory
  -> CognitiveImmuneVerifiedCore
  -> VerifiedDecisionReport
  -> ReplayExpectation
  -> ExecutionProgram
  -> StateChange
```

The verified pipeline is deterministic for identical inputs.

## 5. Architecture components

### EvidenceGraph

The evidence graph provides structural evidence integrity:

- non-empty node identifiers;
- stable payload hash validation;
- missing parent rejection;
- duplicate node rejection;
- directed acyclic graph enforcement;
- minimum confidence support;
- producer diversity support;
- stable graph digest.

### ActionCatalog

The action catalog separates action semantics from actor claims.

Each action defines:

- class;
- expected utility;
- impact risk;
- trust damage risk;
- reversibility;
- blocking cost;
- error cost;
- whether verified target status is required;
- whether low observation entropy is required.

### CognitiveImmuneVerifiedCore

The verified core runs independent invariant verifiers and emits a fail-closed decision report.

Derived verifier set:

- provenance integrity;
- observation entropy bound;
- role symmetry;
- target status protection;
- proportionality;
- human value preservation;
- distal self consistency;
- memory consistency;
- adversarial pressure;
- critical quorum.

### Replay guard

Replay verifies that a decision is bound to the same claim hash, evidence graph hash, memory hash, and optional decision hash.

This prevents silent drift between decision-time and review-time state.

### Execution programs

Verified decisions compile into explicit execution programs:

- `APPLY_VERIFIED_ACTION`;
- `HOLD_FOR_RECHECK`;
- `REQUEST_STATE_RESYNC`;
- `QUARANTINE_CLAIM`;
- `REDUCE_TO_REVERSIBLE_BOUNDARY`;
- `PRESERVE_VALUE_BOUNDARY`;
- `OPEN_REVIEW_TASK`.

### State transition executor

Execution programs deterministically transition verified states:

```text
ACTIVE -> ALLOWED
ACTIVE -> HELD
ACTIVE -> QUARANTINED
ACTIVE -> RECHECK_REQUIRED
ACTIVE -> BOUNDARY_APPLIED
```

Each transition emits a `StateChange` record with before status, after status, and a decision-hash-bound reason.

## 6. Public runtime surface

Primary modules:

```text
cognitive_immune_os.evidence_graph
cognitive_immune_os.action_catalog
cognitive_immune_os.verified_guardrail
cognitive_immune_os.replay
cognitive_immune_os.execution_programs
cognitive_immune_os.execution_state_executor
```

Primary entry points:

```text
build_verified_cognitive_immune_core()
CognitiveImmuneVerifiedCore.evaluate(...)
replay_verified_decision(...)
compile_execution_program(...)
execute_program_transition(...)
execute_program_transitions(...)
```

## 7. Determinism guarantees

The runtime is designed to preserve deterministic behavior for identical inputs:

- sorted batch state transitions;
- stable hash computation;
- frozen dataclasses;
- explicit action catalog;
- explicit verifier order;
- no hidden network calls;
- no random number generation;
- no wall-clock dependency in decision hashing.

## 8. Test matrix

The focused test suite covers:

- conflict priority invariants;
- evidence reference requirements;
- contract-loaded resolution keys;
- evidence hash validation;
- evidence graph cycle rejection;
- missing provenance handling;
- role symmetry failure handling;
- target status uncertainty handling;
- high entropy handling;
- adversarial pressure handling;
- replay hash verification;
- execution program compilation;
- state transition execution;
- batch transition determinism;
- unknown target rejection;
- terminal status predicate.

## 9. Claim boundary

This product layer makes no claim about gamma scaling, intelligence, universality, biological validity, causal dynamics, substrate validation, or theorem-level moral safety.

It is a bounded runtime verification and state-transition product for conflict handling.

## 10. Reviewer checklist

A reviewer should verify:

- critical invariants are derived, not accepted as self-report;
- evidence integrity checks are structural and deterministic;
- high-impact paths fail closed under uncertainty;
- replay hashes bind decision state;
- execution programs are explicit and finite;
- state transitions are deterministic;
- workflow permissions are restricted;
- tests remain hermetic and avoid importing the full scientific stack.
