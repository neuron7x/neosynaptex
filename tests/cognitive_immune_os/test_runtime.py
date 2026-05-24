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
from cognitive_immune_os.execution_programs import ExecutionProgramId
from cognitive_immune_os.runtime import RuntimeInputs, execute_verified_claim
from cognitive_immune_os.state_model import StateStatus, VerifiedState
from cognitive_immune_os.verified_guardrail import (
    AgentClaim,
    AgentProfile,
    SystemMemory,
    build_verified_cognitive_immune_core,
)


def _node(payload: dict[str, object]) -> EvidenceNode:
    return EvidenceNode(
        node_id="e1",
        kind=EvidenceKind.SIGNED_LEDGER,
        producer_id="producer-e1",
        payload=payload,
        payload_hash=payload_hash(payload),
        confidence=0.95,
        timestamp_utc="2026-05-24T12:00:00Z",
        signature="sig:test",
    )


def _evidence() -> EvidenceGraph:
    return EvidenceGraph(
        nodes=(
            _node(
                {
                    "guilt_status": "UNKNOWN",
                    "observation_entropy": 0.1,
                    "role_symmetry_pass": True,
                    "adversarial_pressure": 0.1,
                }
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
        claim_id="claim-001",
        actor=AgentProfile(agent_id="agent-a", role="AUTHORITY"),
        target=AgentProfile(agent_id="agent-b", role="OTHER", minimum_value=1.0),
        action_id="temporary_boundary",
        claimed_reason="stabilize conflict without sacrificing invariant integrity",
        claimed_expected_utility=1.0,
        evidence_refs=("e1",),
        created_at_utc="2026-05-24T12:00:00Z",
    )


def _inputs(target_ids: tuple[str, ...] = ("s0",)) -> RuntimeInputs:
    return RuntimeInputs(
        claim=_claim(),
        evidence=_evidence(),
        memory=SystemMemory(),
        catalog=_catalog(),
        states={"s0": VerifiedState("s0", StateStatus.ACTIVE)},
        target_ids=target_ids,
    )


def test_runtime_executes_verified_claim_end_to_end() -> None:
    result = execute_verified_claim(
        core=build_verified_cognitive_immune_core(),
        inputs=_inputs(),
    )

    assert result.report.allowed is True
    assert result.program.program_id is ExecutionProgramId.APPLY_VERIFIED_ACTION
    assert result.states["s0"].status is StateStatus.ALLOWED
    assert result.changes[0].before is StateStatus.ACTIVE
    assert result.changes[0].after is StateStatus.ALLOWED
    assert result.replay_expectation.decision_hash == result.report.audit.decision_hash


def test_runtime_rejects_empty_targets_before_execution() -> None:
    with pytest.raises(ValueError, match="target_ids"):
        execute_verified_claim(
            core=build_verified_cognitive_immune_core(),
            inputs=_inputs(target_ids=()),
        )


def test_runtime_preserves_deterministic_result_for_same_inputs() -> None:
    core = build_verified_cognitive_immune_core()
    first = execute_verified_claim(core=core, inputs=_inputs())
    second = execute_verified_claim(core=core, inputs=_inputs())

    assert first.report.audit.decision_hash == second.report.audit.decision_hash
    assert first.program == second.program
    assert first.changes == second.changes
    assert first.states == second.states
