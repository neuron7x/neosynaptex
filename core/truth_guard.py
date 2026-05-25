"""Minimal fail-closed truth-drift gate."""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.event_bus import AnomalyEvent, EventBus

__all__ = ["TruthGuardConfig", "TruthGuardDecision", "evaluate_truth_guard"]


@dataclass(frozen=True)
class TruthGuardConfig:
    drift_threshold: float = 0.2
    min_confidence: float = 0.6
    hard_drift_threshold: float = 1.0
    alert_domain: str = "architecture.truth_alert"


@dataclass(frozen=True)
class TruthGuardDecision:
    activated: bool
    drift: float
    reason: str


def evaluate_truth_guard(
    *,
    baseline: float,
    observed: float,
    confidence: float,
    config: TruthGuardConfig | None = None,
    event_bus: EventBus | None = None,
) -> TruthGuardDecision:
    config = config or TruthGuardConfig()

    _check_unit("baseline", baseline)
    _check_unit("observed", observed)
    _check_unit("confidence", confidence)
    _check_unit("config.drift_threshold", config.drift_threshold)
    _check_unit("config.min_confidence", config.min_confidence)
    _check_unit("config.hard_drift_threshold", config.hard_drift_threshold)
    if config.hard_drift_threshold < config.drift_threshold:
        raise ValueError("config.hard_drift_threshold must be >= config.drift_threshold")
    if not config.alert_domain:
        raise ValueError("config.alert_domain must be non-empty")

    drift = abs(observed - baseline)
    hard_drift = drift > config.hard_drift_threshold
    low_confidence_drift = drift >= config.drift_threshold and confidence < config.min_confidence
    activated = hard_drift or low_confidence_drift

    if activated:
        if event_bus is not None:
            event_bus.emit(
                AnomalyEvent(
                    domain=config.alert_domain,
                    metric="truth_drift",
                    value=drift,
                    threshold=config.drift_threshold,
                )
            )
        if hard_drift:
            return TruthGuardDecision(True, drift, "hard_drift_requires_revalidation")
        return TruthGuardDecision(True, drift, "dynamic_environment_drifted_truth")

    if drift >= config.drift_threshold:
        return TruthGuardDecision(False, drift, "drift_but_confidence_ok")
    if confidence < config.min_confidence:
        return TruthGuardDecision(False, drift, "confidence_low_but_drift_small")
    return TruthGuardDecision(False, drift, "stable")


def _check_unit(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be in [0, 1], got {value}")
