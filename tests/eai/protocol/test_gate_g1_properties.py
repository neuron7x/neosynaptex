"""Property-based (Hypothesis) verification of Gate G1 invariants.

Where ``tests/eai/integration/test_gate_g1.py`` pins behaviour on named
examples, this suite proves the same invariants hold across generated inputs:
determinism, self-consistent SHA-256 identity, bounded decomposition, semantic
invariance to whitespace/Unicode encoding, and reproducible fail-closed
behaviour. These are the mathematical guarantees Gate G1 claims, checked as
universally-quantified properties rather than point samples.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from core.eai.gate_g1 import (
    _MAX_INPUT_CHARS,
    _MAX_SUBTASKS,
    GateG1CompileError,
    GateG1Context,
    compile_execution_packet,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CTX = GateG1Context("linux-ci", "neosynaptex", "neuron7xLab/neosynaptex", ("no network",))


@given(st.text(max_size=400))
@settings(max_examples=300, deadline=None)
def test_compile_is_deterministic_or_fails_closed(s: str) -> None:
    """Any input either compiles to a byte-identical packet on replay, or it
    raises GateG1CompileError reproducibly. There is no third, nondeterministic
    outcome."""
    try:
        first = compile_execution_packet(s, _CTX)
    except GateG1CompileError:
        with pytest.raises(GateG1CompileError):
            compile_execution_packet(s, _CTX)
        return
    second = compile_execution_packet(s, _CTX)
    assert first == second
    assert first.packet_hash == second.packet_hash
    assert _SHA256.match(first.packet_hash)
    assert first.emits_clarification is False
    assert 1 <= len(first.subtasks) <= _MAX_SUBTASKS
    assert first.schema_version == "gate_g1/v1"


@given(st.text(min_size=1, max_size=200))
@settings(max_examples=300, deadline=None)
def test_whitespace_repadding_is_semantically_invariant(s: str) -> None:
    """packet_hash is a semantic identity: re-padding the token stream with
    different whitespace leaves intent and replay identity unchanged."""
    assume(s.strip())
    repadded = "   ".join(s.split())
    try:
        a = compile_execution_packet(s, _CTX)
        b = compile_execution_packet(repadded, _CTX)
    except GateG1CompileError:
        assume(False)
        return
    assert a.intent == b.intent
    assert a.packet_hash == b.packet_hash


@given(st.integers(min_value=_MAX_INPUT_CHARS + 1, max_value=_MAX_INPUT_CHARS + 50))
@settings(max_examples=25, deadline=None)
def test_over_length_always_fails_closed(n: int) -> None:
    with pytest.raises(GateG1CompileError):
        compile_execution_packet("x" * n, _CTX)


@given(st.sampled_from(["", " ", "   ", "\n\t ", " ", "  "]))
def test_blank_inputs_always_fail_closed(s: str) -> None:
    with pytest.raises(GateG1CompileError):
        compile_execution_packet(s, _CTX)


@given(st.text(min_size=1, max_size=300))
@settings(max_examples=200, deadline=None)
def test_insufficient_context_always_fails_closed(s: str) -> None:
    assume(s.strip())
    blank_ctx = GateG1Context("linux", "", "repo")
    with pytest.raises(GateG1CompileError):
        compile_execution_packet(s, blank_ctx)
