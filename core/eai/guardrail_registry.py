from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal

from core.eai.constraint_index import InvalidationCondition, RevalidationArtifact, SemanticKeyIndex
from core.eai.intelligence_cycle import ClaimType, EvidenceArtifact, KillArtifact

Status = Literal[
    "ACTIVE", "CHALLENGED", "SCOPED_DOWN", "MERGED", "RETIRED", "SUPERSEDED", "STRENGTHENED"
]


@dataclass(frozen=True)
class GuardrailPatch:
    guardrail_id: str
    source_kill_artifact_id: str
    claim_id: str
    forbidden_pattern: str
    failure_mode: str
    applies_to_claim_types: list[ClaimType]
    applies_to_domains: list[str]
    validity_conditions: list[str]
    supersession_conditions: list[str]
    revalidation_tests: list[str]
    enforcement_level: Literal["warn", "quarantine", "kill"]
    status: Status
    version: int
    created_from_hash: str
    last_revalidated_at: str | None = None


@dataclass(frozen=True)
class RevalidationClaim:
    guardrail_id: str
    evidence_artifact_id: str
    reason: str


class GuardrailRegistry:
    def __init__(self) -> None:
        self._active: dict[str, GuardrailPatch] = {}
        self._history: list[GuardrailPatch] = []
        self._index = SemanticKeyIndex()

    def register_from_kill(
        self, artifact: KillArtifact, retention_hash: str, domain: str = "generic"
    ) -> GuardrailPatch:
        gid = f"GRD-{artifact.artifact_id.split('-')[-1]}"
        patch = GuardrailPatch(
            guardrail_id=gid,
            source_kill_artifact_id=artifact.artifact_id,
            claim_id=artifact.claim.claim_id,
            forbidden_pattern=artifact.claim.claim_text,
            failure_mode=artifact.failed_test,
            applies_to_claim_types=[artifact.claim.claim_type],
            applies_to_domains=[domain],
            validity_conditions=["until revalidated"],
            supersession_conditions=["external verification + reproducible test pass"],
            revalidation_tests=["provenance_check", "external_verification", "regression_test"],
            enforcement_level="kill",
            status="ACTIVE",
            version=1,
            created_from_hash=retention_hash,
        )
        self._active[gid] = patch
        self._history.append(patch)
        # semantic keys
        self._index.add(patch.forbidden_pattern.lower(), patch.guardrail_id)
        self._index.add(f"{patch.claim_id}:{patch.forbidden_pattern.lower()}", patch.guardrail_id)
        return patch

    def evaluate_candidate(self, candidate_text: str, claim_type: ClaimType) -> str:
        text = candidate_text.lower()
        for p in self._active.values():
            if (
                claim_type in p.applies_to_claim_types
                and p.forbidden_pattern.lower() in text
                and p.status in {"ACTIVE", "CHALLENGED", "STRENGTHENED"}
            ):
                return "KILLED" if p.enforcement_level == "kill" else "QUARANTINED"
        return "ALLOW"

    def scan_conflicts(self, evidence: EvidenceArtifact) -> list[RevalidationClaim]:
        claims: list[RevalidationClaim] = []
        seen: set[str] = set()
        text = evidence.claim.claim_text.lower()
        keys = [text, f"{evidence.claim.claim_id}:{text}"]
        candidate_ids = set(self._index.lookup_many(keys))

        for gid, patch in self._active.items():
            if patch.status not in {"ACTIVE", "CHALLENGED", "STRENGTHENED"}:
                continue
            pattern = patch.forbidden_pattern.lower()
            pattern_tokens = {t for t in pattern.replace(":", " ").split() if t}
            text_tokens = {t for t in text.replace(":", " ").split() if t}
            token_overlap = len(pattern_tokens & text_tokens)
            semantic_overlap = pattern in text or text in pattern or token_overlap >= 2
            if (gid in candidate_ids or semantic_overlap) and patch.guardrail_id not in seen:
                seen.add(patch.guardrail_id)
                claims.append(
                    RevalidationClaim(
                        patch.guardrail_id, evidence.artifact_id, "semantic key conflict"
                    )
                )
        return claims

    def apply_revalidation(
        self, claim: RevalidationClaim, passed: bool, scope_down_pattern: str | None = None
    ) -> GuardrailPatch:
        current = self._active[claim.guardrail_id]
        now = datetime.now(timezone.utc).isoformat()
        if not passed:
            updated = replace(
                current, status="CHALLENGED", version=current.version + 1, last_revalidated_at=now
            )
        elif scope_down_pattern:
            updated = replace(
                current,
                status="SCOPED_DOWN",
                version=current.version + 1,
                forbidden_pattern=scope_down_pattern,
                last_revalidated_at=now,
            )
        else:
            updated = replace(
                current, status="RETIRED", version=current.version + 1, last_revalidated_at=now
            )
        self._active[claim.guardrail_id] = updated
        self._history.append(updated)
        return updated

    @property
    def history(self) -> list[GuardrailPatch]:
        return self._history


def build_invalidation_condition(guardrail: GuardrailPatch) -> InvalidationCondition:
    return InvalidationCondition(
        condition_id=f"COND-{guardrail.guardrail_id}",
        anchor_id=guardrail.guardrail_id,
        subject="library:Y",
        predicate="supports",
        object="feature:Z",
        required_claim_type="software",
        invalidation_mode="satisfies_missing_evidence",
        version_constraint=None,
        required_evidence_classes=["package_registry_version"],
        required_tests=guardrail.revalidation_tests,
        required_external_verifiers=["docker_pytest_v0"],
        boundary_must_cover=["local deterministic verification only"],
        provenance_required=True,
    )


def build_revalidation_artifact(
    guardrail_id: str,
    evidence_artifact_id: str,
    old_state: str,
    new_state: str,
    decision: Literal["SCOPED_DOWN", "RETIRED", "SUPERSEDED", "STRENGTHENED", "UNCHANGED"],
) -> RevalidationArtifact:
    return RevalidationArtifact(
        revalidation_id=f"RVA-{guardrail_id}",
        guardrail_id=guardrail_id,
        evidence_artifact_id=evidence_artifact_id,
        old_guardrail_state=old_state,
        new_guardrail_state=new_state,
        decision=decision,
        decision_reason="state transition via revalidation",
        tests_run=["provenance_check", "external_verification"],
        boundary_before="old",
        boundary_after="new",
        retention_hash="a" * 64,
    )
