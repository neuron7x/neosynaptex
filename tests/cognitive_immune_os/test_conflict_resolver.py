from __future__ import annotations

import pytest

from cognitive_immune_os.conflict_object import ConflictObject, ConflictSeverity, ConflictType
from cognitive_immune_os.conflict_resolver import ResolutionAction, priority, resolve_conflict


def _conflict(conflict_type: ConflictType, severity: ConflictSeverity) -> ConflictObject:
    return ConflictObject(
        conflict_id="conflict.test.case",
        conflict_type=conflict_type,
        severity=severity,
        targets=("state.gamma.example",),
        evidence_refs=("evidence/example.json",),
        rationale="test rationale",
    )


def test_self_contradiction_is_p0_highest_priority() -> None:
    conflict = _conflict(ConflictType.SELF_CONTRADICTION, ConflictSeverity.P0)
    assert priority(conflict) == 0
    assert ResolutionAction.STATE_DEMOTION in resolve_conflict(conflict)


def test_self_contradiction_priority_ignores_caller_supplied_p6() -> None:
    conflict = _conflict(ConflictType.SELF_CONTRADICTION, ConflictSeverity.P6)
    assert priority(conflict) == 0


def test_invalid_instrument_marks_state_untested() -> None:
    conflict = _conflict(ConflictType.INVALID_INSTRUMENT, ConflictSeverity.P1)
    assert ResolutionAction.UNTESTED_MARKER in resolve_conflict(conflict)


def test_policy_bias_requires_policy_revision() -> None:
    conflict = _conflict(ConflictType.POLICY_BIAS, ConflictSeverity.P4)
    assert ResolutionAction.POLICY_REVISION in resolve_conflict(conflict)


@pytest.mark.parametrize("conflict_type", list(ConflictType))
def test_every_conflict_type_has_non_empty_resolution(conflict_type: ConflictType) -> None:
    conflict = _conflict(conflict_type, ConflictSeverity.P6)
    assert resolve_conflict(conflict)


def test_conflict_object_rejects_missing_evidence_refs() -> None:
    with pytest.raises(ValueError, match="evidence_refs"):
        ConflictObject(
            conflict_id="conflict.bad",
            conflict_type=ConflictType.STALE_EVIDENCE,
            severity=ConflictSeverity.P5,
            targets=("state.example",),
            evidence_refs=(),
            rationale="missing evidence refs",
        )
