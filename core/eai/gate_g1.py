from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final

from core.claim_classifier import classify_claim_type
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    ReproducibilityManifest,
)

# ---------------------------------------------------------------------------
# Cognitive Compiler Gate G1 — deterministic ingress layer for the EAI stack.
#
# Gate G1 sits *before* the existing verified runtime (falsification engine ->
# IEV gate -> artifact ledger -> integration memory, orchestrated by
# ``core.eai.engine.EAIEngine``). Its single responsibility is to compile raw,
# chaotic, fatigued or out-of-distribution human input into a deterministic
# ``ExecutionPacket`` that seeds the structured inputs the runtime already
# expects (a ``ClaimCard`` candidate, a ``BoundaryCard``, a
# ``ReproducibilityManifest`` and a retention hash).
#
# Gate G1 makes NO scientific or consciousness claims and NEVER asks the user
# clarifying questions. It performs the engineering transition Variant A
# (unstructured signal) -> Variant B (bounded, testable work units). It is a
# *compiler*, not an oracle: whether the seeded claim survives is decided
# downstream by the falsification and IEV gates, not here.
#
# Hard invariants (enforced by tests/eai/integration/test_gate_g1.py):
#   * no randomness, no wall-clock dependence, no network calls;
#   * no hidden mutable state — every dataclass is frozen;
#   * same (raw_input, context) always yields the same ``packet_hash``;
#   * empty input or insufficient context fails closed (raises), it never
#     silently guesses;
#   * any non-empty input under sufficient context compiles into >= 1 bounded
#     work unit;
#   * the gate never emits a clarification request (``emits_clarification`` is
#     always ``False``).
# ---------------------------------------------------------------------------


class GateG1CompileError(ValueError):
    """Raised when raw input or context cannot be compiled.

    Gate G1 fails closed: rather than fabricate intent from an empty signal or
    an under-specified context, it refuses. This keeps the downstream runtime
    from ingesting an unprovenanced packet.
    """


@dataclass(frozen=True)
class GateG1Context:
    """Known, structured context surrounding a raw ingress signal.

    All three of ``environment``, ``project`` and ``repository`` are required;
    ``constraints`` is an ordered, immutable tuple of explicit boundaries.
    """

    environment: str
    project: str
    repository: str
    constraints: tuple[str, ...] = ()

    def is_sufficient(self) -> bool:
        return bool(self.environment.strip() and self.project.strip() and self.repository.strip())


@dataclass(frozen=True)
class ErrorState:
    """Explicit before/after framing plus the safety boundary of the work."""

    current_state: str
    expected_state: str
    failure_boundary: str
    inputs: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    success_condition: str


@dataclass(frozen=True)
class SubTask:
    """One bounded, individually testable unit of work."""

    subtask_id: str
    description: str
    order: int


@dataclass(frozen=True)
class AgentRoute:
    """A named agent role and the mandate it is responsible for."""

    role: str
    mandate: str


