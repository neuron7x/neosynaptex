from __future__ import annotations

import asyncio
from pathlib import Path

from core.dre import ConstitutionInvariant, DREConfig, DREInput, run_dre_loop


def _event(**overrides: object) -> DREInput:
    data = {
        "model_self": (0.5, 0.5),
        "model_other": (0.5, 0.5),
        "expected_free_energy": 0.1,
        "action": "allow",
        "action_magnitude": 0.1,
        "efferent_copy": (1.0, 0.0),
        "timestamp_ns": 1,
        "state_id": 1,
        "execution_velocity": 1.0,
    }
    data.update(overrides)
    return DREInput(**data)


def test_dre_source_does_not_claim_ast_segmentation_when_gate_is_numeric() -> None:
    source = Path("core/dre.py").read_text(encoding="utf-8")
    assert "AST-segregation" not in source
    assert "_ast_segmentation_mask" not in source


def test_ktb_records_accepted_events_not_only_failures() -> None:
    decisions, state = asyncio.run(
        run_dre_loop(
            [_event(timestamp_ns=1), _event(timestamp_ns=2)],
            config=DREConfig(),
            invariant=ConstitutionInvariant(("allow",), 1.0),
        )
    )
    assert [decision.accepted for decision in decisions] == [True, True]
    assert len(state.ktb) == 2
    assert [row.accepted for row in state.ktb] == [True, True]
    assert [row.decision_reason for row in state.ktb] == ["accepted", "accepted"]
    assert all(0.0 <= float(row.overlap_score) <= 1.0 for row in state.ktb)


def test_phase_transition_is_not_triggered_by_single_old_failure() -> None:
    events = [_event(timestamp_ns=1, efferent_copy=(0.0, 0.0))]
    events.extend(_event(timestamp_ns=i + 2) for i in range(6))
    _, state = asyncio.run(
        run_dre_loop(
            events,
            config=DREConfig(phase_transition_days=7),
            invariant=ConstitutionInvariant(("allow",), 1.0),
        )
    )
    assert state.phase_transition_triggered is False


def test_phase_transition_uses_configured_failure_ratio_window() -> None:
    events = [
        _event(timestamp_ns=1, efferent_copy=(0.0, 0.0)),
        _event(timestamp_ns=2, efferent_copy=(0.0, 0.0)),
        _event(timestamp_ns=3),
        _event(timestamp_ns=4),
    ]
    _, state = asyncio.run(
        run_dre_loop(
            events,
            config=DREConfig(phase_transition_days=4, phase_failure_ratio_threshold=0.5),
            invariant=ConstitutionInvariant(("allow",), 1.0),
        )
    )
    assert state.phase_transition_triggered is True
