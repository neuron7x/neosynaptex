from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from cognitive_immune_os.conflict_object import ConflictSeverity, ConflictType
from cognitive_immune_os.conflict_resolver import ResolutionAction

DEFAULT_POLICY_PATH = Path("contracts/cognitive_immune_os/conflict_types.yaml")


def _as_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def load_resolution_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[ConflictType, tuple[ResolutionAction, ...]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = _as_mapping(raw, "policy root")
    conflict_types = _as_mapping(root.get("conflict_types"), "conflict_types")

    policy: dict[ConflictType, tuple[ResolutionAction, ...]] = {}
    for conflict_name, conflict_raw in conflict_types.items():
        conflict_type = ConflictType(str(conflict_name))
        conflict_data = _as_mapping(conflict_raw, f"conflict_types.{conflict_name}")
        raw_actions = conflict_data.get("required_resolution")
        if not isinstance(raw_actions, list) or not raw_actions:
            raise ValueError(f"{conflict_name}.required_resolution must be a non-empty list")
        policy[conflict_type] = tuple(ResolutionAction(str(action)) for action in raw_actions)

    missing = set(ConflictType) - set(policy)
    if missing:
        missing_names = ", ".join(sorted(item.value for item in missing))
        raise ValueError(f"missing conflict policy entries: {missing_names}")
    return policy


def load_severity_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[ConflictType, ConflictSeverity]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = _as_mapping(raw, "policy root")
    conflict_types = _as_mapping(root.get("conflict_types"), "conflict_types")

    severities: dict[ConflictType, ConflictSeverity] = {}
    for conflict_name, conflict_raw in conflict_types.items():
        conflict_type = ConflictType(str(conflict_name))
        conflict_data = _as_mapping(conflict_raw, f"conflict_types.{conflict_name}")
        severities[conflict_type] = ConflictSeverity(str(conflict_data.get("severity")))
    return severities
