from __future__ import annotations

import asyncio
import math

import numpy as np
import pytest

from core.dre import (
    ConstitutionInvariant,
    DREConfig,
    DREInput,
    compute_forcing_vector,
    kl_divergence,
    run_dre_loop,
)


def _inp(**overrides: object) -> DREInput:
    base = dict(
        model_self=(0.5, 0.5),
        model_other=(0.5, 0.5),
        expected_free_energy=0.1,
        action="allow",
        action_magnitude=0.1,
        efferent_copy=(1.0, 0.0),
        timestamp_ns=1,
        state_id=7,
        execution_velocity=2.0,
    )
    base.update(overrides)
    return DREInput(**base)


def test_kl_divergence_zero_on_equal_distributions() -> None:
    assert kl_divergence((0.5, 0.5), (0.5, 0.5)) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize(
    ("model_other", "model_self"),
    [
        ((math.nan, 1.0), (0.5, 0.5)),
        ((math.inf, 1.0), (0.5, 0.5)),
        ((0.0, 0.0), (0.5, 0.5)),
        ((0.5, 0.5), (0.0, 0.0)),
    ],
)
def test_kl_divergence_rejects_non_finite_or_zero_mass_vectors(
    model_other: tuple[float, ...], model_self: tuple[float, ...]
) -> None:
    with pytest.raises(ValueError):
        kl_divergence(model_other, model_self)


def test_quarantine_external_when_mask_is_zero() -> None:
    cfg = DREConfig()
    inv = ConstitutionInvariant(("allow",), 1.0)
    events = [_inp(efferent_copy=(0.0, 0.0), model_other=(0.3, 0.7))]
    out, state = asyncio.run(run_dre_loop(events, config=cfg, invariant=inv))
    assert out[0].reason == "blocked:quarantine_external"
    assert out[0].quarantine_external is True
    assert len(state.ktb) == 1


def test_ktb_rejects_string_logs_by_type_contract() -> None:
    cfg = DREConfig(max_ktb_events=2)
    inv = ConstitutionInvariant(("allow",), 1.0)
    events = [
        _inp(efferent_copy=(0.0, 0.0), timestamp_ns=10),
        _inp(efferent_copy=(0.0, 0.0), timestamp_ns=11),
        _inp(efferent_copy=(0.0, 0.0), timestamp_ns=12),
    ]
    _, state = asyncio.run(run_dre_loop(events, config=cfg, invariant=inv))
    assert len(state.ktb) == 2
    assert all(hasattr(row, "trajectory_jacobian") for row in state.ktb)


def test_day7_phase_transition_triggered() -> None:
    cfg = DREConfig(phase_transition_days=7, max_ktb_events=16)
    inv = ConstitutionInvariant(("allow",), 1.0)
    events = [_inp(efferent_copy=(0.0, 0.0), timestamp_ns=i + 1) for i in range(7)]
    _, state = asyncio.run(run_dre_loop(events, config=cfg, invariant=inv))
    assert state.phase_transition_triggered is True
    assert state.day_index == 7


def test_compute_forcing_vector_shape_and_finite() -> None:
    cfg = DREConfig(max_ktb_events=8)
    inv = ConstitutionInvariant(("allow",), 1.0)
    events = [_inp(efferent_copy=(0.0, 0.0), timestamp_ns=i + 1) for i in range(3)]
    _, state = asyncio.run(run_dre_loop(events, config=cfg, invariant=inv))
    f_env = compute_forcing_vector(state.ktb)
    assert f_env.shape == (7,)
    assert np.all(np.isfinite(f_env))


def test_fail_closed_risk_gate() -> None:
    cfg = DREConfig(risk_threshold_tau=0.2)
    inv = ConstitutionInvariant(("allow",), 1.0)
    out, _ = asyncio.run(run_dre_loop([_inp(expected_free_energy=0.2)], config=cfg, invariant=inv))
    assert out[0].reason == "blocked:fail_closed_risk_gate"


@pytest.mark.parametrize(
    "bad_event",
    [
        _inp(timestamp_ns=-1),
        _inp(state_id=-1),
        _inp(expected_free_energy=math.nan),
        _inp(action_magnitude=math.inf),
        _inp(execution_velocity=math.nan),
        _inp(efferent_copy=(math.nan, 0.0)),
    ],
)
def test_run_dre_loop_rejects_non_finite_or_unsigned_wrap_inputs(bad_event: DREInput) -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            run_dre_loop(
                [bad_event],
                config=DREConfig(),
                invariant=ConstitutionInvariant(("allow",), 1.0),
            )
        )


def test_run_dre_loop_rejects_invalid_config() -> None:
    with pytest.raises(ValueError, match="friction_gain"):
        asyncio.run(
            run_dre_loop(
                [_inp()],
                config=DREConfig(friction_gain=math.nan),
                invariant=ConstitutionInvariant(("allow",), 1.0),
            )
        )