@dataclass(frozen=True)
class ExecutionPacket:
    """Deterministic Variant B compilation of a raw ingress signal.

    The packet is a *candidate* for the existing runtime. ``to_claim_card`` /
    ``to_boundary_card`` / ``to_reproducibility`` / ``retention_hash`` expose it
    in the exact shape ``core.eai.engine.EAIEngine.run_candidate`` consumes; the
    engine's falsification and IEV gates remain the sole promotion authority.
    """

    intent: str
    claim_type: ClaimType
    error_state: ErrorState
    subtasks: tuple[SubTask, ...]
    agent_routes: tuple[AgentRoute, ...]
    execution_order: tuple[str, ...]
    validation_gates: tuple[str, ...]
    expected_artifacts: tuple[str, ...]
    raw_input_hash: str
    context_hash: str
    packet_hash: str
    emits_clarification: bool = False

    def to_claim_card(self) -> ClaimCard:
        """Seed the runtime's ClaimCard from the compiled intent."""
        return ClaimCard(
            claim_id=f"CLM-{self.packet_hash[:16]}",
            claim_text=self.intent,
            claim_type=self.claim_type,
            assumptions=list(self.error_state.inputs),
            expected_observations=[self.error_state.expected_state],
            failure_conditions=[self.error_state.failure_boundary],
        )

    def to_boundary_card(self) -> BoundaryCard:
        """Seed a BoundaryCard scoping the packet to ingress, never to a live
        state change (Gate G1 compiles; it does not mutate state)."""
        valid_for = ["ingress_compilation"]
        return BoundaryCard(
            boundary_id=f"BND-{self.packet_hash[:16]}",
            valid_for=valid_for,
            invalid_for=["state_change", "scientific_claim"],
            tested_conditions=list(valid_for),
            untested_conditions=["state_change"],
        )

    def to_reproducibility(self, *, environment: str) -> ReproducibilityManifest:
        """Seed a ReproducibilityManifest. ``packet_hash`` is a valid SHA-256
        hex digest, so it doubles as the reproducible artifact hash."""
        return ReproducibilityManifest(
            commands=list(self.execution_order),
            environment=environment,
            artifact_hash=self.packet_hash,
        )

    def retention_hash(self) -> str:
        """The retention hash the runtime expects — the packet's own digest."""
        return self.packet_hash


# --- canonical, deterministic vocabulary -----------------------------------

_AGENT_ROUTES: Final[tuple[AgentRoute, ...]] = (
    AgentRoute("Planner", "derive objective and execution order"),
    AgentRoute("Executor", "map sub-tasks to concrete repository actions"),
    AgentRoute("Critic", "detect ambiguity, scope creep and unsafe claims"),
    AgentRoute("Verifier", "enforce deterministic schema and replay hash"),
    AgentRoute("EvidenceKeeper", "preserve raw input, context hash and packet hash"),
    AgentRoute("FinalSynthesizer", "produce the final verdict contract"),
)

_EXECUTION_ORDER: Final[tuple[str, ...]] = (
    "compile_error_state",
    "decompose_subtasks",
    "assign_agent_routes",
    "bind_replay_identity",
    "hand_off_to_eai_engine",
)

_VALIDATION_GATES: Final[tuple[str, ...]] = (
    "no_clarification_questions_emitted",
    "no_randomness",
    "no_wall_clock_dependency",
    "frozen_dataclasses",
    "stable_packet_hash",
    "deterministic_output_ordering",
    "fail_closed_on_empty_or_invalid_context",
    "claim_boundary_preserved",
)

_MISSING_EVIDENCE: Final[tuple[str, ...]] = (
    "no_falsification_report",
    "no_boundary_validation",
    "no_reproducibility_run",
)

_FAILURE_BOUNDARY: Final[str] = (
    "No scientific or consciousness claims. Do not replace the existing verified "
    "runtime. No network calls, randomness, wall-clock dependence or hidden "
    "mutable state."
)

_CURRENT_STATE: Final[str] = "raw ingress signal, unstructured Variant A input"

_EXPECTED_STATE: Final[str] = (
    "structured Variant B execution packet: intent, error state, bounded "
    "sub-tasks, agent routes, validation gates and expected artifacts"
)

_SUCCESS_CONDITION: Final[str] = (
    "same raw input and context always produce the same ExecutionPacket; "
    "chaotic or malformed input still compiles into bounded, testable work units"
)

# Split on sentence terminators, semicolons and newlines. Purely structural and
# deterministic — no natural-language model, no heuristics that could vary.
_SEGMENT_SPLIT: Final[re.Pattern[str]] = re.compile(r"[.\n;!?]+")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(raw_input: str) -> str:
    """Collapse all whitespace runs to single spaces; preserve case."""
    return " ".join(raw_input.split())


