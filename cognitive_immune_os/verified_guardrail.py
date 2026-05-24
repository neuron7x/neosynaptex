from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from cognitive_immune_os.action_catalog import ActionCatalog
from cognitive_immune_os.evidence_graph import EvidenceGraph, sha256_text


class VerifiedVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class VerifiedSeverity(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VerifiedDecisionStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    QUARANTINED = "QUARANTINED"


class VerifiedResolutionAction(str, Enum):
    ALLOW = "ALLOW"
    HARD_BLOCK = "HARD_BLOCK"
    QUARANTINE = "QUARANTINE"
    REQUEST_RESYNC = "REQUEST_RESYNC"
    DEESCALATE = "DEESCALATE"
    BOUNDARY_WITHOUT_ERASURE = "BOUNDARY_WITHOUT_ERASURE"
    ESCALATE_TO_HUMAN_REVIEW = "ESCALATE_TO_HUMAN_REVIEW"


class VerifiedInvariant(str, Enum):
    PROVENANCE_INTEGRITY = "PROVENANCE_INTEGRITY"
    OBSERVATION_ENTROPY_BOUND = "OBSERVATION_ENTROPY_BOUND"
    ROLE_SYMMETRY = "ROLE_SYMMETRY"
    INNOCENCE_PROTECTION = "INNOCENCE_PROTECTION"
    PROPORTIONALITY = "PROPORTIONALITY"
    HUMAN_VALUE_PRESERVATION = "HUMAN_VALUE_PRESERVATION"
    DISTAL_SELF_CONSISTENCY = "DISTAL_SELF_CONSISTENCY"
    MEMORY_CONSISTENCY = "MEMORY_CONSISTENCY"
    ADVERSARIAL_PRESSURE = "ADVERSARIAL_PRESSURE"
    CRITICAL_QUORUM = "CRITICAL_QUORUM"


CRITICAL_INVARIANTS = frozenset(
    {
        VerifiedInvariant.PROVENANCE_INTEGRITY,
        VerifiedInvariant.ROLE_SYMMETRY,
        VerifiedInvariant.INNOCENCE_PROTECTION,
        VerifiedInvariant.HUMAN_VALUE_PRESERVATION,
        VerifiedInvariant.CRITICAL_QUORUM,
    }
)


@dataclass(frozen=True, slots=True)
class CognitiveParameters:
    min_agent_value: float = 1.0
    max_observation_entropy: float = 0.35
    min_evidence_confidence: float = 0.80
    min_critical_confidence: float = 0.85
    max_impact_for_unresolved_status: float = 0.05
    max_trust_damage_for_allow: float = 0.50
    max_adversarial_pressure: float = 0.55
    min_quorum_ratio: float = 1.0
    max_repeated_escalations: int = 2
    punitive_requires_verified_status: bool = True
    irreversible_requires_verified_status: bool = True
    fail_closed_on_unknown: bool = True


@dataclass(frozen=True, slots=True)
class AgentProfile:
    agent_id: str
    role: str
    minimum_value: float = 1.0

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty")
        if not self.role.strip():
            raise ValueError("role must be non-empty")
        if self.minimum_value < 0.0:
            raise ValueError("minimum_value must be non-negative")


@dataclass(frozen=True, slots=True)
class AgentClaim:
    claim_id: str
    actor: AgentProfile
    target: AgentProfile
    action_id: str
    claimed_reason: str
    claimed_expected_utility: float
    evidence_refs: tuple[str, ...]
    created_at_utc: str

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ValueError("claim_id must be non-empty")
        if not self.action_id.strip():
            raise ValueError("action_id must be non-empty")
        if not self.claimed_reason.strip():
            raise ValueError("claimed_reason must be non-empty")


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    event_id: str
    agent_id: str
    event_type: str
    polarity: str
    payload: dict[str, object]
    evidence_refs: tuple[str, ...] = ()
    timestamp_utc: str = ""


@dataclass(frozen=True, slots=True)
class SystemMemory:
    events: tuple[MemoryEvent, ...] = ()

    def count_events(self, agent_id: str, event_type: str) -> int:
        return sum(
            1
            for event in self.events
            if event.agent_id == agent_id and event.event_type == event_type
        )

    def has_contradiction(self, agent_id: str) -> bool:
        return self.count_events(agent_id, "self_contradiction") > 0

    def repeated_escalations(self, agent_id: str) -> int:
        return self.count_events(agent_id, "escalation")

    def digest(self) -> str:
        payload = [
            {
                "event_id": event.event_id,
                "agent_id": event.agent_id,
                "event_type": event.event_type,
                "polarity": event.polarity,
                "payload": event.payload,
                "evidence_refs": event.evidence_refs,
                "timestamp_utc": event.timestamp_utc,
            }
            for event in self.events
        ]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return sha256_text(encoded)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    invariant: VerifiedInvariant
    verdict: VerifiedVerdict
    severity: VerifiedSeverity
    confidence: float
    evidence_used: tuple[str, ...]
    reason: str
    failure_mode: str | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    decision_hash: str
    claim_hash: str
    evidence_graph_hash: str
    memory_hash: str
    verifier_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerifiedDecisionReport:
    claim_id: str
    status: VerifiedDecisionStatus
    resolution_action: VerifiedResolutionAction
    allowed: bool
    fail_closed: bool
    results: tuple[VerificationResult, ...]
    audit: AuditRecord


class InvariantVerifier(Protocol):
    name: VerifiedInvariant

    def verify(
        self,
        claim: AgentClaim,
        evidence: EvidenceGraph,
        memory: SystemMemory,
        catalog: ActionCatalog,
        params: CognitiveParameters,
    ) -> VerificationResult: ...


def _result(
    invariant: VerifiedInvariant,
    verdict: VerifiedVerdict,
    severity: VerifiedSeverity,
    confidence: float,
    evidence_used: tuple[str, ...],
    reason: str,
    failure_mode: str | None = None,
) -> VerificationResult:
    return VerificationResult(
        invariant,
        verdict,
        severity,
        max(0.0, min(1.0, confidence)),
        evidence_used,
        reason,
        failure_mode,
    )


def _pass(inv: VerifiedInvariant, confidence: float, refs: tuple[str, ...], reason: str) -> VerificationResult:
    return _result(inv, VerifiedVerdict.PASS, VerifiedSeverity.LOW, confidence, refs, reason)


def _fail(
    inv: VerifiedInvariant,
    severity: VerifiedSeverity,
    confidence: float,
    refs: tuple[str, ...],
    reason: str,
    mode: str,
) -> VerificationResult:
    return _result(inv, VerifiedVerdict.FAIL, severity, confidence, refs, reason, mode)


def _unknown(
    inv: VerifiedInvariant,
    severity: VerifiedSeverity,
    confidence: float,
    refs: tuple[str, ...],
    reason: str,
    mode: str,
) -> VerificationResult:
    return _result(inv, VerifiedVerdict.UNKNOWN, severity, confidence, refs, reason, mode)


class ProvenanceIntegrityVerifier:
    name = VerifiedInvariant.PROVENANCE_INTEGRITY

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del memory, catalog
        if not claim.evidence_refs:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, (), "claim has no evidence refs", "NO_EVIDENCE_REFS")
        try:
            selected = evidence.require(claim.evidence_refs)
        except ValueError as exc:
            return _fail(self.name, VerifiedSeverity.CRITICAL, 1.0, claim.evidence_refs, str(exc), "MISSING_EVIDENCE_REF")
        min_confidence = min(node.confidence for node in selected)
        if min_confidence < params.min_evidence_confidence:
            return _unknown(self.name, VerifiedSeverity.HIGH, min_confidence, claim.evidence_refs, "evidence confidence below threshold", "LOW_EVIDENCE_CONFIDENCE")
        return _pass(self.name, min_confidence, claim.evidence_refs, "provenance references exist and hashes validated")


