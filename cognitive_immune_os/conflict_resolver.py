from __future__ import annotations

from enum import Enum

from cognitive_immune_os.conflict_object import ConflictObject, ConflictSeverity


class ResolutionAction(str, Enum):
    STATE_DEMOTION = "STATE_DEMOTION"
    STATE_HOLD = "STATE_HOLD"
    STATE_RECHECK = "STATE_RECHECK"
    POLICY_REVISION = "POLICY_REVISION"
    SCOPE_NARROWING = "SCOPE_NARROWING"
    UNTESTED_MARKER = "UNTESTED_MARKER"


_SEVERITY_RANK: dict[ConflictSeverity, int] = {
    ConflictSeverity.P0: 0,
    ConflictSeverity.P1: 1,
    ConflictSeverity.P2: 2,
    ConflictSeverity.P3: 3,
    ConflictSeverity.P4: 4,
    ConflictSeverity.P5: 5,
    ConflictSeverity.P6: 6,
}


def resolve_conflict(conflict: ConflictObject) -> tuple[ResolutionAction, ...]:
    from cognitive_immune_os.policy_loader import load_resolution_policy

    actions = load_resolution_policy()[conflict.conflict_type]
    if not actions:
        raise RuntimeError("empty conflict resolution")
    return actions


def priority(conflict: ConflictObject) -> int:
    from cognitive_immune_os.policy_loader import load_severity_policy

    canonical_severity = load_severity_policy()[conflict.conflict_type]
    return _SEVERITY_RANK[canonical_severity]
