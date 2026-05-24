from __future__ import annotations

from dataclasses import replace

from cognitive_immune_os.conflict_object import ConflictObject, ConflictType
from cognitive_immune_os.conflict_resolver import ResolutionAction, resolve_conflict
from cognitive_immune_os.state_model import StateChange, StateStatus, VerifiedState


PolicyMap = dict[ConflictType | str, tuple[ResolutionAction, ...]]

_ACTION_TO_STATUS: dict[ResolutionAction, StateStatus] = {
    ResolutionAction.STATE_DEMOTION: StateStatus.DEMOTED,
    ResolutionAction.STATE_HOLD: StateStatus.HELD,
    ResolutionAction.STATE_RECHECK: StateStatus.RECHECK_REQUIRED,
    ResolutionAction.POLICY_REVISION: StateStatus.RECHECK_REQUIRED,
    ResolutionAction.SCOPE_NARROWING: StateStatus.SCOPE_NARROWED,
    ResolutionAction.UNTESTED_MARKER: StateStatus.UNTESTED,
}


def dependent_state_ids(state_id: str, states: dict[str, VerifiedState]) -> tuple[str, ...]:
    seen: set[str] = set()
    queue = [candidate.state_id for candidate in states.values() if state_id in candidate.depends_on]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        queue.extend(candidate.state_id for candidate in states.values() if current in candidate.depends_on)
    return tuple(sorted(seen))


def _actions_for(conflict: ConflictObject, policy: PolicyMap | None) -> tuple[ResolutionAction, ...]:
    if policy is None:
        return resolve_conflict(conflict)
    if conflict.conflict_type in policy:
        return policy[conflict.conflict_type]
    return policy[conflict.conflict_type.value]


def execute_conflict(
    conflict: ConflictObject,
    states: dict[str, VerifiedState],
    policy: PolicyMap | None = None,
) -> tuple[dict[str, VerifiedState], tuple[StateChange, ...]]:
    actions = _actions_for(conflict, policy)
    if not actions:
        raise RuntimeError("empty conflict execution")

    target_ids = set(conflict.targets)
    if conflict.cascade_required:
        for target in conflict.targets:
            target_ids.update(dependent_state_ids(target, states))

    next_states = dict(states)
    changes: list[StateChange] = []
    first_status = _ACTION_TO_STATUS[actions[0]]
    reason = f"{conflict.conflict_id}:{conflict.conflict_type.value}"

    for state_id in sorted(target_ids):
        current = next_states[state_id]
        updated = replace(current, status=first_status, notes=(*current.notes, reason))
        next_states[state_id] = updated
        changes.append(StateChange(state_id=state_id, before=current.status, after=first_status, reason=reason))

    return next_states, tuple(changes)
