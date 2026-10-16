"""Fail-closed audit of the exact first-step dopamine TD expression.

A first-step zero-reward value estimate is a randomly initialized state feature,
not calibrated reward prediction error or verified claim utility.
"""
from __future__ import annotations
import math


def expected_first_step_valence(
    current_value: float, *, discount: float = 0.99,
    reward: float = 0.0, previous_value: float = 0.0,
) -> float:
    """Mirror delta=r+gamma*V(s)-V(previous), then clamp to [-1,1]."""
    values = (current_value, discount, reward, previous_value)
    if any(isinstance(x, bool) or not isinstance(x, (float, int))
           or not math.isfinite(x) for x in values):
        raise ValueError("nonfinite_or_nonnumeric_td_operand")
    if not (0.0 <= discount <= 1.0):
        raise ValueError("invalid_temporal_discount")
    return max(-1.0, min(1.0, reward + discount * current_value - previous_value))


def assert_one_step_zero_reward_construct(
    *, current_value: float, observed_valence: float,
    discount: float, previous_value: float, reward: float,
    atol: float = 2e-6,
) -> None:
    """Exact pilot premise and numerical reconstruction; fail on any drift."""
    if reward != 0.0 or previous_value != 0.0:
        raise ValueError("pilot_requires_zero_reward_and_new_value_state")
    if not math.isclose(discount, 0.99, abs_tol=1e-6, rel_tol=0.0):
        raise ValueError("pilot_discount_not_default_0_99")
    if isinstance(observed_valence, bool) or not isinstance(observed_valence, (float, int)) or not math.isfinite(observed_valence):
        raise ValueError("invalid_observed_valence")
    expected = expected_first_step_valence(
        current_value, discount=discount, reward=reward,
        previous_value=previous_value,
    )
    if not math.isclose(observed_valence, expected, abs_tol=atol, rel_tol=0.0):
        raise ValueError("first_step_valence_identity_violated")
