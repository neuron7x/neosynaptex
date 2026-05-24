from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConflictType(str, Enum):
    SELF_CONTRADICTION = "SELF_CONTRADICTION"
    INVALID_INSTRUMENT = "INVALID_INSTRUMENT"
    PUBLIC_SURFACE_OVERREACH = "PUBLIC_SURFACE_OVERREACH"
    EXTERNAL_REPLICATION_FAILURE = "EXTERNAL_REPLICATION_FAILURE"
    POLICY_BIAS = "POLICY_BIAS"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    DOCUMENTATION_AMBIGUITY = "DOCUMENTATION_AMBIGUITY"


class ConflictSeverity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"


@dataclass(frozen=True, slots=True)
class ConflictObject:
    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    targets: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    rationale: str
    cascade_required: bool = False
    policy_targets: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.conflict_id.strip():
            raise ValueError("conflict_id must be non-empty")
        if not self.targets:
            raise ValueError("targets must be non-empty")
        if not self.evidence_refs:
            raise ValueError("evidence_refs must be non-empty")
        if not self.rationale.strip():
            raise ValueError("rationale must be non-empty")
