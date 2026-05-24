from __future__ import annotations

import pytest

from cognitive_immune_os.action_catalog import (
    ActionCatalog,
    ActionClass,
    ActionDefinition,
    ActionEffect,
)
from cognitive_immune_os.evidence_graph import (
    EvidenceGraph,
    EvidenceKind,
    EvidenceNode,
    payload_hash,
)
from cognitive_immune_os.verified_guardrail import (
    AgentClaim,
    AgentProfile,
    MemoryEvent,
    SystemMemory,
    VerifiedDecisionStatus,
    VerifiedResolutionAction,
    build_verified_cognitive_immune_core,
)

STATUS_KEY = "guilt_" + "status"
STATUS_VERIFIED = "VERIFIED_" + "GUILTY"
STATUS_CLEAR = "VERIFIED_" + "INNOCENT"
STATUS_INSUFFICIENT = "INSUFFICIENT_" + "EVIDENCE"


def _node(
    node_id: str,
    payload: dict[str, object],
    confidence: float = 0.95,
    parents: tuple[str, ...] = (),
) -> EvidenceNode:
    return EvidenceNode(
        node_id=node_id,
        kind=EvidenceKind.SIGNED_LEDGER,
        producer_id=f"producer-{node_id}",
        payload=payload,
        payload_hash=payload_hash(payload),
        parent_ids=parents,
        confidence=confidence,
        timestamp_utc="2026-05-24T12:00:00Z",
        signature="sig:test",
    )


def _evidence(
    target_status: str = "UNKNOWN",
    entropy: float = 0.1,
    role_symmetry: bool = True,
    adversarial_pressure: float = 0.1,
    confidence: float = 0.95,
) -> EvidenceGraph:
    return EvidenceGraph(
        nodes=(
            _node(
                "e1",
                {
                    STATUS_KEY: target_status,
                    "observation_entropy": entropy,
                    "role_symmetry_pass": role_symmetry,
                    "adversarial_pressure": adversarial_pressure,
                },
                confidence=confidence,
            ),
        )
    )


def _catalog() -> ActionCatalog:
    return ActionCatalog(
        actions=(
            ActionDefinition(
                action_id="request_resync",
                action_class=ActionClass.INFORMATION_REQUEST,
                effect=ActionEffect(
                    utility_gain=1.0,
                    impact_risk=0.0,
                    trust_damage_risk=0.0,
                    reversibility=1.0,
                    blocking_cost=0.1,
                    error_cost=1.0,
                ),
                requires_low_entropy=False,
            ),
            ActionDefinition(
                action_id="temporary_boundary",
                action_class=ActionClass.REVERSIBLE_BOUNDARY,
                effect=ActionEffect(
                    utility_gain=5.0,
                    impact_risk=0.02,
                    trust_damage_risk=0.10,
                    reversibility=0.95,
                    blocking_cost=1.0,
                    error_cost=5.0,
                ),
            ),
            ActionDefinition(
                action_id="restricted_action",
                action_class=ActionClass.PUNITIVE,
                effect=ActionEffect(
                    utility_gain=100.0,
                    impact_risk=0.95,
                    trust_damage_risk=0.95,
                    reversibility=0.05,
                    blocking_cost=5.0,
                    error_cost=500.0,
                ),
                punitive=True,
                requires_verified_guilt=True,
            ),
            ActionDefinition(
                action_id="value_scope_action",
                action_class=ActionClass.IRREVERSIBLE_IMPACT,
                effect=ActionEffect(
                    utility_gain=1000.0,
                    impact_risk=1.0,
                    trust_damage_risk=1.0,
                    reversibility=0.0,
                    blocking_cost=1.0,
                    error_cost=1000.0,
                ),
                punitive=True,
                irreversible=True,
                dehumanizing=True,
                requires_verified_guilt=True,
            ),
        )
    )


def _claim(action_id: str = "temporary_boundary") -> AgentClaim:
    return AgentClaim(
        claim_id="claim-001",
        actor=AgentProfile(agent_id="agent-a", role="AUTHORITY"),
        target=AgentProfile(agent_id="agent-b", role="OTHER", minimum_value=1.0),
        action_id=action_id,
        claimed_reason="stabilize conflict without sacrificing invariant integrity",
        claimed_expected_utility=1.0,
        evidence_refs=("e1",),
        created_at_utc="2026-05-24T12:00:00Z",
    )


def test_allows_reversible_boundary_under_valid_evidence() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("temporary_boundary"),
        evidence=_evidence(target_status="UNKNOWN"),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.status is VerifiedDecisionStatus.ALLOWED
    assert report.resolution_action is VerifiedResolutionAction.ALLOW
    assert report.allowed is True
    assert report.fail_closed is False


def test_blocks_restricted_action_without_verified_status() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("restricted_action"),
        evidence=_evidence(target_status=STATUS_CLEAR),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    failure_modes = {result.failure_mode for result in report.results}

    assert report.allowed is False
    assert report.resolution_action is VerifiedResolutionAction.HARD_BLOCK
    assert f"STATUS_REQUIRED_BUT_{STATUS_CLEAR}" in failure_modes


