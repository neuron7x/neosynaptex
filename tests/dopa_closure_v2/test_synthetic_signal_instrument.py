"""Metamorphic and discriminative tests of synthetic routing instrument only."""
from __future__ import annotations

import random

import pytest

from experiments.dopa_signal_validity.paired_instrument import (
    Candidate, TrialConfig, evaluate, run_trial, selected_indices,
)


def test_reproducible_seeded_instrument() -> None:
    assert evaluate(TrialConfig(trials=32)) == evaluate(TrialConfig(trials=32))


def test_top_k_selection_does_not_read_outcomes() -> None:
    rows = [Candidate(i, 0.4 + i * 0.01, 0.5, i % 2) for i in range(8)]
    altered = [Candidate(x.claim_id, x.uncertainty_proxy, x.cue, 1-x.verification_benefit)
               for x in rows]
    scores = [x.uncertainty_proxy for x in rows]
    assert selected_indices(rows, scores, 3) == selected_indices(altered, scores, 3)


def test_all_policies_receive_identical_budget() -> None:
    cfg = TrialConfig(trials=4, candidates=40, slots=7)
    scores = run_trial(random.Random(42), cfg, informative=True)
    assert set(scores) == {
        "uncertainty_only", "modulated", "permuted", "sign_reversed", "random", "oracle_ceiling",
    }
    assert all(0 <= x <= cfg.slots for x in scores.values())
    assert scores["oracle_ceiling"] >= max(scores.values())


def test_discriminates_informative_cue_from_null() -> None:
    result = evaluate(TrialConfig(trials=128))
    good = result["regimes"]["informative"]
    null = result["regimes"]["null"]
    assert good["paired_gain_vs_uncertainty"] > 1.0
    assert good["paired_bootstrap_95pct"][0] > 0.0
    assert abs(null["paired_gain_vs_uncertainty"]) < 1.0
    assert good["mean_verified_benefit_per_trial"]["modulated"] > (
        good["mean_verified_benefit_per_trial"]["permuted"]
    )


def test_zero_gain_equals_baseline_on_every_trial() -> None:
    cfg = TrialConfig(gain=0.0, candidates=40, slots=5)
    for seed in range(20):
        r = run_trial(random.Random(seed), cfg, informative=bool(seed % 2))
        assert r["modulated"] == r["uncertainty_only"]
        assert r["permuted"] == r["uncertainty_only"]
        assert r["sign_reversed"] == r["uncertainty_only"]


@pytest.mark.parametrize("wrong", [
    {"trials": 0}, {"candidates": 1}, {"slots": 0},
    {"slots": 128}, {"gain": -0.1}, {"gain": 0.26}, {"seed": True},
])
def test_bad_protocol_fails_closed(wrong: dict) -> None:
    with pytest.raises(ValueError):
        TrialConfig(**wrong)
