"""Defect-sensitive contracts for the DNCA/DOPA routing-only integration."""
from __future__ import annotations

import math

import pytest

from core.eai.dnca_modulated_router import (
    DNCAObservation,
    EvidenceInput,
    observe_sps,
    route_live_dnca,
    route_observation,
)
from core.eai.dopa_construct_gate import ConstructContext
from core.eai.dopa_result import Err, Ok

CONFIG = "configs/dopa_closure_v2/allocator.yaml"
ADMISSIBLE = ConstructContext(True, True, False, False, True, True)
BLOCKED = ConstructContext(False, True, False, False, True, True)


def _obs(*, valence: float = 0.5, inhibition: float = 0.1) -> DNCAObservation:
    return DNCAObservation(0.7, valence, 0.5, inhibition, 3)


def _claims(n: int = 1) -> list[EvidenceInput]:
    return [
        EvidenceInput(f"claim-{i}", 0.6, 0.7, 0.1, 0.8, 0.55)
        for i in range(n)
    ]


def _success(result: object) -> dict:
    assert isinstance(result, Ok), result
    return result.value


def test_modulation_is_sign_sensitive_and_budget_matched() -> None:
    neutral = _success(route_observation(_obs(), _claims(), ADMISSIBLE, CONFIG))
    raised = _success(route_observation(_obs(), _claims(), ADMISSIBLE, CONFIG, dopamine_gain=0.2))
    inverted = _success(route_observation(_obs(valence=-0.5), _claims(), ADMISSIBLE, CONFIG, dopamine_gain=0.2))
    assert raised["routes"][0]["priority"] > neutral["routes"][0]["priority"]
    assert inverted["routes"][0]["priority"] < neutral["routes"][0]["priority"]
    assert neutral["budget_ledger"]["envelope"] == raised["budget_ledger"]["envelope"]
    assert all(x["closure_count"] == 0 for x in (neutral, raised, inverted))
    assert all(x["signal_validity"] == "UNTESTED" for x in (neutral, raised, inverted))


def test_inhibition_forces_hold_without_promoting_truth() -> None:
    result = _success(route_observation(_obs(inhibition=0.9), _claims(2), ADMISSIBLE, CONFIG))
    assert result["status"] == "ROUTING_ONLY"
    assert all(r["mode"] == "quarantine" for r in result["routes"])
    assert all(r["reason"] == "INHIBITION_HOLD" for r in result["routes"])
    assert all(r["verification_result"] == "not_run" for r in result["routes"])
    assert not any(r["mode"] in {"close", "verified"} for r in result["routes"])


def test_untrusted_projection_is_not_labeled_live_dnca() -> None:
    result = _success(route_observation(_obs(), _claims(), ADMISSIBLE, CONFIG))
    assert result["source"] == "UNTRUSTED_SPS_PROJECTION"
    assert result["modulation_scope"] == "GLOBAL_THRESHOLD_SHIFT_NOT_CLAIM_SPECIFIC"
    assert result["claim_specific_signal_qualified"] is False


def test_failed_construct_gates_produce_no_routes_or_spend() -> None:
    result = _success(route_observation(_obs(), _claims(), BLOCKED, CONFIG))
    assert result["status"] == "INSTRUMENT_INADMISSIBLE"
    assert result["routes"] == []
    assert result["budget_ledger"]["spent"] == 0.0


def test_budget_conserved_under_scarcity() -> None:
    result = _success(route_observation(_obs(), _claims(40), ADMISSIBLE, CONFIG))
    ledger = result["budget_ledger"]
    assert ledger["conserved"] is True
    assert ledger["remaining"] >= 0.0
    assert math.isclose(ledger["spent"] + ledger["remaining"], ledger["envelope"])
    assert any(r["reason"] == "INSUFFICIENT_BUDGET" for r in result["routes"])
    assert result["closure_count"] == 0


@pytest.mark.parametrize("gain", [-0.1, 0.251, 3.0, float("nan")])
def test_invalid_gain_fails_closed(gain: float) -> None:
    assert isinstance(
        route_observation(_obs(), _claims(), ADMISSIBLE, CONFIG, dopamine_gain=gain), Err
    )


def test_duplicate_and_invalid_evidence_rejected() -> None:
    evidence = _claims()
    assert isinstance(
        route_observation(_obs(), evidence + evidence, ADMISSIBLE, CONFIG), Err
    )
    bad = [EvidenceInput("bad", 0.5, 0.5, 1.2, 0.2, 0.5)]
    assert isinstance(route_observation(_obs(), bad, ADMISSIBLE, CONFIG), Err)


def test_unexecuted_observation_cannot_route() -> None:
    assert isinstance(
        route_observation(DNCAObservation(0.4, 0.2, 0.2, 0.2, 0), _claims(), ADMISSIBLE, CONFIG),
        Err,
    )


def test_fake_dnca_object_not_accepted_as_live_runtime() -> None:
    result = route_live_dnca(object(), _claims(), ADMISSIBLE, CONFIG)
    assert isinstance(result, Err)


def test_sps_projection_rejects_missing_nonfinite_and_unrun() -> None:
    torch = pytest.importorskip("torch")
    fields = {
        "step": 1,
        "prediction_error": torch.tensor([0.5, 0.2]),
        "valence": torch.tensor([0.3]),
        "dopamine_signal": torch.tensor([0.4]),
        "inhibition_signal": torch.tensor([0.1]),
    }
    projected = observe_sps(fields)
    assert 0 < projected.prediction_error < 1
    assert projected.signed_valence == pytest.approx(0.3)
    for patch in (
        {"step": 0},
        {"prediction_error": torch.tensor([float("nan")])},
        {"dopamine_signal": torch.tensor([0.1, 0.2])},
        {"inhibition_signal": torch.tensor([1.1])},
    ):
        with pytest.raises(ValueError):
            observe_sps({**fields, **patch})


def test_output_is_stable_for_same_input_and_config() -> None:
    a = _success(route_observation(_obs(), _claims(3), ADMISSIBLE, CONFIG))
    b = _success(route_observation(_obs(), _claims(3), ADMISSIBLE, CONFIG))
    assert a == b



def test_executed_dnca_runtime_projects_to_routing_only() -> None:
    """Real integration smoke: no mocks, no truth claim, only routing."""
    torch = pytest.importorskip("torch")
    try:
        from neuron7x_agents.dnca.orchestrator import DNCA
    except ImportError:
        pytest.skip("install local agents package: pip install -e agents")
    model = DNCA(state_dim=16, hidden_dim=32, seed=42)
    model.step(torch.zeros(16), reward=0.1)
    result = route_live_dnca(model, _claims(), ADMISSIBLE, CONFIG)
    output = _success(result)
    assert output["source"] == "EXECUTED_DNCA_SPS"
    assert output["dnca_step"] >= 1
    assert output["status"] == "ROUTING_ONLY"
    assert output["closure_count"] == 0
    assert output["signal_validity"] == "UNTESTED"
