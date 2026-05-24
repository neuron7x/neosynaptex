from __future__ import annotations

import pytest

from cognitive_immune_os.execution_programs import (
    ExecutionProgram,
    ExecutionProgramId,
    ExecutionStep,
    ExecutionStepId,
)
from cognitive_immune_os.execution_state_executor import (
    execute_program_transition,
    execute_program_transitions,
    is_terminal_status,
)
from cognitive_immune_os.state_model import StateStatus, VerifiedState


def _program(program_id: ExecutionProgramId) -> ExecutionProgram:
    return ExecutionProgram(
        program_id=program_id,
        claim_id="claim-001",
        steps=(ExecutionStep(ExecutionStepId.RECORD_DECISION, "record"),),
        source_decision_hash="sha256:abc",
    )


def test_apply_program_moves_active_to_allowed() -> None:
    state = VerifiedState("s0", StateStatus.ACTIVE)
    next_state, change = execute_program_transition(
        _program(ExecutionProgramId.APPLY_VERIFIED_ACTION),
        state,
    )

    assert next_state.status is StateStatus.ALLOWED
    assert change.before is StateStatus.ACTIVE
    assert change.after is StateStatus.ALLOWED
    assert "sha256:abc" in change.reason


def test_quarantine_program_moves_active_to_quarantined() -> None:
    state = VerifiedState("s0", StateStatus.ACTIVE)
    next_state, change = execute_program_transition(
        _program(ExecutionProgramId.QUARANTINE_CLAIM),
        state,
    )

    assert next_state.status is StateStatus.QUARANTINED
    assert change.after is StateStatus.QUARANTINED


def test_resync_program_moves_active_to_recheck_required() -> None:
    state = VerifiedState("s0", StateStatus.ACTIVE)
    next_state, change = execute_program_transition(
        _program(ExecutionProgramId.REQUEST_STATE_RESYNC),
        state,
    )

    assert next_state.status is StateStatus.RECHECK_REQUIRED
    assert change.after is StateStatus.RECHECK_REQUIRED


def test_boundary_program_moves_active_to_boundary_applied() -> None:
    state = VerifiedState("s0", StateStatus.ACTIVE)
    next_state, change = execute_program_transition(
        _program(ExecutionProgramId.REDUCE_TO_REVERSIBLE_BOUNDARY),
        state,
    )

    assert next_state.status is StateStatus.BOUNDARY_APPLIED
    assert change.after is StateStatus.BOUNDARY_APPLIED


def test_hold_program_moves_active_to_held() -> None:
    state = VerifiedState("s0", StateStatus.ACTIVE)
    next_state, change = execute_program_transition(
        _program(ExecutionProgramId.HOLD_FOR_RECHECK),
        state,
    )

    assert next_state.status is StateStatus.HELD
    assert change.after is StateStatus.HELD


def test_batch_transition_is_deterministic_and_sorted() -> None:
    states = {
        "s2": VerifiedState("s2", StateStatus.ACTIVE),
        "s1": VerifiedState("s1", StateStatus.ACTIVE),
    }

    next_states, changes = execute_program_transitions(
        _program(ExecutionProgramId.REQUEST_STATE_RESYNC),
        states,
        target_ids=("s2", "s1"),
    )

    assert tuple(change.state_id for change in changes) == ("s1", "s2")
    assert next_states["s1"].status is StateStatus.RECHECK_REQUIRED
    assert next_states["s2"].status is StateStatus.RECHECK_REQUIRED


def test_batch_transition_rejects_empty_targets() -> None:
    with pytest.raises(ValueError, match="target_ids"):
        execute_program_transitions(
            _program(ExecutionProgramId.REQUEST_STATE_RESYNC),
            {"s0": VerifiedState("s0", StateStatus.ACTIVE)},
            target_ids=(),
        )


def test_batch_transition_rejects_unknown_target() -> None:
    with pytest.raises(KeyError, match="unknown target"):
        execute_program_transitions(
            _program(ExecutionProgramId.REQUEST_STATE_RESYNC),
            {"s0": VerifiedState("s0", StateStatus.ACTIVE)},
            target_ids=("missing",),
        )


def test_terminal_status_predicate() -> None:
    assert is_terminal_status(StateStatus.ALLOWED)
    assert is_terminal_status(StateStatus.QUARANTINED)
    assert is_terminal_status(StateStatus.RECHECK_REQUIRED)
    assert is_terminal_status(StateStatus.BOUNDARY_APPLIED)
    assert is_terminal_status(StateStatus.HELD)
    assert not is_terminal_status(StateStatus.ACTIVE)
