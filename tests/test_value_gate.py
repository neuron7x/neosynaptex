from __future__ import annotations

import math

import pytest

from core.value_gate import ValueGateConfig, ValueGateInput, evaluate_value_gate


def test_accepts_when_score_above_threshold_and_counterfactual() -> None:
    out = evaluate_value_gate(
        ValueGateInput(
            utility=2.0, risk=0.4, uncertainty=0.2, kl_drift=0.1, counterfactual_score=0.5
        ),
        ValueGateConfig(min_value_score=1.0),
    )
    assert out.accepted is True


def test_blocks_on_value_threshold() -> None:
    out = evaluate_value_gate(
        ValueGateInput(
            utility=0.0,
            risk=0.4,
            uncertainty=0.2,
            kl_drift=0.1,
            counterfactual_score=-1.0,
        ),
        ValueGateConfig(min_value_score=0.0),
    )
    assert out.accepted is False
    assert out.reason == "blocked:value_below_threshold"


def test_blocks_on_counterfactual() -> None:
    out = evaluate_value_gate(
        ValueGateInput(
            utility=1.0,
            risk=0.0,
            uncertainty=0.0,
            kl_drift=0.0,
            counterfactual_score=1.1,
        ),
        ValueGateConfig(min_value_score=0.0),
    )
    assert out.accepted is False
    assert out.reason == "blocked:counterfactual_better"


def test_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError):
        evaluate_value_gate(
            ValueGateInput(
                utility=1.0,
                risk=-0.1,
                uncertainty=0.0,
                kl_drift=0.0,
                counterfactual_score=0.0,
            ),
            ValueGateConfig(),
        )


@pytest.mark.parametrize(
    ("inp", "cfg"),
    [
        (
            ValueGateInput(
                utility=math.nan,
                risk=0.0,
                uncertainty=0.0,
                kl_drift=0.0,
                counterfactual_score=0.0,
            ),
            ValueGateConfig(),
        ),
        (
            ValueGateInput(
                utility=1.0,
                risk=math.inf,
                uncertainty=0.0,
                kl_drift=0.0,
                counterfactual_score=0.0,
            ),
            ValueGateConfig(),
        ),
        (
            ValueGateInput(
                utility=1.0,
                risk=0.0,
                uncertainty=0.0,
                kl_drift=0.0,
                counterfactual_score=math.nan,
            ),
            ValueGateConfig(),
        ),
        (
            ValueGateInput(
                utility=1.0,
                risk=0.0,
                uncertainty=0.0,
                kl_drift=0.0,
                counterfactual_score=0.0,
            ),
            ValueGateConfig(lambda_risk=math.inf),
        ),
    ],
)
def test_rejects_non_finite_inputs(inp: ValueGateInput, cfg: ValueGateConfig) -> None:
    with pytest.raises(ValueError, match="finite"):
        evaluate_value_gate(inp, cfg)