class ObservationEntropyVerifier:
    name = VerifiedInvariant.OBSERVATION_ENTROPY_BOUND

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del memory
        action = catalog.get(claim.action_id)
        if action is None:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "unknown action_id", "UNKNOWN_ACTION")
        try:
            selected = evidence.require(claim.evidence_refs)
        except ValueError:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "missing evidence for entropy derivation", "MISSING_EVIDENCE_REF")
        values = [float(node.payload.get("observation_entropy", 1.0)) for node in selected if "observation_entropy" in node.payload]
        entropy = max(values) if values else 1.0
        if action.requires_low_entropy and entropy > params.max_observation_entropy:
            return _fail(self.name, VerifiedSeverity.HIGH, 1.0 - entropy, claim.evidence_refs, "observation entropy exceeds threshold", "OBSERVATION_ENTROPY_TOO_HIGH")
        return _pass(self.name, 1.0 - entropy, claim.evidence_refs, "observation entropy is bounded")


class RoleSymmetryVerifier:
    name = VerifiedInvariant.ROLE_SYMMETRY

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del memory, catalog, params
        try:
            selected = evidence.require(claim.evidence_refs)
        except ValueError:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "missing evidence for role symmetry", "MISSING_EVIDENCE_REF")
        values = [bool(node.payload["role_symmetry_pass"]) for node in selected if "role_symmetry_pass" in node.payload]
        if not values:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "missing role-symmetry evidence", "MISSING_ROLE_SYMMETRY_EVIDENCE")
        if not all(values):
            return _fail(self.name, VerifiedSeverity.CRITICAL, evidence.min_confidence(claim.evidence_refs), claim.evidence_refs, "rule fails role reversal", "ROLE_REVERSAL_ASYMMETRY")
        return _pass(self.name, evidence.min_confidence(claim.evidence_refs), claim.evidence_refs, "role reversal passed")


