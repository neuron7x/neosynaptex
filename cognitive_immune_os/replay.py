from __future__ import annotations

from dataclasses import dataclass

from cognitive_immune_os.action_catalog import ActionCatalog
from cognitive_immune_os.evidence_graph import EvidenceGraph
from cognitive_immune_os.verified_guardrail import (
    AgentClaim,
    CognitiveImmuneVerifiedCore,
    SystemMemory,
    VerifiedDecisionReport,
)


@dataclass(frozen=True, slots=True)
class ReplayExpectation:
    claim_hash: str
    evidence_graph_hash: str
    memory_hash: str
    decision_hash: str | None = None


class ReplayMismatchError(ValueError):
    pass


def replay_verified_decision(
    core: CognitiveImmuneVerifiedCore,
    claim: AgentClaim,
    evidence: EvidenceGraph,
    memory: SystemMemory,
    catalog: ActionCatalog,
    expected: ReplayExpectation,
) -> VerifiedDecisionReport:
    report = core.evaluate(claim=claim, evidence=evidence, memory=memory, catalog=catalog)

    mismatches: list[str] = []
    if report.audit.claim_hash != expected.claim_hash:
        mismatches.append("claim_hash")
    if report.audit.evidence_graph_hash != expected.evidence_graph_hash:
        mismatches.append("evidence_graph_hash")
    if report.audit.memory_hash != expected.memory_hash:
        mismatches.append("memory_hash")
    if expected.decision_hash is not None and report.audit.decision_hash != expected.decision_hash:
        mismatches.append("decision_hash")

    if mismatches:
        joined = ", ".join(mismatches)
        raise ReplayMismatchError(f"verified replay mismatch: {joined}")

    return report
