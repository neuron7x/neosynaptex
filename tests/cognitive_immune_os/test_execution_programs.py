from __future__ import annotations

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
from cognitive_immune_os.execution_programs import (
    ExecutionProgramId,
    ExecutionStepId,
    compile_execution_program,
)
from cognitive_immune_os.verified_guardrail import (
    AgentClaim,
    AgentProfile,
    SystemMemory,
    build_verified_cognitive_immune_core,
)


def _node(payload: dict[str, object], confidence: float = 0.95) -> EvidenceNode:
    return EvidenceNode(
        node_id="e1",
        kind=EvidenceKind.SIGNED_LEDGER,
        producer_id="producer-e1",
        payload=payload,
        payload_hash=payload_hash(payload),
        confidence=confidence,
        timestamp_utc="2026-05-24T12:00:00Z",
    )


def _evidence(role_symmetry: bool = True, entropy: float = 0.1) -> EvidenceGraph:
    return EvidenceGraph(
        nodes=(
            _node(
                {
                    "observation_entropy": entropy,
                    "role_symmetry_pass": role_symmetry,
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
                    utility_gain=1.0,
                    impact_risk=0.02,
                    trust_damage_risk=0.1,
                    reversibility=0.95,
                    blocking_cost=1.0,
                    error_cost=5.0,
                ),
            ),
        )
    )


def _claim() -> AgentClaim:
    return AgentClaim(
        claim_id="claim-program",
        actor=AgentProfile(agent_id="agent-a", role="SYSTEM"),
        target=AgentProfile(agent_id="agent-b", role="OTHER"),
        action_id="temporary_boundary",
        claimed_reason="program compilation test",
        claimed_expected_utility=1.0,
        evidence_refs=("e1",),
        created_at_utc="2026-05-24T12:00:00Z",
    )


def test_allowed_report_compiles_to_apply_program() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim(),
        evidence=_evidence(role_symmetry=True),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    program = compile_execution_program(report)

    assert program.program_id is ExecutionProgramId.APPLY_VERIFIED_ACTION
    assert program.terminal_step is ExecutionStepId.APPLY_ACTION
    assert program.source_decision_hash == report.audit.decision_hash


def test_failed_role_check_compiles_to_hold_program_with_role_step() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim(),
        evidence=_evidence(role_symmetry=False),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    program = compile_execution_program(report)
    steps = {step.step_id for step in program.steps}

    assert program.program_id is ExecutionProgramId.HOLD_FOR_RECHECK
    assert ExecutionStepId.REQUIRE_ROLE_CHECK in steps
    assert program.terminal_step is ExecutionStepId.PAUSE_EXECUTION


def test_missing_evidence_compiles_to_resync_program() -> None:
    report = build_verified_cognitive_immune_core().evaluate(
        claim=_claim(),
        evidence=EvidenceGraph(nodes=()),
        memory=SystemMemory(),
        catalog=_catalog(),
    )

    program = compile_execution_program(report)
    steps = {step.step_id for step in program.steps}

    assert program.program_id is ExecutionProgramId.REQUEST_STATE_RESYNC
    assert ExecutionStepId.REQUIRE_EVIDENCE in steps
