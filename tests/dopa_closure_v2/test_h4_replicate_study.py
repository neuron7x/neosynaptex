"""H4: eight-seed replay evidence cannot auto-promote scientific status."""
import pytest
from experiments.dopa_signal_validity.h4_replicate_study import SEEDS, replay

@pytest.fixture(scope="module")
def evidence():
    return replay()

def test_replay_never_claims_real_dnca_or_independent_oracle(evidence):
    assert evidence["scientific_verdict"] == "SYNTHETIC_ONLY_REAL_DNCA_TD_UNTESTED"
    assert evidence["oracle_receipts_verified"] is False
    assert evidence["post_outcome_td_used_for_same_claim_routing"] is False
    assert evidence["cost_status"] == "SLOTS_MATCHED_TOTAL_TRAIN_INFERENCE_NOT_MATCHED"

def test_eight_seed_identity_and_provenance(evidence):
    assert evidence["seeds"] == list(SEEDS)
    assert len(evidence["dataset_sha256_by_seed"]) == len(SEEDS)
    assert len(evidence["sha256_before_digest"]) == 64
    for model in evidence["model_summary"].values():
        assert len(model["per_seed_utility"]) == len(SEEDS)
        assert len(model["per_seed_brier"]) == len(SEEDS)
        assert all(len(h) == 64 for h in model["checkpoints_sha256"])

def test_linear_is_competitor_not_auto_victory(evidence):
    # Checks evidence shape and explicit two-sided uncertainty, not a fixed winning arm.
    lo, hi = evidence["descriptive_seed_bootstrap_95pct"]
    assert lo <= evidence["mean_value_minus_linear"] <= hi
    assert evidence["model_summary"]["full_linear"]["mean_brier"] >= 0
    assert evidence["model_summary"]["trained_value_net"]["mean_brier"] >= 0
