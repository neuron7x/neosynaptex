from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionClass(str, Enum):
    REVERSIBLE_BOUNDARY = "REVERSIBLE_BOUNDARY"
    PUNITIVE = "PUNITIVE"
    IRREVERSIBLE_IMPACT = "IRREVERSIBLE_IMPACT"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    DEESCALATION = "DEESCALATION"
    QUARANTINE = "QUARANTINE"
    REPUTATIONAL_IMPACT = "REPUTATIONAL_IMPACT"
    RESOURCE_DENIAL = "RESOURCE_DENIAL"


@dataclass(frozen=True, slots=True)
class ActionEffect:
    utility_gain: float
    impact_risk: float
    trust_damage_risk: float
    reversibility: float
    blocking_cost: float
    error_cost: float

    def __post_init__(self) -> None:
        for name in ("impact_risk", "trust_damage_risk", "reversibility"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")
        if self.blocking_cost < 0.0:
            raise ValueError("blocking_cost must be non-negative")
        if self.error_cost < 0.0:
            raise ValueError("error_cost must be non-negative")


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    action_id: str
    action_class: ActionClass
    effect: ActionEffect
    punitive: bool = False
    irreversible: bool = False
    dehumanizing: bool = False
    requires_verified_guilt: bool = False
    requires_low_entropy: bool = True
    requires_valid_provenance: bool = True

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("action_id must be non-empty")
        if self.action_class is ActionClass.PUNITIVE and not self.punitive:
            raise ValueError("PUNITIVE action_class requires punitive=True")
        if self.action_class is ActionClass.IRREVERSIBLE_IMPACT and not self.irreversible:
            raise ValueError("IRREVERSIBLE_IMPACT action_class requires irreversible=True")


@dataclass(frozen=True, slots=True)
class ActionCatalog:
    actions: tuple[ActionDefinition, ...]

    def __post_init__(self) -> None:
        ids = [action.action_id for action in self.actions]
        if len(ids) != len(set(ids)):
            raise ValueError("ActionCatalog contains duplicate action_id values")

    def by_id(self) -> dict[str, ActionDefinition]:
        return {action.action_id: action for action in self.actions}

    def get(self, action_id: str) -> ActionDefinition | None:
        return self.by_id().get(action_id)

    def require(self, action_id: str) -> ActionDefinition:
        action = self.get(action_id)
        if action is None:
            raise KeyError(f"Unknown action_id: {action_id}")
        return action
