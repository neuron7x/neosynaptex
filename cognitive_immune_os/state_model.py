from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StateStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ALLOWED = "ALLOWED"
    HELD = "HELD"
    QUARANTINED = "QUARANTINED"
    RECHECK_REQUIRED = "RECHECK_REQUIRED"
    BOUNDARY_APPLIED = "BOUNDARY_APPLIED"
    DEMOTED = "DEMOTED"
    SCOPE_NARROWED = "SCOPE_NARROWED"
    UNTESTED = "UNTESTED"


@dataclass(frozen=True, slots=True)
class VerifiedState:
    state_id: str
    status: StateStatus
    depends_on: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StateChange:
    state_id: str
    before: StateStatus
    after: StateStatus
    reason: str
