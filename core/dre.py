"""Deterministic Reflex Engine with calibrated behavioral telemetry."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import NamedTuple, cast

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "BehavioralStateVector",
    "ConstitutionInvariant",
    "DREConfig",
    "DREDecision",
    "DREInput",
    "DREState",
    "compute_forcing_vector",
    "kl_divergence",
    "run_dre_loop",
]

_EPS = 1e-12
_DIM = 7
_SHAPE = (_DIM, _DIM)
_U32 = np.iinfo(np.uint32).max
_U64 = np.iinfo(np.uint64).max
FloatArray = NDArray[np.float64]


class BehavioralStateVector(NamedTuple):
    timestamp_ns: np.uint64
    state_id: np.uint32
    friction_coefficient: np.float32
    trajectory_jacobian: FloatArray
    execution_velocity: np.float32
    accepted: bool
    decision_reason: str
    overlap_score: np.float32


@dataclass(frozen=True)
class DREConfig:
    kl_threshold: float = 0.25
    risk_threshold_tau: float = 0.2
    friction_gain: float = 0.1
    overlap_threshold: float = 1e-9
    phase_transition_days: int = 7
    phase_failure_ratio_threshold: float = 1.0
    max_ktb_events: int = 1024


@dataclass(frozen=True)
class ConstitutionInvariant:
    allowed_actions: tuple[str, ...]
    max_action_magnitude: float


@dataclass(frozen=True)
class DREInput:
    model_self: tuple[float, ...]
    model_other: tuple[float, ...]
    expected_free_energy: float
    action: str
    action_magnitude: float
    efferent_copy: tuple[float, ...]
    timestamp_ns: int
    state_id: int
    execution_velocity: float


@dataclass(frozen=True)
class DREDecision:
    accepted: bool
    reason: str
    kl_value: float
    friction: float
    quarantine_external: bool


@dataclass(frozen=True)
class DREState:
    day_index: int
    ktb: tuple[BehavioralStateVector, ...]
    phase_transition_triggered: bool


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _non_negative(name: str, value: float) -> None:
    _finite(name, value)
    if value < 0.0:
        raise ValueError(f"{name} must be >= 0")


def _unit(name: str, value: float) -> None:
    _finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")


def _distribution(name: str, values: Sequence[float]) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError(f"{name} must be a non-empty 1D vector")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    if np.any(arr < 0.0):
        raise ValueError("model distributions must be non-negative")
    total = float(np.sum(arr))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError(f"{name} must have positive finite mass")
    return cast(FloatArray, arr / total)


def _validate_config(cfg: DREConfig) -> None:
    _non_negative("config.kl_threshold", cfg.kl_threshold)
    _non_negative("config.risk_threshold_tau", cfg.risk_threshold_tau)
    _non_negative("config.friction_gain", cfg.friction_gain)
    _unit("config.overlap_threshold", cfg.overlap_threshold)
    _unit("config.phase_failure_ratio_threshold", cfg.phase_failure_ratio_threshold)
    if cfg.phase_transition_days < 1:
        raise ValueError("phase_transition_days must be >= 1")
    if cfg.max_ktb_events < 1:
        raise ValueError("max_ktb_events must be >= 1")


def _validate_input(inp: DREInput) -> None:
    _non_negative("expected_free_energy", inp.expected_free_energy)
    _non_negative("action_magnitude", inp.action_magnitude)
    _finite("execution_velocity", inp.execution_velocity)
    if not 0 <= inp.timestamp_ns <= _U64:
        raise ValueError("timestamp_ns must fit uint64 without wraparound")
    if not 0 <= inp.state_id <= _U32:
        raise ValueError("state_id must fit uint32 without wraparound")


def kl_divergence(model_other: Sequence[float], model_self: Sequence[float]) -> float:
    q = _distribution("model_other", model_other)
    p = _distribution("model_self", model_self)
    if q.size != p.size:
        raise ValueError("model vectors must have equal length")
    value = float(np.sum(q * (np.log(q + _EPS) - np.log(p + _EPS))))
    if not math.isfinite(value):
        raise ValueError("kl_divergence result must be finite")
    return value


def _constitution_ok(action: str, magnitude: float, inv: ConstitutionInvariant) -> bool:
    _non_negative("invariant.max_action_magnitude", inv.max_action_magnitude)
    return action in inv.allowed_actions and 0.0 <= magnitude <= inv.max_action_magnitude


def _overlap_score(model_other: Sequence[float], efferent_copy: Sequence[float]) -> float:
    ext = np.asarray(model_other, dtype=np.float64)
    eff = np.asarray(efferent_copy, dtype=np.float64)
    if ext.ndim != 1 or eff.ndim != 1:
        raise ValueError("model_other and efferent_copy must be 1D vectors")
    if ext.shape != eff.shape:
        raise ValueError("efferent_copy shape must match model_other shape")
    if not np.all(np.isfinite(ext)) or not np.all(np.isfinite(eff)):
        raise ValueError("model_other and efferent_copy must contain only finite values")
    denom = float(np.linalg.norm(ext) * np.linalg.norm(eff))
    if denom <= _EPS:
        return 0.0
    score = float(np.sum(np.abs(ext * eff)) / (denom + _EPS))
    if not math.isfinite(score):
        raise ValueError("external overlap score must be finite")
    return min(1.0, max(0.0, score))


def _feature(value: float) -> float:
    _finite("feature", value)
    return math.tanh(value)


def _behavior_vector(
    inp: DREInput,
    decision: DREDecision,
    overlap: float,
) -> BehavioralStateVector:
    _validate_input(inp)
    _unit("overlap_score", overlap)
    features = np.asarray(
        [
            _feature(decision.kl_value),
            min(1.0, decision.friction),
            min(1.0, inp.expected_free_energy),
            _feature(inp.action_magnitude),
            _feature(inp.execution_velocity),
            overlap,
            1.0 if decision.accepted else 0.0,
        ],
        dtype=np.float64,
    )
    if features.shape != (_DIM,) or not np.all(np.isfinite(features)):
        raise ValueError("behavior features must be finite 7D vectors")
    jac = cast(FloatArray, np.outer(features, features))
    return BehavioralStateVector(
        np.uint64(inp.timestamp_ns),
        np.uint32(inp.state_id),
        np.float32(decision.friction),
        jac,
        np.float32(inp.execution_velocity),
        decision.accepted,
        decision.reason,
        np.float32(overlap),
    )


def _decision(
    accepted: bool,
    reason: str,
    kl_value: float,
    friction: float,
    quarantine_external: bool,
) -> DREDecision:
    return DREDecision(accepted, reason, kl_value, friction, quarantine_external)


def _evaluate_atom(
    inp: DREInput,
    cfg: DREConfig,
    inv: ConstitutionInvariant,
) -> tuple[DREDecision, float]:
    _validate_input(inp)
    kl_value = kl_divergence(inp.model_other, inp.model_self)
    friction = min(1.0, cfg.friction_gain * (1.0 + kl_value))
    overlap = _overlap_score(inp.model_other, inp.efferent_copy)
    if overlap <= cfg.overlap_threshold:
        return _decision(False, "blocked:quarantine_external", kl_value, friction, True), overlap
    if kl_value > cfg.kl_threshold:
        return _decision(False, "blocked:input_kl_drift", kl_value, friction, False), overlap
    if inp.expected_free_energy >= cfg.risk_threshold_tau:
        reason = "blocked:fail_closed_risk_gate"
        return _decision(False, reason, kl_value, friction, False), overlap
    if not _constitution_ok(inp.action, inp.action_magnitude, inv):
        return _decision(False, "blocked:dlpfc_invariant", kl_value, friction, False), overlap
    return _decision(True, "accepted", kl_value, friction, False), overlap


def _push_ktb(
    ktb: list[BehavioralStateVector],
    event: BehavioralStateVector,
    max_events: int,
) -> None:
    if max_events < 1:
        raise ValueError("max_ktb_events must be >= 1")
    if len(ktb) >= max_events:
        ktb.pop(0)
    ktb.append(event)


def compute_forcing_vector(ktb: Sequence[BehavioralStateVector]) -> FloatArray:
    """Compute a bounded behavioral forcing proxy from KTB jacobians."""
    if not ktb:
        return np.zeros(_SHAPE[0], dtype=np.float64)
    mats = np.stack([row.trajectory_jacobian.astype(np.float64) for row in ktb], axis=0)
    if mats.shape[1:] != _SHAPE:
        raise ValueError(f"trajectory_jacobian must have shape {_SHAPE}")
    if not np.all(np.isfinite(mats)):
        raise ValueError("trajectory_jacobian must contain only finite values")
    u, s, _ = np.linalg.svd(np.mean(mats, axis=0), full_matrices=False)
    if not np.all(np.isfinite(s)):
        raise ValueError("singular values must be finite")
    if float(s[0]) <= _EPS:
        return np.zeros(_SHAPE[0], dtype=np.float64)
    return cast(FloatArray, (u[:, 0] * min(1.0, float(s[0]))).astype(np.float64))


def _phase_transition(ktb: Sequence[BehavioralStateVector], cfg: DREConfig) -> bool:
    if len(ktb) < cfg.phase_transition_days:
        return False
    window = ktb[-cfg.phase_transition_days :]
    failure_ratio = sum(not row.accepted for row in window) / len(window)
    return failure_ratio >= cfg.phase_failure_ratio_threshold


async def run_dre_loop(
    stream: Iterable[DREInput],
    *,
    config: DREConfig,
    invariant: ConstitutionInvariant,
    start_day_index: int = 0,
) -> tuple[list[DREDecision], DREState]:
    _validate_config(config)
    if start_day_index < 0:
        raise ValueError("start_day_index must be >= 0")
    decisions: list[DREDecision] = []
    ktb: list[BehavioralStateVector] = []
    day_index = start_day_index
    for item in stream:
        day_index += 1
        decision, overlap = _evaluate_atom(item, config, invariant)
        decisions.append(decision)
        _push_ktb(ktb, _behavior_vector(item, decision, overlap), config.max_ktb_events)
    state = DREState(day_index, tuple(ktb), _phase_transition(ktb, config))
    return decisions, state
