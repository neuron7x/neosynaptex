from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ClaimStatus(str, Enum):
    EVIDENCE = "EVIDENCE"
    KILLED = "KILLED"
    QUARANTINED = "QUARANTINED"


class ClaimType(str, Enum):
    FACTUAL = "factual"
    CAUSAL = "causal"
    PREDICTIVE = "predictive"
    SOFTWARE = "software"
    METHODOLOGICAL = "methodological"
    STATISTICAL = "statistical"
    SECURITY = "security"
    OPERATIONAL = "operational"
    THEORETICAL = "theoretical"
    COMPLIANCE = "compliance"


def _is_sha256_hex(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value or ""))


@dataclass
class ClaimCard:
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    assumptions: list[str] = field(default_factory=list)
    expected_observations: list[str] = field(default_factory=list)
    failure_conditions: list[str] = field(default_factory=list)


@dataclass
class BoundaryCard:
    boundary_id: str
    valid_for: list[str]
    invalid_for: list[str]
    tested_conditions: list[str]
    untested_conditions: list[str]

    def allows(self, context: str) -> bool:
        return context in self.valid_for and context not in self.invalid_for


@dataclass
class FalsificationReport:
    tests_run: list[str] = field(default_factory=list)
    passed: bool = False


@dataclass
class ReproducibilityManifest:
    commands: list[str] = field(default_factory=list)
    environment: str = ""
    artifact_hash: str = ""


@dataclass
class EvidenceArtifact:
    artifact_id: str
    claim: ClaimCard
    boundary: BoundaryCard | None
    falsification_report: FalsificationReport | None
    reproducibility: ReproducibilityManifest | None
    integration_permission: bool = True
    # Optional independent revalidation paths (e.g. multiple
    # cross-validation seeds, multiple redteam agent confirmations).
    # Default empty so existing callers see no behaviour change.
    # The graded-threshold gate (see core/eai/graded_gate.py)
    # requires len(revalidation_evidence_paths) to scale with
    # conflict_strength when that gate is used. Standard
    # decide_intent_update ignores this field.
    revalidation_evidence_paths: list[str] = field(default_factory=list)

    def can_be_promoted(self) -> bool:
        return bool(
            self.boundary
            and bool(set(self.boundary.valid_for) - set(self.boundary.invalid_for))
            and self.falsification_report
            and self.falsification_report.passed
            and self.falsification_report.tests_run
            and bool(set(self.boundary.tested_conditions).issubset(set(self.boundary.valid_for)))
            and self.reproducibility
            and _is_sha256_hex(self.reproducibility.artifact_hash)
            and self.integration_permission
        )


@dataclass
class KillArtifact:
    artifact_id: str
    claim: ClaimCard
    kill_reason: str
    failed_test: str
    future_guardrail: str
    retained: bool = True
    integration_permission: bool = False

    def can_be_integrated(self) -> bool:
        return False

    def is_high_quality_kill(self) -> bool:
        return all(
            [
                self.kill_reason.strip(),
                self.failed_test.strip(),
                self.future_guardrail.strip(),
                self.retained,
            ]
        )


@dataclass
class QuarantinedClaim:
    claim: ClaimCard
    quarantine_reason: str
    integration_permission: bool = False

    def can_update_integration_memory(self) -> bool:
        return False


def may_update_intent(
    artifact: EvidenceArtifact | None, *, retention_hash: str | None, revalidation_passed: bool
) -> bool:
    return bool(
        artifact
        and artifact.can_be_promoted()
        and _is_sha256_hex(retention_hash or "")
        and revalidation_passed
    )


def inference_seals_future_lie(
    next_intent_delta: dict[str, Any] | None, integration_patch: dict[str, Any] | None
) -> bool:
    """ICU policy: inference must both change next action and encode anti-regression controls."""
    if not next_intent_delta or not integration_patch:
        return False
    anti_regression = integration_patch.get("guardrail_update") or integration_patch.get(
        "regression_block"
    )
    return bool(anti_regression)


@dataclass
class IntelligenceClosureUnit:
    status: ClaimStatus
    artifact: EvidenceArtifact | KillArtifact | QuarantinedClaim | None
    retention_hash: str | None
    integration_patch: dict[str, Any] | None = None
    next_intent_delta: dict[str, Any] | None = None
    revalidation_passed: bool = False

    def is_intelligence_unit(self) -> bool:
        if self.status is ClaimStatus.EVIDENCE:
            return (
                isinstance(self.artifact, EvidenceArtifact)
                and bool(self.integration_patch and self.next_intent_delta)
                and may_update_intent(
                    self.artifact,
                    retention_hash=self.retention_hash,
                    revalidation_passed=self.revalidation_passed,
                )
            )
        if self.status is ClaimStatus.KILLED:
            return (
                isinstance(self.artifact, KillArtifact)
                and _is_sha256_hex(self.retention_hash or "")
                and self.artifact.is_high_quality_kill()
            )
        if self.status is ClaimStatus.QUARANTINED:
            return (
                isinstance(self.artifact, QuarantinedClaim)
                and self.integration_patch is None
                and _is_sha256_hex(self.retention_hash or "")
            )
        return False

    def satisfies_icu_policy(self) -> bool:
        """ICU = falsified + bounded + artifacted + intent-shifting + anti-regression."""
        if self.status is not ClaimStatus.EVIDENCE:
            return False
        return self.is_intelligence_unit() and inference_seals_future_lie(
            self.next_intent_delta, self.integration_patch
        )