class InnocenceProtectionVerifier:
    name = VerifiedInvariant.INNOCENCE_PROTECTION

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del memory
        action = catalog.get(claim.action_id)
        if action is None:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "unknown action_id", "UNKNOWN_ACTION")
        try:
            selected = evidence.require(claim.evidence_refs)
        except ValueError:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "missing evidence for status derivation", "MISSING_EVIDENCE_REF")
        statuses = [str(node.payload["guilt_status"]) for node in selected if "guilt_status" in node.payload]
        status = self._merge_status(statuses)
        requires_verified = (
            action.requires_verified_guilt
            or (params.punitive_requires_verified_status and action.punitive)
            or (params.irreversible_requires_verified_status and action.irreversible)
        )
        if requires_verified and status != "VERIFIED_GUILTY":
            return _fail(self.name, VerifiedSeverity.CRITICAL, evidence.min_confidence(claim.evidence_refs), claim.evidence_refs, "verified target status required", f"STATUS_REQUIRED_BUT_{status}")
        if status != "VERIFIED_GUILTY" and action.effect.impact_risk > params.max_impact_for_unresolved_status:
            return _fail(self.name, VerifiedSeverity.CRITICAL, evidence.min_confidence(claim.evidence_refs), claim.evidence_refs, "impact risk under unresolved status exceeds threshold", f"IMPACT_WITH_{status}")
        return _pass(self.name, evidence.min_confidence(claim.evidence_refs), claim.evidence_refs, "target status invariant preserved")

    def _merge_status(self, statuses: list[str]) -> str:
        if not statuses:
            return "INSUFFICIENT_EVIDENCE"
        unique = set(statuses)
        if "VERIFIED_INNOCENT" in unique:
            return "VERIFIED_INNOCENT"
        if "CONTESTED" in unique:
            return "CONTESTED"
        if "VERIFIED_GUILTY" in unique and len(unique) == 1:
            return "VERIFIED_GUILTY"
        if "UNKNOWN" in unique:
            return "UNKNOWN"
        return "INSUFFICIENT_EVIDENCE"


class ProportionalityVerifier:
    name = VerifiedInvariant.PROPORTIONALITY

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del evidence, memory
        action = catalog.get(claim.action_id)
        if action is None:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "unknown action_id", "UNKNOWN_ACTION")
        effect = action.effect
        if effect.impact_risk > 0.75 and effect.reversibility < 0.25:
            return _fail(self.name, VerifiedSeverity.HIGH, 0.90, claim.evidence_refs, "high impact with low reversibility", "HIGH_IMPACT_LOW_REVERSIBILITY")
        if effect.trust_damage_risk > params.max_trust_damage_for_allow:
            return _fail(self.name, VerifiedSeverity.HIGH, 0.90, claim.evidence_refs, "trust damage exceeds threshold", "TRUST_DAMAGE_TOO_HIGH")
        return _pass(self.name, 0.90, claim.evidence_refs, "proportionality passed")