def _decompose(normalized: str) -> tuple[SubTask, ...]:
    """Split a normalized signal into ordered, de-duplicated bounded units.

    Order of first appearance is preserved (deterministic). If no segment
    survives (e.g. punctuation-only input), the whole normalized signal becomes
    a single work unit so the packet always carries >= 1 testable task.
    """
    seen: set[str] = set()
    segments: list[str] = []
    for chunk in _SEGMENT_SPLIT.split(normalized):
        piece = chunk.strip()
        if piece and piece not in seen:
            seen.add(piece)
            segments.append(piece)
    if not segments:
        segments = [normalized]
    return tuple(
        SubTask(subtask_id=f"ST-{index:06d}", description=piece, order=index)
        for index, piece in enumerate(segments, start=1)
    )


def _canonical_payload(
    *,
    intent: str,
    claim_type: ClaimType,
    error_state: ErrorState,
    subtasks: tuple[SubTask, ...],
    raw_input_hash: str,
    context_hash: str,
) -> str:
    """Stable JSON serialization used as the pre-image of ``packet_hash``.

    ``sort_keys`` makes the digest independent of dict insertion order; the
    canonical agent routes, execution order and validation gates are fixed
    constants and therefore need not enter the pre-image.
    """
    payload = {
        "intent": intent,
        "claim_type": claim_type.value,
        "error_state": {
            "current_state": error_state.current_state,
            "expected_state": error_state.expected_state,
            "failure_boundary": error_state.failure_boundary,
            "inputs": list(error_state.inputs),
            "missing_evidence": list(error_state.missing_evidence),
            "success_condition": error_state.success_condition,
        },
        "subtasks": [[st.subtask_id, st.description, st.order] for st in subtasks],
        "raw_input_hash": raw_input_hash,
        "context_hash": context_hash,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compile_execution_packet(raw_input: str, context: GateG1Context) -> ExecutionPacket:
    """Compile a raw ingress signal into a deterministic ``ExecutionPacket``.

    Fails closed (``GateG1CompileError``) on empty input or insufficient
    context. Never asks a clarifying question. Same ``(raw_input, context)``
    always yields the same packet.
    """
    if not raw_input or not raw_input.strip():
        raise GateG1CompileError(
            "empty raw input: Gate G1 fails closed rather than guessing intent"
        )
    if not context.is_sufficient():
        raise GateG1CompileError(
            "insufficient context: environment, project and repository are all required"
        )

    normalized = _normalize(raw_input)
    claim_type = classify_claim_type(normalized)
    subtasks = _decompose(normalized)

    inputs = (context.environment, context.project, context.repository, *context.constraints)
    error_state = ErrorState(
        current_state=_CURRENT_STATE,
        expected_state=_EXPECTED_STATE,
        failure_boundary=_FAILURE_BOUNDARY,
        inputs=inputs,
        missing_evidence=_MISSING_EVIDENCE,
        success_condition=_SUCCESS_CONDITION,
    )

    raw_input_hash = _sha256(raw_input)
    context_hash = _sha256(
        json.dumps(
            {
                "environment": context.environment,
                "project": context.project,
                "repository": context.repository,
                "constraints": list(context.constraints),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    packet_hash = _sha256(
        _canonical_payload(
            intent=normalized,
            claim_type=claim_type,
            error_state=error_state,
            subtasks=subtasks,
            raw_input_hash=raw_input_hash,
            context_hash=context_hash,
        )
    )

    expected_artifacts = tuple(f"work_unit/{st.subtask_id}" for st in subtasks)

    return ExecutionPacket(
        intent=normalized,
        claim_type=claim_type,
        error_state=error_state,
        subtasks=subtasks,
        agent_routes=_AGENT_ROUTES,
        execution_order=_EXECUTION_ORDER,
        validation_gates=_VALIDATION_GATES,
        expected_artifacts=expected_artifacts,
        raw_input_hash=raw_input_hash,
        context_hash=context_hash,
        packet_hash=packet_hash,
    )
