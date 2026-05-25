from __future__ import annotations

from core.deliberation import DeliberationConfig, build_deliberation_trace
from core.dre import DREDecision
from core.truth_guard import TruthGuardDecision
from core.value_gate import ValueGateDecision


def test_deliberation_accepts_when_all_validators_pass() -> None:
    trace = build_deliberation_trace(
        truth_guard=TruthGuardDecision(False, 0.0, "stable"),
        value_gate=ValueGateDecision(True, 1.0, "accepted"),
        dre_decisions=(DREDecision(True, "accepted", 0.0, 0.0, False),),
    )
    assert trace.accepted is True
    assert len(trace.steps) == 3


def test_deliberation_blocks_when_value_gate_fails() -> None:
    trace = build_deliberation_trace(
        truth_guard=TruthGuardDecision(False, 0.0, "stable"),
        value_gate=ValueGateDecision(False, -1.0, "blocked:value_below_threshold"),
        dre_decisions=(),
    )
    assert trace.accepted is False
    assert trace.steps[1].passed is False


def test_deliberation_respects_step_bound() -> None:
    trace = build_deliberation_trace(
        truth_guard=TruthGuardDecision(False, 0.0, "stable"),
        value_gate=ValueGateDecision(True, 1.0, "accepted"),
        dre_decisions=(DREDecision(True, "accepted", 0.0, 0.0, False),),
        config=DeliberationConfig(max_steps=2),
    )
    assert len(trace.steps) == 2


def test_deliberation_acceptance_uses_full_validator_set_when_trace_is_truncated() -> None:
    trace = build_deliberation_trace(
        truth_guard=TruthGuardDecision(False, 0.0, "stable"),
        value_gate=ValueGateDecision(True, 1.0, "accepted"),
        dre_decisions=(DREDecision(False, "blocked:input_kl_drift", 1.0, 0.2, False),),
        config=DeliberationConfig(max_steps=1),
    )
    assert len(trace.steps) == 1
    assert trace.steps[0].name == "dre"
    assert trace.steps[0].passed is False
    assert trace.accepted is False


def test_deliberation_truncated_trace_keeps_first_failure_visible() -> None:
    trace = build_deliberation_trace(
        truth_guard=TruthGuardDecision(False, 0.0, "stable"),
        value_gate=ValueGateDecision(False, -1.0, "blocked:value_below_threshold"),
        dre_decisions=(DREDecision(False, "blocked:input_kl_drift", 1.0, 0.2, False),),
        config=DeliberationConfig(max_steps=2),
    )
    assert [step.name for step in trace.steps] == ["truth_guard", "value_gate"]
    assert trace.steps[-1].passed is False
    assert trace.accepted is False