class HumanValuePreservationVerifier:
    name = VerifiedInvariant.HUMAN_VALUE_PRESERVATION

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del evidence, memory
        action = catalog.get(claim.action_id)
        if action is None:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "unknown action_id", "UNKNOWN_ACTION")
        if claim.target.minimum_value < params.min_agent_value:
            return _fail(self.name, VerifiedSeverity.CRITICAL, 1.0, claim.evidence_refs, "target minimum value below system minimum", "TARGET_VALUE_BELOW_MINIMUM")
        if action.dehumanizing:
            return _fail(self.name, VerifiedSeverity.CRITICAL, 1.0, claim.evidence_refs, "action violates target value preservation", "TARGET_VALUE_ERASURE_ACTION")
        return _pass(self.name, 1.0, claim.evidence_refs, "target agent value preserved")


class DistalSelfConsistencyVerifier:
    name = VerifiedInvariant.DISTAL_SELF_CONSISTENCY

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del evidence, catalog, params
        if memory.has_contradiction(claim.actor.agent_id):
            return _fail(self.name, VerifiedSeverity.HIGH, 0.90, claim.evidence_refs, "actor has self-contradiction history", "ACTOR_SELF_CONTRADICTION_HISTORY")
        return _pass(self.name, 0.90, claim.evidence_refs, "actor memory contains no self-contradiction")


class MemoryConsistencyVerifier:
    name = VerifiedInvariant.MEMORY_CONSISTENCY

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del evidence, catalog
        if memory.repeated_escalations(claim.actor.agent_id) > params.max_repeated_escalations:
            return _fail(self.name, VerifiedSeverity.HIGH, 0.85, claim.evidence_refs, "actor exceeded repeated escalation threshold", "REPEATED_ESCALATION_PATTERN")
        return _pass(self.name, 0.90, claim.evidence_refs, "memory consistency passed")


class AdversarialPressureVerifier:
    name = VerifiedInvariant.ADVERSARIAL_PRESSURE

    def verify(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog, params: CognitiveParameters) -> VerificationResult:
        del memory, catalog
        try:
            selected = evidence.require(claim.evidence_refs)
        except ValueError:
            return _unknown(self.name, VerifiedSeverity.CRITICAL, 0.0, claim.evidence_refs, "missing evidence for adversarial pressure", "MISSING_EVIDENCE_REF")
        values = [float(node.payload["adversarial_pressure"]) for node in selected if "adversarial_pressure" in node.payload]
        pressure = max(values) if values else 0.0
        if pressure > params.max_adversarial_pressure:
            return _fail(self.name, VerifiedSeverity.HIGH, 1.0 - pressure, claim.evidence_refs, "adversarial pressure exceeds threshold", "ADVERSARIAL_PRESSURE_TOO_HIGH")
        return _pass(self.name, 1.0 - pressure, claim.evidence_refs, "adversarial pressure bounded")


