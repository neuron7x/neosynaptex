"""Diagnostic pilot tests: no truth feedback to DNCA and no false promotion."""
from __future__ import annotations

import math

import pytest

from experiments.dopa_signal_validity import real_dnca_claimwise_pilot as pilot


def test_deterministic_sensory_dataset() -> None:
    config = pilot.ProbeConfig(seeds=(5,), candidates=6, slots=2)
    assert pilot.make_cases(5, config) == pilot.make_cases(5, config)
    features, proxies, labels = pilot.make_cases(5, config)
    assert len(features) == len(proxies) == len(labels) == 6
    assert all(len(x) == 16 for x in features)
    assert all(0 <= p <= 1 for p in proxies)
    assert all(y in (0, 1) for y in labels)


def test_oracle_labels_cannot_be_passed_to_real_dnca_signature() -> None:
    import inspect

    parameters = inspect.signature(pilot.collect_real_dnca_cues).parameters
    assert set(parameters) == {"features", "seed", "config"}
    assert "labels" not in parameters and "utility" not in parameters


def test_mocked_cues_never_promote_untrained_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = pilot.ProbeConfig(seeds=(11,), model_seed=11, candidates=6, slots=2)
    def simulated_cue(features, *, seed, config):
        assert seed == 11
        assert len(features) == 6
        return [0.1 * (i - 2) for i in range(len(features))], 50, "SIMULATED"
    monkeypatch.setattr(pilot, "collect_real_dnca_cues", simulated_cue)
    record = pilot.execute_pilot(config)
    assert record["verdict"] == "INSTRUMENT_INADMISSIBLE_UNTRAINED_SIGNAL"
    assert record["runs"][0]["analysis"]["global_shift_strict_inversions"] == 0
    assert record["runs"][0]["analysis"]["all_arms_same_slots"]
    assert record["runs"][0]["torch_version"] == "SIMULATED"
    assert record["runs"][0]["data_seed"] == 11
    assert record["runs"][0]["model_seed"] == 11
    assert record["signal_construct"] == "CLIPPED_GAMMA_TIMES_RANDOM_VALUE_NET_NOT_TD_LEARNING"
    assert len(record["runs"][0]["sensory_inputs_sha256"]) == 64
    assert len(record["runs"][0]["withheld_utility_sha256"]) == 64
    assert len(record["runs"][0]["cue_values_sha256"]) == 64


@pytest.mark.parametrize("options", [
    {"candidates": 2},
    {"slots": 12},
    {"state_dim": 7},
    {"hidden_dim": 15},
    {"seeds": (1, 1)},
])
def test_malformed_configs_fail_closed(options: dict) -> None:
    with pytest.raises(ValueError):
        pilot.ProbeConfig(**options)


@pytest.mark.slow
def test_real_dnca_one_claim_executes_without_truth_feedback() -> None:
    """Actual dependency test: separate from controlled analytic tests."""
    pytest.importorskip("torch")
    pytest.importorskip("neuron7x_agents.dnca.orchestrator")
    cfg = pilot.ProbeConfig(seeds=(31,), candidates=3, slots=1)
    features, _, _ = pilot.make_cases(31, cfg)
    cues, elapsed_ns, _ = pilot.collect_real_dnca_cues(
        features[:1], seed=31, config=cfg
    )
    assert len(cues) == 1
    assert math.isfinite(cues[0]) and -1 <= cues[0] <= 1
    assert elapsed_ns >= 0


def test_prequential_mocked_multigroup_cues_never_promote_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostic orchestration: mocked cue output is never DNCA evidence."""
    config = pilot.ProbeConfig(seeds=(11, 12, 13, 14), candidates=6, slots=2)

    def stand_in(features, *, seed, config):
        assert len(features) == 6
        return [0.08 * (i - 3) for i in range(len(features))], 50, "SIMULATED"

    monkeypatch.setattr(pilot, "collect_real_dnca_cues", stand_in)
    record = pilot.execute_pilot(config)
    diagnostic = record["prequential_diagnostic"]
    assert record["verdict"] == "INSTRUMENT_INADMISSIBLE_UNTRAINED_SIGNAL"
    assert all(r["model_seed"] == config.model_seed for r in record["runs"])
    assert [r["data_seed"] for r in record["runs"]] == list(config.seeds)
    assert diagnostic["status"] == "UNQUALIFIED_ORACLE_AND_UNMETERED_COMPUTE"
    assert diagnostic["n_groups"] == 4
    assert diagnostic["oracle_receipt_hashes_verified"] is False
    assert diagnostic["end_to_end_cost_metered"] is False
    assert len(diagnostic["input_sha256"]) == 64


def test_distinct_data_seeds_share_one_model_seed() -> None:
    a = pilot.ProbeConfig(seeds=(1, 2, 3, 4), model_seed=100, candidates=6, slots=2)
    b = pilot.ProbeConfig(seeds=(5, 6, 7, 8), model_seed=100, candidates=6, slots=2)
    assert a.model_seed == b.model_seed
    assert a.seeds != b.seeds


@pytest.mark.parametrize("bad", [True, -1, 2**63, 3.14])
def test_invalid_model_seed_rejected(bad) -> None:
    with pytest.raises(ValueError, match="invalid_model_seed"):
        pilot.ProbeConfig(model_seed=bad)


def test_invalid_data_seed_bool_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_data_seeds"):
        pilot.ProbeConfig(seeds=(31, True, 41, 43))