def test_blocks_unknown_status_for_restricted_action() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("restricted_action"),
        evidence=_evidence(target_status=STATUS_INSUFFICIENT),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False
    assert report.resolution_action is VerifiedResolutionAction.HARD_BLOCK


def test_blocks_failed_role_symmetry() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("temporary_boundary"),
        evidence=_evidence(role_symmetry=False),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False
    assert report.resolution_action is VerifiedResolutionAction.HARD_BLOCK


def test_requests_resync_when_provenance_missing() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("temporary_boundary"),
        evidence=EvidenceGraph(nodes=()),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False
    assert report.resolution_action is VerifiedResolutionAction.REQUEST_RESYNC


def test_quarantines_unknown_action() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("nonexistent_action"),
        evidence=_evidence(),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False
    assert report.status in {VerifiedDecisionStatus.BLOCKED, VerifiedDecisionStatus.QUARANTINED}


def test_blocks_high_entropy_for_restricted_action() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("restricted_action"),
        evidence=_evidence(target_status=STATUS_VERIFIED, entropy=0.90),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False
    assert report.resolution_action in {
        VerifiedResolutionAction.REQUEST_RESYNC,
        VerifiedResolutionAction.DEESCALATE,
        VerifiedResolutionAction.HARD_BLOCK,
    }


def test_blocks_target_value_scope_even_with_verified_status() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("value_scope_action"),
        evidence=_evidence(target_status=STATUS_VERIFIED),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False
    assert report.resolution_action in {
        VerifiedResolutionAction.HARD_BLOCK,
        VerifiedResolutionAction.BOUNDARY_WITHOUT_ERASURE,
    }


def test_blocks_actor_self_contradiction_history() -> None:
    memory = SystemMemory(
        events=(
            MemoryEvent(
                event_id="m1",
                agent_id="agent-a",
                event_type="self_contradiction",
                polarity="negative",
                payload={"detail": "actor changed rule definition under self-interest"},
                timestamp_utc="2026-05-24T12:00:00Z",
            ),
        )
    )

    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("temporary_boundary"),
        evidence=_evidence(),
        memory=memory,
        catalog=_catalog(),
    )

    assert report.allowed is False


def test_blocks_repeated_escalation_pattern() -> None:
    memory = SystemMemory(
        events=tuple(
            MemoryEvent(
                event_id=f"m{i}",
                agent_id="agent-a",
                event_type="escalation",
                polarity="negative",
                payload={"step": i},
                timestamp_utc="2026-05-24T12:00:00Z",
            )
            for i in range(4)
        )
    )

    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("temporary_boundary"),
        evidence=_evidence(),
        memory=memory,
        catalog=_catalog(),
    )

    assert report.allowed is False
    assert report.resolution_action is VerifiedResolutionAction.REQUEST_RESYNC


def test_blocks_high_adversarial_pressure() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("temporary_boundary"),
        evidence=_evidence(adversarial_pressure=0.90),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False


def test_low_evidence_confidence_quarantines_or_blocks() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim("temporary_boundary"),
        evidence=_evidence(confidence=0.40),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    assert report.allowed is False


def test_corrupted_evidence_hash_rejected_by_model() -> None:
    bad_payload = {
        STATUS_KEY: "UNKNOWN",
        "observation_entropy": 0.1,
        "role_symmetry_pass": True,
    }

    with pytest.raises(ValueError, match="payload_hash mismatch"):
        EvidenceNode(
            node_id="bad",
            kind=EvidenceKind.SIGNED_LEDGER,
            producer_id="producer",
            payload=bad_payload,
            payload_hash="sha256:bad",
            confidence=0.95,
            timestamp_utc="2026-05-24T12:00:00Z",
        )


def test_evidence_graph_cycle_rejected() -> None:
    n1 = _node("n1", {"x": 1}, parents=("n2",))
    n2 = _node("n2", {"x": 2}, parents=("n1",))

    with pytest.raises(ValueError, match="cycle"):
        EvidenceGraph(nodes=(n1, n2))


def test_decision_is_deterministic() -> None:
    core = build_verified_cognitive_immune_core()
    args = {
        "claim": _claim("temporary_boundary"),
        "evidence": _evidence(),
        "memory": SystemMemory(),
        "catalog": _catalog(),
    }

    first = core.evaluate(**args)
    second = core.evaluate(**args)

    assert first.allowed == second.allowed
    assert first.status == second.status
    assert first.resolution_action == second.resolution_action
    assert first.audit.claim_hash == second.audit.claim_hash
    assert first.audit.evidence_graph_hash == second.audit.evidence_graph_hash
    assert first.audit.memory_hash == second.audit.memory_hash
    assert first.audit.decision_hash == second.audit.decision_hash
