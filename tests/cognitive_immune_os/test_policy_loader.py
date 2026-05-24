from __future__ import annotations

from pathlib import Path

from cognitive_immune_os.conflict_object import ConflictType
from cognitive_immune_os.conflict_resolver import ResolutionAction
from cognitive_immune_os.policy_loader import load_resolution_policy


def test_policy_loader_covers_every_event_type() -> None:
    policy = load_resolution_policy(Path("contracts/cognitive_immune_os/conflict_types.yaml"))
    assert set(policy) == set(ConflictType)


def test_policy_loader_reads_contract_action_values() -> None:
    policy = load_resolution_policy(Path("contracts/cognitive_immune_os/conflict_types.yaml"))
    assert policy[ConflictType.POLICY_BIAS][0] is ResolutionAction.POLICY_REVISION
