from __future__ import annotations

import asyncio

import pytest

from core.dre import ConstitutionInvariant, DREConfig, DREInput
from core.dre_runtime import run_integrated_cycle, run_integrated_cycle_async
from core.event_bus import EventBus
from core.value_gate import ValueGateInput


def _event() -> DREInput:
    return DREInput(
        model_self=(0.5, 0.5),
        model_other=(0.5, 0.5),
        expected_free_energy=0.1,
        action="allow",
        action_magnitude=0.1,
        efferent_copy=(1.0, 0.0),
        timestamp_ns=1,
        state_id=1,
        execution_velocity=1.0,
    )


def _value() -> ValueGateInput:
    return ValueGateInput(
        utility=2.0,
        risk=0.1,
        uncertainty=0.1,
        kl_drift=0.0,
        counterfactual_score=0.5,
    )


def test_truth_guard_pause_returns_no_dre_decisions() -> None:
    bus = EventBus()
    out = run_integrated_cycle(
        baseline=0.0,
        observed=0.8,
        confidence=0.2,
        dre_events=(_event(),),
        dre_config=DREConfig(),
        invariant=ConstitutionInvariant(("allow",), 1.0),
        event_bus=bus,
        value_gate_input=_value(),
    )
    assert out.truth_guard.activated is True
    assert out.dre_decisions == ()
    assert out.value_gate.reason == "blocked:truth_guard"
    assert out.deliberation.accepted is False
    assert out.dre_state.day_index == 0
    assert len(bus.replay()) == 1


def test_missing_value_input_returns_no_dre_decisions() -> None:
    out = run_integrated_cycle(
        baseline=0.4,
        observed=0.45,
        confidence=0.9,
        dre_events=(_event(),),
        dre_config=DREConfig(),
        invariant=ConstitutionInvariant(("allow",), 1.0),
    )
    assert out.truth_guard.activated is False
    assert out.value_gate.accepted is False
    assert out.value_gate.reason == "blocked:missing_value_gate_input"
    assert out.dre_decisions == ()
    assert out.deliberation.accepted is False


def test_integrated_cycle_runs_dre_with_explicit_value_input() -> None:
    out = run_integrated_cycle(
        baseline=0.4,
        observed=0.45,
        confidence=0.9,
        dre_events=(_event(),),
        dre_config=DREConfig(),
        invariant=ConstitutionInvariant(("allow",), 1.0),
        value_gate_input=_value(),
    )
    assert out.truth_guard.activated is False
    assert len(out.dre_decisions) == 1
    assert out.dre_decisions[0].accepted is True
    assert out.dre_state.day_index == 1
    assert out.deliberation.accepted is True


def test_integrated_cycle_async_runs_inside_existing_event_loop() -> None:
    async def _run() -> None:
        out = await run_integrated_cycle_async(
            baseline=0.4,
            observed=0.45,
            confidence=0.9,
            dre_events=(_event(),),
            dre_config=DREConfig(),
            invariant=ConstitutionInvariant(("allow",), 1.0),
            value_gate_input=_value(),
        )
        assert out.truth_guard.activated is False
        assert len(out.dre_decisions) == 1
        assert out.deliberation.accepted is True

    asyncio.run(_run())


def test_sync_integrated_cycle_raises_inside_existing_event_loop() -> None:
    async def _run() -> None:
        with pytest.raises(RuntimeError, match="active event loop"):
            run_integrated_cycle(
                baseline=0.4,
                observed=0.45,
                confidence=0.9,
                dre_events=(_event(),),
                dre_config=DREConfig(),
                invariant=ConstitutionInvariant(("allow",), 1.0),
                value_gate_input=_value(),
            )

    asyncio.run(_run())


def test_value_gate_rejection_returns_no_dre_decisions() -> None:
    out = run_integrated_cycle(
        baseline=0.4,
        observed=0.45,
        confidence=0.9,
        dre_events=(_event(),),
        dre_config=DREConfig(),
        invariant=ConstitutionInvariant(("allow",), 1.0),
        value_gate_input=ValueGateInput(
            utility=0.0,
            risk=1.0,
            uncertainty=1.0,
            kl_drift=1.0,
            counterfactual_score=0.0,
        ),
    )
    assert out.truth_guard.activated is False
    assert out.value_gate.accepted is False
    assert out.dre_decisions == ()
    assert out.deliberation.accepted is False
