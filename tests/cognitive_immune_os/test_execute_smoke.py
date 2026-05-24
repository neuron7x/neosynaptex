from __future__ import annotations

from cognitive_immune_os.conflict_object import ConflictObject, ConflictSeverity, ConflictType
from cognitive_immune_os.conflict_resolver import ResolutionAction
from cognitive_immune_os.immune_executor import execute_conflict
from cognitive_immune_os.state_model import StateStatus, VerifiedState


def _event() -> ConflictObject:
    return ConflictObject(
        conflict_id="c0",
        conflict_type=ConflictType.STALE_EVIDENCE,
        severity=ConflictSeverity.P5,
        targets=("s0",),
        evidence_refs=("evidence/e0.json",),
        rationale="bounded case",
    )


def test_execute_conflict_changes_state_from_string_keyed_policy() -> None:
    states = {"s0": VerifiedState("s0", StateStatus.ACTIVE)}
    policy = {ConflictType.STALE_EVIDENCE.value: (ResolutionAction.STATE_RECHECK,)}
    next_states, changes = execute_conflict(_event(), states, policy=policy)
    assert next_states["s0"].status is StateStatus.RECHECK_REQUIRED
    assert changes[0].after is StateStatus.RECHECK_REQUIRED


def test_execute_conflict_changes_state_from_contract_loaded_key_shape() -> None:
    states = {"s0": VerifiedState("s0", StateStatus.ACTIVE)}
    policy = {ConflictType.STALE_EVIDENCE: (ResolutionAction.STATE_RECHECK,)}
    next_states, changes = execute_conflict(_event(), states, policy=policy)
    assert next_states["s0"].status is StateStatus.RECHECK_REQUIRED
    assert changes[0].after is StateStatus.RECHECK_REQUIRED
