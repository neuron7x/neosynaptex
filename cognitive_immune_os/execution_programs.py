from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cognitive_immune_os.verified_guardrail import (
    VerificationResult,
    VerifiedDecisionReport,
    VerifiedInvariant,
    VerifiedResolutionAction,
    VerifiedVerdict,
)


class ExecutionProgramId(str, Enum):
    APPLY_VERIFIED_ACTION = "APPLY_VERIFIED_ACTION"
    HOLD_FOR_RECHECK = "HOLD_FOR_RECHECK"
    REQUEST_STATE_RESYNC = "REQUEST_STATE_RESYNC"
    QUARANTINE_CLAIM = "QUARANTINE_CLAIM"
    REDUCE_TO_REVERSIBLE_BOUNDARY = "REDUCE_TO_REVERSIBLE_BOUNDARY"
    PRESERVE_VALUE_BOUNDARY = "PRESERVE_VALUE_BOUNDARY"
    OPEN_REVIEW_TASK = "OPEN_REVIEW_TASK"


class ExecutionStepId(str, Enum):
    RECORD_DECISION = "RECORD_DECISION"
    PAUSE_EXECUTION = "PAUSE_EXECUTION"
    REQUIRE_EVIDENCE = "REQUIRE_EVIDENCE"
    REQUIRE_ROLE_CHECK = "REQUIRE_ROLE_CHECK"
    REQUIRE_TARGET_STATUS = "REQUIRE_TARGET_STATUS"
    REQUIRE_LOW_ENTROPY = "REQUIRE_LOW_ENTROPY"
    REQUIRE_MEMORY_RECHECK = "REQUIRE_MEMORY_RECHECK"
    APPLY_REVERSIBLE_BOUNDARY = "APPLY_REVERSIBLE_BOUNDARY"
    MARK_QUARANTINE = "MARK_QUARANTINE"
    APPLY_ACTION = "APPLY_ACTION"
    OPEN_REVIEW = "OPEN_REVIEW"


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    step_id: ExecutionStepId
    reason: str


@dataclass(frozen=True, slots=True)
class ExecutionProgram:
    program_id: ExecutionProgramId
    claim_id: str
    steps: tuple[ExecutionStep, ...]
    source_decision_hash: str

    @property
    def terminal_step(self) -> ExecutionStepId:
        return self.steps[-1].step_id


_STEP_BY_INVARIANT: dict[VerifiedInvariant, ExecutionStepId] = {
    VerifiedInvariant.PROVENANCE_INTEGRITY: ExecutionStepId.REQUIRE_EVIDENCE,
    VerifiedInvariant.OBSERVATION_ENTROPY_BOUND: ExecutionStepId.REQUIRE_LOW_ENTROPY,
    VerifiedInvariant.ROLE_SYMMETRY: ExecutionStepId.REQUIRE_ROLE_CHECK,
    VerifiedInvariant.INNOCENCE_PROTECTION: ExecutionStepId.REQUIRE_TARGET_STATUS,
    VerifiedInvariant.PROPORTIONALITY: ExecutionStepId.APPLY_REVERSIBLE_BOUNDARY,
    VerifiedInvariant.HUMAN_VALUE_PRESERVATION: ExecutionStepId.APPLY_REVERSIBLE_BOUNDARY,
    VerifiedInvariant.DISTAL_SELF_CONSISTENCY: ExecutionStepId.REQUIRE_MEMORY_RECHECK,
    VerifiedInvariant.MEMORY_CONSISTENCY: ExecutionStepId.REQUIRE_MEMORY_RECHECK,
    VerifiedInvariant.ADVERSARIAL_PRESSURE: ExecutionStepId.REQUIRE_EVIDENCE,
    VerifiedInvariant.CRITICAL_QUORUM: ExecutionStepId.REQUIRE_EVIDENCE,
}


def compile_execution_program(report: VerifiedDecisionReport) -> ExecutionProgram:
    if report.allowed:
        return ExecutionProgram(
            program_id=ExecutionProgramId.APPLY_VERIFIED_ACTION,
            claim_id=report.claim_id,
            steps=(
                ExecutionStep(ExecutionStepId.RECORD_DECISION, "record accepted verifier report"),
                ExecutionStep(ExecutionStepId.APPLY_ACTION, "all derived invariants passed"),
            ),
            source_decision_hash=report.audit.decision_hash,
        )

    diagnostics = _diagnostic_steps(report.results)
    if report.resolution_action is VerifiedResolutionAction.REQUEST_RESYNC:
        return _program(
            ExecutionProgramId.REQUEST_STATE_RESYNC,
            report,
            diagnostics,
            ExecutionStep(ExecutionStepId.REQUIRE_EVIDENCE, "refresh evidence and derived state"),
        )
    if report.resolution_action is VerifiedResolutionAction.QUARANTINE:
        return _program(
            ExecutionProgramId.QUARANTINE_CLAIM,
            report,
            diagnostics,
            ExecutionStep(ExecutionStepId.MARK_QUARANTINE, "hold claim outside executable state"),
        )
    if report.resolution_action is VerifiedResolutionAction.DEESCALATE:
        return _program(
            ExecutionProgramId.REDUCE_TO_REVERSIBLE_BOUNDARY,
            report,
            diagnostics,
            ExecutionStep(ExecutionStepId.APPLY_REVERSIBLE_BOUNDARY, "reduce to reversible boundary"),
        )
    if report.resolution_action is VerifiedResolutionAction.BOUNDARY_WITHOUT_ERASURE:
        return _program(
            ExecutionProgramId.PRESERVE_VALUE_BOUNDARY,
            report,
            diagnostics,
            ExecutionStep(ExecutionStepId.APPLY_REVERSIBLE_BOUNDARY, "preserve value while bounding scope"),
        )
    if report.resolution_action is VerifiedResolutionAction.ESCALATE_TO_HUMAN_REVIEW:
        return _program(
            ExecutionProgramId.OPEN_REVIEW_TASK,
            report,
            diagnostics,
            ExecutionStep(ExecutionStepId.OPEN_REVIEW, "manual review required"),
        )
    return _program(
        ExecutionProgramId.HOLD_FOR_RECHECK,
        report,
        diagnostics,
        ExecutionStep(ExecutionStepId.PAUSE_EXECUTION, "critical verifier result requires hold"),
    )


def _diagnostic_steps(results: tuple[VerificationResult, ...]) -> tuple[ExecutionStep, ...]:
    steps: list[ExecutionStep] = [ExecutionStep(ExecutionStepId.RECORD_DECISION, "record verifier report")]
    seen: set[ExecutionStepId] = set()
    for result in results:
        if result.verdict is VerifiedVerdict.PASS:
            continue
        step_id = _STEP_BY_INVARIANT[result.invariant]
        if step_id in seen:
            continue
        seen.add(step_id)
        steps.append(ExecutionStep(step_id=step_id, reason=result.failure_mode or result.reason))
    return tuple(steps)


def _program(
    program_id: ExecutionProgramId,
    report: VerifiedDecisionReport,
    diagnostics: tuple[ExecutionStep, ...],
    terminal: ExecutionStep,
) -> ExecutionProgram:
    steps = diagnostics if diagnostics[-1].step_id is terminal.step_id else (*diagnostics, terminal)
    return ExecutionProgram(
        program_id=program_id,
        claim_id=report.claim_id,
        steps=steps,
        source_decision_hash=report.audit.decision_hash,
    )