class VerifiedDecisionPolicy:
    def decide(self, claim: AgentClaim, results: tuple[VerificationResult, ...], params: CognitiveParameters, audit_factory: AuditFactory) -> VerifiedDecisionReport:
        quorum = self._quorum(results, params)
        all_results = (*results, quorum)
        failures = tuple(result for result in all_results if result.verdict is VerifiedVerdict.FAIL)
        unknowns = tuple(result for result in all_results if result.verdict is VerifiedVerdict.UNKNOWN)
        if failures:
            action = self._action_for_failures(failures)
            return VerifiedDecisionReport(claim.claim_id, VerifiedDecisionStatus.BLOCKED, action, False, True, all_results, audit_factory(all_results))
        if unknowns:
            action = VerifiedResolutionAction.QUARANTINE if params.fail_closed_on_unknown else VerifiedResolutionAction.REQUEST_RESYNC
            return VerifiedDecisionReport(claim.claim_id, VerifiedDecisionStatus.QUARANTINED, action, False, True, all_results, audit_factory(all_results))
        return VerifiedDecisionReport(claim.claim_id, VerifiedDecisionStatus.ALLOWED, VerifiedResolutionAction.ALLOW, True, False, all_results, audit_factory(all_results))

    def _quorum(self, results: tuple[VerificationResult, ...], params: CognitiveParameters) -> VerificationResult:
        critical = tuple(result for result in results if result.invariant in CRITICAL_INVARIANTS)
        if not critical:
            return _fail(VerifiedInvariant.CRITICAL_QUORUM, VerifiedSeverity.CRITICAL, 1.0, (), "critical invariant set is empty", "EMPTY_CRITICAL_SET")
        passing = tuple(result for result in critical if result.verdict is VerifiedVerdict.PASS and result.confidence >= params.min_critical_confidence)
        ratio = len(passing) / len(critical)
        evidence_used = tuple(eid for result in critical for eid in result.evidence_used)
        if ratio < params.min_quorum_ratio:
            return _fail(VerifiedInvariant.CRITICAL_QUORUM, VerifiedSeverity.CRITICAL, ratio, evidence_used, "critical quorum failed", "CRITICAL_QUORUM_FAILED")
        return _pass(VerifiedInvariant.CRITICAL_QUORUM, ratio, evidence_used, "critical quorum passed")

    def _action_for_failures(self, failures: tuple[VerificationResult, ...]) -> VerifiedResolutionAction:
        failed = {failure.invariant for failure in failures}
        severities = {failure.severity for failure in failures}
        if VerifiedInvariant.INNOCENCE_PROTECTION in failed:
            return VerifiedResolutionAction.HARD_BLOCK
        if VerifiedInvariant.HUMAN_VALUE_PRESERVATION in failed:
            return VerifiedResolutionAction.BOUNDARY_WITHOUT_ERASURE
        if VerifiedInvariant.PROVENANCE_INTEGRITY in failed:
            return VerifiedResolutionAction.REQUEST_RESYNC
        if VerifiedInvariant.OBSERVATION_ENTROPY_BOUND in failed:
            return VerifiedResolutionAction.REQUEST_RESYNC
        if VerifiedInvariant.PROPORTIONALITY in failed:
            return VerifiedResolutionAction.DEESCALATE
        if VerifiedInvariant.MEMORY_CONSISTENCY in failed:
            return VerifiedResolutionAction.REQUEST_RESYNC
        if VerifiedSeverity.CRITICAL in severities:
            return VerifiedResolutionAction.HARD_BLOCK
        if VerifiedSeverity.HIGH in severities:
            return VerifiedResolutionAction.QUARANTINE
        return VerifiedResolutionAction.ESCALATE_TO_HUMAN_REVIEW


class AuditFactory(Protocol):
    def __call__(self, results: tuple[VerificationResult, ...]) -> AuditRecord: ...


@dataclass(frozen=True, slots=True)
class CognitiveImmuneVerifiedCore:
    verifiers: tuple[InvariantVerifier, ...]
    policy: VerifiedDecisionPolicy
    params: CognitiveParameters

    @property
    def verifier_names(self) -> tuple[str, ...]:
        return tuple(verifier.name.value for verifier in self.verifiers)

    def evaluate(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, catalog: ActionCatalog) -> VerifiedDecisionReport:
        results = tuple(verifier.verify(claim, evidence, memory, catalog, self.params) for verifier in self.verifiers)
        return self.policy.decide(claim, results, self.params, lambda final_results: self._audit(claim, evidence, memory, final_results))

    def _audit(self, claim: AgentClaim, evidence: EvidenceGraph, memory: SystemMemory, results: tuple[VerificationResult, ...]) -> AuditRecord:
        claim_hash = _stable_hash({"claim_id": claim.claim_id, "actor": claim.actor.agent_id, "target": claim.target.agent_id, "action_id": claim.action_id, "evidence_refs": claim.evidence_refs, "created_at_utc": claim.created_at_utc})
        evidence_hash = evidence.digest()
        memory_hash = memory.digest()
        decision_hash = _stable_hash({"claim_hash": claim_hash, "evidence_hash": evidence_hash, "memory_hash": memory_hash, "results": [(result.invariant.value, result.verdict.value, result.failure_mode) for result in results], "verifiers": self.verifier_names})
        return AuditRecord(decision_hash, claim_hash, evidence_hash, memory_hash, self.verifier_names)


def _stable_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_verified_cognitive_immune_core(params: CognitiveParameters | None = None) -> CognitiveImmuneVerifiedCore:
    return CognitiveImmuneVerifiedCore(
        verifiers=(
            ProvenanceIntegrityVerifier(),
            ObservationEntropyVerifier(),
            RoleSymmetryVerifier(),
            InnocenceProtectionVerifier(),
            ProportionalityVerifier(),
            HumanValuePreservationVerifier(),
            DistalSelfConsistencyVerifier(),
            MemoryConsistencyVerifier(),
            AdversarialPressureVerifier(),
        ),
        policy=VerifiedDecisionPolicy(),
        params=params or CognitiveParameters(),
    )
