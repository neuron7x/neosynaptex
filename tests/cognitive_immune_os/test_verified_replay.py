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
from cognitive_immune_os.replay import (
    ReplayExpectation,
    ReplayMismatchError,
    replay_verified_decision,
)
from cognitive_immune_os.verified_guardrail import (
    AgentClaim,
    AgentProfile,
    SystemMemory,
    build_verified_cognitive_immune_core,
)


def _evidence() -> EvidenceGraph:
    payload = {
        "observation_entropy": 0.1,
        "role_symmetry_pass": True,
        "adversarial_pressure": 0.1,
    }
    return EvidenceGraph(
        nodes=(
            EvidenceNode(
                node_id="e1",
                kind=EvidenceKind.SIGNED_LEDGER,
                producer_id="producer-e1",
                payload=payload,
                payload_hash=payload_hash(payload),
                confidence=0.95,
                timestamp_utc="2026-05-24T12:00:00Z",
            ),
        )
    )


def _catalog() -> ActionCatalog:
    return ActionCatalog(
        actions=(
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
        )
    )


def _claim() -> AgentClaim:
    return AgentClaim(
        claim_id="claim-replay",
        actor=AgentProfile(agent_id="agent-a", role="SYSTEM"),
        target=AgentProfile(agent_id="agent-b", role="OTHER", minimum_value=1.0),
        action_id="temporary_boundary",
        claimed_reason="bounded replay case",
        claimed_expected_utility=1.0,
        evidence_refs=("e1",),
        created_at_utc="2026-05-24T12:00:00Z",
    )


def test_replay_accepts_matching_audit_hashes() -> None:
    core = build_verified_cognitive_immune_core()
    claim = _claim()
    evidence = _evidence()
    memory = SystemMemory()
    catalog = _catalog()

    first = core.evaluate(claim=claim, evidence=evidence, memory=memory, catalog=catalog)
    expected = ReplayExpectation(
        claim_hash=first.audit.claim_hash,
        evidence_graph_hash=first.audit.evidence_graph_hash,
        memory_hash=first.audit.memory_hash,
        decision_hash=first.audit.decision_hash,
    )

    replayed = replay_verified_decision(core, claim, evidence, memory, catalog, expected)

    assert replayed.audit.decision_hash == first.audit.decision_hash
    assert replayed.allowed == first.allowed


def test_replay_reports_changed_decision_hash() -> None:
    core = build_verified_cognitive_immune_core()
    claim = _claim()
    evidence = _evidence()
    memory = SystemMemory()
    catalog = _catalog()

    first = core.evaluate(claim=claim, evidence=evidence, memory=memory, catalog=catalog)
    expected = ReplayExpectation(
        claim_hash=first.audit.claim_hash,
        evidence_graph_hash=first.audit.evidence_graph_hash,
        memory_hash=first.audit.memory_hash,
        decision_hash="sha256:0000",
    )

    with pytest.raises(ReplayMismatchError, match="decision_hash"):
        replay_verified_decision(core, claim, evidence, memory, catalog, expected)
