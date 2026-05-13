from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class InvalidationCondition:
    condition_id: str
    anchor_id: str
    subject: str
    predicate: str
    object: str
    required_claim_type: str
    invalidation_mode: str
    version_constraint: str | None
    required_evidence_classes: list[str]
    required_tests: list[str]
    required_external_verifiers: list[str]
    boundary_must_cover: list[str]
    provenance_required: bool
    fail_closed_if_ambiguous: bool = True


@dataclass(frozen=True)
class RevalidationArtifact:
    revalidation_id: str
    guardrail_id: str
    evidence_artifact_id: str
    old_guardrail_state: str
    new_guardrail_state: str
    decision: Literal["SCOPED_DOWN", "RETIRED", "SUPERSEDED", "STRENGTHENED", "UNCHANGED"]
    decision_reason: str
    tests_run: list[str]
    boundary_before: str
    boundary_after: str
    retention_hash: str


class SemanticKeyIndex:
    def __init__(self) -> None:
        self._idx: dict[str, set[str]] = {}

    def add(self, key: str, guardrail_id: str) -> None:
        self._idx.setdefault(key, set()).add(guardrail_id)

    def lookup_many(self, keys: list[str]) -> set[str]:
        out: set[str] = set()
        for k in keys:
            out.update(self._idx.get(k, set()))
        return out
