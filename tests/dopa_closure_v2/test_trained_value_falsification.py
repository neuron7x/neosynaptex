"""H4 adversarial checks; scoped to supervised synthetic value instrumentation."""
import math
import numpy as np
import pytest
import torch
from experiments.dopa_signal_validity.trained_value_falsification import (
    Plan, _make_data, _network, _selection, _utility, _brier, _model_sha, run,
)

@pytest.fixture(scope="module")
def report():
    return run(Plan(train_n=480,validation_n=160,test_groups=8,candidates=10,
                    slots=3,epochs=35,seed=873))

def test_train_val_test_distinct(report):
    assert len(set(report["dataset_sha256"].values())) == 3
    assert report["test_event_count"] == 80

def test_always_scientifically_inadmissible(report):
    assert report["scientific_verdict"] == "INADMISSIBLE_SYNTHETIC_ORACLE_NO_ACTUAL_DNCA"
    assert report["residual_available_for_same_claim_routing"] is False
    assert report["cost_comparability"].startswith("UNMATCHED")

def test_trained_and_random_checkpoints_differ(report):
    a=report["models"]["trained_value_net"]
    b=report["models"]["untrained_value_net"]
    assert a["checkpoint_sha256"] != b["checkpoint_sha256"]
    assert a["train_seconds"] >= 0
    assert b["train_seconds"] == 0

def test_no_oracle_leakage_during_selection():
    scores=np.array([0.8,0.7,0.6,0.9,0.5,0.1],dtype=float)
    a=_selection(scores,2,3,1)
    labels1=torch.tensor([1.,0.,1.,1.,0.,0.])
    labels2=1-labels1
    assert a==_selection(scores,2,3,1)
    assert _utility(a,labels1) != _utility(a,labels2)

def test_different_plan_seeds_change_heldout_dataset():
    a,_=_make_data(30,45,8)
    b,_=_make_data(30,46,8)
    assert not torch.equal(a,b)

def test_value_topology_is_same_as_da_value_net():
    model=_network(16,32)
    assert isinstance(model[0],torch.nn.Linear)
    assert isinstance(model[1],torch.nn.GELU)
    assert isinstance(model[2],torch.nn.Linear)
    assert tuple(model[0].weight.shape)==(16,16)
    assert tuple(model[2].weight.shape)==(1,16)

def test_random_seed_gives_matching_checkpoint_and_metric():
    p=Plan(train_n=480,validation_n=160,test_groups=8,candidates=10,slots=3,epochs=35,seed=902)
    a,b=run(p),run(p)
    assert a["dataset_sha256"]==b["dataset_sha256"]
    assert all(a['models'][name]['checkpoint_sha256']==b['models'][name]['checkpoint_sha256']
               for name in a['models'])
    assert all(a['models'][name]['heldout_brier']==b['models'][name]['heldout_brier']
               for name in a['models'])
    assert all(a['models'][name]['mean_beneficial_choices_per_group']==b['models'][name]['mean_beneficial_choices_per_group']
               for name in a['models'])

def test_brier_probabilities_are_bounded():
    y=torch.tensor([0.,1.,1.])
    assert _brier(np.array([0.,1.,1.]),y)==0.
    assert _brier(np.array([1.,0.,0.]),y)==1.

def test_model_hash_changes_with_weights():
    model=_network(8,32)
    before=_model_sha(model)
    with torch.no_grad():
        model[0].weight.add_(0.01)
    assert before!=_model_sha(model)

@pytest.mark.parametrize('fields',[
    {'slots':0}, {'slots':16}, {'train_n':50}, {'validation_n':20},
    {'test_groups':3},{'candidates':2},{'hidden':7},{'epochs':0},{'seed':True},
])
def test_invalid_protocol_fail_closed(fields):
    with pytest.raises(ValueError): Plan(**fields)


def test_preoutcome_residual_cannot_be_exante_feature(report):
    assert report["claim"]=="SUPERVISED_CLASSIFIER_NOT_TEMPORAL_DIFFERENCE_LEARNING"
    assert report["residual_available_for_same_claim_routing"] is False
    assert math.isfinite(report["terminal_post_outcome_residual_rmse"])

def test_oracle_ceiling_is_upper_bound(report):
    upper=report['oracle_ceiling_beneficial_choices_per_group']
    assert all(x['mean_beneficial_choices_per_group']<=upper for x in report['models'].values())
