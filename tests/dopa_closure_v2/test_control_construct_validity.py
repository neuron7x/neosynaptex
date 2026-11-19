"""Falsification tests for degenerate/invalid priority-only controls."""

from __future__ import annotations

import math

import pytest

from core.eai.dopa_controls import run_controls
from core.eai.dopa_types import ClaimSignal


def _claim(claim_id: str, risk: float = 0.3) -> ClaimSignal:
    return ClaimSignal(claim_id, 0.6, 0.6, 0.6, risk, 0.7, 0.55)


def test_shuffling_priority_cannot_change_mean_or_establish_validity() -> None:
    claims = [_claim(str(i)) for i in range(5)]
    priorities = [0.1, 0.5, 0.9, 0.25, 0.75]
    result = run_controls(claims, priorities, seed=731)
    assert math.isclose(
        result.permutation_break_mean_priority,
        sum(priorities) / len(priorities),
        rel_tol=1e-14,
    )
    assert result.passed is False
    assert result.validity == "UNTESTED"
    assert result.reason == "priority_means_cannot_validate_verification_benefit"


def test_permuting_claim_association_is_invisible_to_mean() -> None:
    claims = [_claim("low"), _claim("high")]
    a = run_controls(claims, [0.01, 0.99], seed=731)
    b = run_controls(claims, [0.99, 0.01], seed=731)
    assert a.permutation_break_mean_priority == b.permutation_break_mean_priority
    assert a.passed is False and b.passed is False


def test_proxy_mean_superiority_does_not_promote_a_pass() -> None:
    claims = [_claim(str(i), risk=0.0) for i in range(4)]
    result = run_controls(claims, [100.0] * 4, seed=42)
    # Arbitrarily large priorities have no direct evidence semantics.
    assert result.passed is False
    assert result.validity == "UNTESTED"


def test_empty_controls_are_not_positive_evidence() -> None:
    result = run_controls([], [], seed=731)
    assert result.passed is False
    assert result.validity == "UNTESTED"


@pytest.mark.parametrize(
    "priorities",
    [
        [],
        [float("nan"), 0.2],
        [float("inf"), 0.2],
        [-0.1, 0.2],
        [True, 0.2],
    ],
)
def test_invalid_controls_fail_closed(priorities: list[float]) -> None:
    with pytest.raises(ValueError):
        run_controls([_claim("a"), _claim("b")], priorities, seed=42)
