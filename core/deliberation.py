"""Deterministic runtime deliberation with self-validation trace."""

from __future__ import annotations

from dataclasses import dataclass

from core.dre import DREDecision
from core.truth_guard import TruthGuardDecision
from core.value_gate import ValueGateDecision

__all__ = [
    "DeliberationConfig",
    "DeliberationStep",
    "DeliberationTrace",
    "build_deliberation_trace",
]


@dataclass(frozen=True)
class DeliberationConfig:
    max_steps: int = 3


@dataclass(frozen=True)
class DeliberationStep:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class DeliberationTrace:
    accepted: bool
    steps: tuple[DeliberationStep, ...]


def _bounded_trace_steps(
    steps: list[DeliberationStep],
    *,
    max_steps: int,
    accepted: bool,
) -> tuple[DeliberationStep, ...]:
    bounded = steps[:max_steps]
    if accepted or any(not step.passed for step in bounded):
        return tuple(bounded)

    first_failure = next((step for step in steps if not step.passed), None)
    if first_failure is None:
        return tuple(bounded)
    if max_steps == 1:
        return (first_failure,)
    return tuple([*bounded[:-1], first_failure])


def build_deliberation_trace(
    *,
    truth_guard: TruthGuardDecision,
    value_gate: ValueGateDecision,
    dre_decisions: tuple[DREDecision, ...],
    config: DeliberationConfig | None = None,
) -> DeliberationTrace:
    """Build deterministic decision trace from gate outcomes.

    ``accepted`` is computed from the full validator set. The emitted trace is
    bounded by ``max_steps``, but a failing validator is preserved inside the
    bounded trace so log-size controls cannot hide the failure path.
    """
    cfg = config or DeliberationConfig()
    if cfg.max_steps < 1:
        raise ValueError("max_steps must be >= 1")

    steps: list[DeliberationStep] = []

    tg_pass = not truth_guard.activated
    steps.append(DeliberationStep("truth_guard", tg_pass, truth_guard.reason))

    vg_pass = value_gate.accepted
    steps.append(DeliberationStep("value_gate", vg_pass, value_gate.reason))

    dre_pass = bool(dre_decisions) and all(d.accepted for d in dre_decisions)
    dre_reason = "accepted" if dre_pass else "blocked:dre_gate"
    steps.append(DeliberationStep("dre", dre_pass, dre_reason))

    accepted = all(step.passed for step in steps)
    bounded = _bounded_trace_steps(steps, max_steps=cfg.max_steps, accepted=accepted)
    return DeliberationTrace(accepted=accepted, steps=bounded)
