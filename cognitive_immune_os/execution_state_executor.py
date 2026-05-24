from __future__ import annotations

from dataclasses import replace

from cognitive_immune_os.execution_programs import ExecutionProgram, ExecutionProgramId
from cognitive_immune_os.state_model import StateChange, StateStatus, VerifiedState


_PROGRAM_STATUS: dict[ExecutionProgramId, StateStatus] = {
    ExecutionProgramId.APPLY_VERIFIED_ACTION: StateStatus.ALLOWED,
    ExecutionProgramId.HOLD_FOR_RECHECK: StateStatus.HELD,
    ExecutionProgramId.REQUEST_STATE_RESYNC: StateStatus.RECHECK_REQUIRED,
    ExecutionProgramId.QUARANTINE_CLAIM: StateStatus.QUARANTINED,
    ExecutionProgramId.REDUCE_TO_REVERSIBLE_BOUNDARY: StateStatus.BOUNDARY_APPLIED,
    ExecutionProgramId.PRESERVE_VALUE_BOUNDARY: StateStatus.BOUNDARY_APPLIED,
    ExecutionProgramId.OPEN_REVIEW_TASK: StateStatus.RECHECK_REQUIRED,
}

_TERMINAL_STATUSES: frozenset[StateStatus] = frozenset(
    {
        StateStatus.ALLOWED,
        StateStatus.QUARANTINED,
        StateStatus.BOUNDARY_APPLIED,
        StateStatus.RECHECK_REQUIRED,
        StateStatus.HELD,
    }
)


def execute_program_transition(
    program: ExecutionProgram,
    state: VerifiedState,
) -> tuple[VerifiedState, StateChange]:
    next_status = _PROGRAM_STATUS[program.program_id]
    reason = f"{program.claim_id}:{program.program_id.value}:{program.source_decision_hash}"
    next_state = replace(
        state,
        status=next_status,
        notes=(*state.notes, reason),
    )
    change = StateChange(
        state_id=state.state_id,
        before=state.status,
        after=next_status,
        reason=reason,
    )
    return next_state, change


def execute_program_transitions(
    program: ExecutionProgram,
    states: dict[str, VerifiedState],
    target_ids: tuple[str, ...],
) -> tuple[dict[str, VerifiedState], tuple[StateChange, ...]]:
    if not target_ids:
        raise ValueError("target_ids must be non-empty")

    missing = tuple(state_id for state_id in target_ids if state_id not in states)
    if missing:
        missing_names = ", ".join(missing)
        raise KeyError(f"unknown target states: {missing_names}")

    next_states = dict(states)
    changes: list[StateChange] = []
    for state_id in sorted(set(target_ids)):
        next_state, change = execute_program_transition(program, next_states[state_id])
        next_states[state_id] = next_state
        changes.append(change)

    return next_states, tuple(changes)


def is_terminal_status(status: StateStatus) -> bool:
    return status in _TERMINAL_STATUSES
