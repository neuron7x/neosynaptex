from __future__ import annotations

import pytest

from core.event_bus import EventBus
from core.truth_guard import TruthGuardConfig, evaluate_truth_guard


def test_activates_only_on_drift_and_low_confidence_and_emits_event() -> None:
    bus = EventBus()
    out = evaluate_truth_guard(
        baseline=0.2,
        observed=0.5,
        confidence=0.4,
        config=TruthGuardConfig(drift_threshold=0.2, min_confidence=0.6),
        event_bus=bus,
    )
    assert out.activated is True
    assert out.reason == "dynamic_environment_drifted_truth"
    events = bus.replay()
    assert len(events) == 1
    assert events[0].domain == "architecture.truth_alert"


def test_stays_off_when_stable() -> None:
    out = evaluate_truth_guard(baseline=0.5, observed=0.55, confidence=0.8)
    assert out.activated is False
    assert out.reason == "stable"


def test_decision_matches_contract_grid() -> None:
    cfg = TruthGuardConfig(drift_threshold=0.3, min_confidence=0.4)
    values = [0.0, 0.2, 0.4, 0.7, 1.0]
    for baseline in values:
        for observed in values:
            for confidence in values:
                out = evaluate_truth_guard(
                    baseline=baseline,
                    observed=observed,
                    confidence=confidence,
                    config=cfg,
                )
                expected = (
                    abs(observed - baseline) >= cfg.drift_threshold
                    and confidence < cfg.min_confidence
                )
                assert out.activated is expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"baseline": -0.1, "observed": 0.1, "confidence": 0.1},
        {"baseline": 0.1, "observed": 1.1, "confidence": 0.1},
        {"baseline": 0.1, "observed": 0.1, "confidence": 2.0},
    ],
)
def test_rejects_out_of_range_inputs(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        evaluate_truth_guard(**kwargs)


def test_rejects_invalid_config() -> None:
    with pytest.raises(ValueError):
        evaluate_truth_guard(
            baseline=0.1,
            observed=0.2,
            confidence=0.3,
            config=TruthGuardConfig(alert_domain=""),
        )
