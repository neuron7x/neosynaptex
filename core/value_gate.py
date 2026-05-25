"""Unified value gate for deterministic action selection."""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["ValueGateConfig", "ValueGateInput", "ValueGateDecision", "evaluate_value_gate"]


@dataclass(frozen=True)
class ValueGateConfig:
    lambda_risk: float = 1.0
    lambda_uncertainty: float = 1.0
    lambda_drift: float = 1.0
    min_value_score: float = 0.0


@dataclass(frozen=True)
class ValueGateInput:
    utility: float
    risk: float
    uncertainty: float
    kl_drift: float
    counterfactual_score: float


@dataclass(frozen=True)
class ValueGateDecision:
    accepted: bool
    score: float
    reason: str


def _check_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _check_non_negative(name: str, value: float) -> None:
    _check_finite(name, value)
    if value < 0.0:
        raise ValueError(f"{name} must be >= 0")


def evaluate_value_gate(inp: ValueGateInput, cfg: ValueGateConfig) -> ValueGateDecision:
    _check_finite("utility", inp.utility)
    _check_non_negative("risk", inp.risk)
    _check_non_negative("uncertainty", inp.uncertainty)
    _check_non_negative("kl_drift", inp.kl_drift)
    _check_finite("counterfactual_score", inp.counterfactual_score)
    _check_non_negative("lambda_risk", cfg.lambda_risk)
    _check_non_negative("lambda_uncertainty", cfg.lambda_uncertainty)
    _check_non_negative("lambda_drift", cfg.lambda_drift)
    _check_finite("min_value_score", cfg.min_value_score)

    score = (
        inp.utility
        - cfg.lambda_risk * inp.risk
        - cfg.lambda_uncertainty * inp.uncertainty
        - cfg.lambda_drift * inp.kl_drift
    )
    if not math.isfinite(score):
        raise ValueError("score must be finite")
    if score < cfg.min_value_score:
        return ValueGateDecision(False, score, "blocked:value_below_threshold")
    if score < inp.counterfactual_score:
        return ValueGateDecision(False, score, "blocked:counterfactual_better")
    return ValueGateDecision(True, score, "accepted")
