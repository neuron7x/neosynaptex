# EAI Checklist Status V1

## PRE-WORK
- Problem statement: defined.
- Falsifiable hypothesis: defined.
- Invariants before code: defined.
- I/O contract: defined in schemas and dataclasses.

## IMPLEMENTATION
- Isolated package: `core/eai`, `contracts/eai`, `tests/eai`.
- Side effects isolated in external verification runner.
- No integration of killed artifacts into knowledge memory.

## VALIDATION
- Protocol, schema, integration, redteam, calibration, verification tests exist.
- Contradiction trap baseline exists.

## FALSIFICATION
- Source contradiction and boundary expansion traps implemented.
- Guardrail/evidence collision revalidation implemented.

## ARTIFACT
- RFC, protocol docs, high-assurance spec, implementation report present.
- UTC timestamps present in external verification report model.
- Mandatory 2026 artifact stack tracked in `docs/eai/EAI_MANDATORY_ARTIFACT_STACK_2026.md`.

## GOVERNANCE CHECKS
- PR body ↔ claim consistency checks are in audit tests.
- Kill-path constraints and claim-status checks are covered in protocol/audit test slices.

## KNOWN GAPS
- Full 300-claim calibration dataset not yet implemented.
- Formal compliance pack (CAR/FRIA/PMSP/Annex IV mapping) is not complete.
- Data governance stack (lineage, consent metadata, DQA) is not complete.
- Full global CI health outside isolated EAI slice remains out of scope.

## EXIT CRITERIA FOR V1.1
- Promote all regulatory documents from planned to implemented.
- Publish reproducibility manifest with environment hashes and fixed seeds.
- Add one-page state-transition map and human-oversight runbook.
