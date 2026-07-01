"""Deterministic contract tests for Cognitive Compiler Gate G1.

Gate G1 is the ingress layer that compiles raw Variant A input into a
Variant B ``ExecutionPacket`` that seeds the existing EAI runtime. These tests
pin the hard invariants: fail-closed behaviour, replay stability, no
clarification, bounded decomposition, immutability and honest hand-off to
``EAIEngine``.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from core.eai.engine import EAIEngine
from core.eai.gate_g1 import (
    ExecutionPacket,
    GateG1CompileError,
    GateG1Context,
    compile_execution_packet,
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _context() -> GateG1Context:
    return GateG1Context(
        environment="linux-ci",
        project="neosynaptex",
        repository="neuron7xLab/neosynaptex",
        constraints=("no network", "deterministic only"),
    )


def _compile(raw: str) -> ExecutionPacket:
    return compile_execution_packet(raw, _context())


def test_chaotic_input_compiles_to_bounded_units() -> None:
    packet = _compile("fix the thing; also the OTHER thing... and maybe check logs")
    assert len(packet.subtasks) >= 1
    assert _SHA256_HEX.match(packet.packet_hash)
    # sub-task ids are stable, ordered and unique
    ids = [st.subtask_id for st in packet.subtasks]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_empty_input_fails_closed() -> None:
    with pytest.raises(GateG1CompileError):
        _compile("")


def test_whitespace_only_input_fails_closed() -> None:
    with pytest.raises(GateG1CompileError):
        _compile("   \n\t  ")


def test_missing_context_fails_closed() -> None:
    with pytest.raises(GateG1CompileError):
        compile_execution_packet(
            "do the work",
            GateG1Context(environment="linux", project="", repository="repo"),
        )


def test_emotional_input_still_compiles_without_clarification() -> None:
    packet = _compile("i'm exhausted and everything is broken JUST MAKE IT WORK")
    assert packet.emits_clarification is False
    assert "no_clarification_questions_emitted" in packet.validation_gates
    assert len(packet.subtasks) >= 1


def test_stable_replay_identical_hash() -> None:
    raw = "compile ingress; route to engine; verify replay"
    a = _compile(raw)
    b = _compile(raw)
    assert a == b
    assert a.packet_hash == b.packet_hash


def test_distinct_input_distinct_hash() -> None:
    a = _compile("alpha task")
    b = _compile("beta task")
    assert a.packet_hash != b.packet_hash


def test_normalized_intent_collapses_whitespace() -> None:
    # the compiled intent is whitespace-normalized...
    assert _compile("a  b").intent == _compile("a b").intent == "a b"


def test_raw_provenance_distinguishes_whitespace() -> None:
    # ...but raw_input_hash preserves the exact original bytes, so the audit
    # identity (packet_hash) still distinguishes them. Provenance is exact.
    assert _compile("a  b").raw_input_hash != _compile("a b").raw_input_hash
    assert _compile("a  b").packet_hash != _compile("a b").packet_hash


def test_punctuation_only_input_yields_one_unit() -> None:
    # non-empty but structurally empty after segmentation -> single fallback unit
    packet = _compile("!!! ??? ...")
    assert len(packet.subtasks) == 1


def test_claim_boundary_is_preserved() -> None:
    packet = _compile("run the pipeline")
    assert "No scientific or consciousness claims." in packet.error_state.failure_boundary
    assert "claim_boundary_preserved" in packet.validation_gates


def test_packet_is_frozen() -> None:
    packet = _compile("immutable please")
    with pytest.raises(dataclasses.FrozenInstanceError):
        packet.intent = "mutated"  # type: ignore[misc]


def test_context_and_raw_hashes_are_sha256() -> None:
    packet = _compile("hash me")
    assert _SHA256_HEX.match(packet.context_hash)
    assert _SHA256_HEX.match(packet.raw_input_hash)


def test_seed_reproducibility_hash_is_valid_sha256() -> None:
    packet = _compile("seed the runtime")
    manifest = packet.to_reproducibility(environment="linux-ci")
    assert _SHA256_HEX.match(manifest.artifact_hash)
    assert manifest.artifact_hash == packet.packet_hash


def test_honest_handoff_to_eai_engine_is_deterministic() -> None:
    packet = _compile("harden the ingress boundary and re-run the gate")
    engine = EAIEngine()

    def _run() -> str:
        outcome = engine.run_candidate(
            claim=packet.to_claim_card(),
            boundary=packet.to_boundary_card(),
            contradiction_markers=[],
            reproducibility=packet.to_reproducibility(environment="linux-ci"),
            retention_hash=packet.retention_hash(),
            revalidation_passed=True,
            integration_patch={"guardrail_update": True},
            next_intent_delta={"delta": 1},
        )
        return outcome.status.value

    # ingress -> runtime is wired and the runtime decision is reproducible
    assert _run() == _run()
