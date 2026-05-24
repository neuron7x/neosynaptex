from __future__ import annotations

from dataclasses import dataclass

from cognitive_immune_os.action_catalog import ActionCatalog
from cognitive_immune_os.evidence_graph import EvidenceGraph
from cognitive_immune_os.execution_programs import ExecutionProgram, compile_execution_program
from cognitive_immune_os.execution_state_executor import execute_program_transitions
from cognitive_immune_os.replay import ReplayExpectation, replay_verified_decision
from cognitive_immune_os.state_model import StateChange, VerifiedState
from cognitive_immune_os.verified_guardrail import (
    AgentClaim,
    CognitiveImmuneVerifiedCore,
    SystemMemory,
    VerifiedDecisionReport,
)


@dataclass(frozen=True, slots=True)
class RuntimeInputs:
    claim: AgentClaim
    evidence: EvidenceGraph
    memory: SystemMemory
    catalog: ActionCatalog
    states: dict[str, VerifiedState]
    target_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeExecutionResult:
    report: VerifiedDecisionReport
    replay_expectation: ReplayExpectation
    program: ExecutionProgram
    states: dict[str, VerifiedState]
    changes: tuple[StateChange, ...]


def replay_expectation_from_report(report: VerifiedDecisionReport) -> ReplayExpectation:
    return ReplayExpectation(
        claim_hash=report.audit.claim_hash,
        evidence_graph_hash=report.audit.evidence_graph_hash,
        memory_hash=report.audit.memory_hash,
        decision_hash=report.audit.decision_hash,
    )


def execute_verified_claim(
    core: CognitiveImmuneVerifiedCore,
    inputs: RuntimeInputs,
) -> RuntimeExecutionResult:
    if not inputs.target_ids:
        raise ValueError("target_ids must be non-empty")

    report = core.evaluate(
        claim=inputs.claim,
        evidence=inputs.evidence,
        memory=inputs.memory,
        catalog=inputs.catalog,
    )
    expectation = replay_expectation_from_report(report)

    replay_verified_decision(
        core=core,
        claim=inputs.claim,
        evidence=inputs.evidence,
        memory=inputs.memory,
        catalog=inputs.catalog,
        expected=expectation,
    )

    program = compile_execution_program(report)
    states, changes = execute_program_transitions(
        program=program,
        states=inputs.states,
        target_ids=inputs.target_ids,
    )

    return RuntimeExecutionResult(
        report=report,
        replay_expectation=expectation,
        program=program,
        states=states,
        changes=changes,
    )
