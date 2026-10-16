from __future__ import annotations
from dataclasses import replace
import math
import pytest
import torch
from experiments.dopa_signal_validity.h5_td_lambda import Plan, Step, collect, audit_oracle, lambda_returns, monte_carlo, run


def test_actual_stochastic_rollout_provenance():
    a=collect(53,12,8)
    b=collect(53,12,8)
    c=collect(54,12,8)
    assert a==b and a!=c
    assert audit_oracle(a)==audit_oracle(b)
    assert audit_oracle(a)!=audit_oracle(c)


def test_oracle_detects_changed_reward():
    eps=collect(8,10,6)
    eps[0][2]=replace(eps[0][2],reward=eps[0][2].reward+0.01)
    with pytest.raises(ValueError,match='reward_oracle_mismatch'):
        audit_oracle(eps)


def test_oracle_detects_broken_temporal_link():
    eps=collect(8,10,6)
    eps[0][2]=replace(eps[0][2],state=(eps[0][2].state[0],0.0,*eps[0][2].state[2:]))
    with pytest.raises(ValueError,match='transition_chain_broken'):
        audit_oracle(eps)


def test_oracle_detects_terminal_forge():
    eps=collect(8,10,6)
    eps[0][1]=replace(eps[0][1],done=True)
    with pytest.raises(ValueError,match='terminal_flag_mismatch'):
        audit_oracle(eps)


def test_lambda_one_equals_monte_carlo_even_when_bootstrap_wrong():
    eps=collect(5,5,7)
    size=sum(map(len,eps))
    target=lambda_returns(eps,torch.randn(size),0.94,1.)
    assert torch.allclose(target,monte_carlo(eps,.94),atol=1e-6)


def test_lambda_zero_one_step_td_without_terminal_bootstrap():
    eps=collect(5,3,5)
    bs=torch.full((15,),3.)
    out=lambda_returns(eps,bs,.9,0.)
    for i,st in enumerate(ep for e in eps for ep in e):
        expect=st.reward if st.done else st.reward + .9*3.
        assert math.isclose(float(out[i]),expect,abs_tol=1e-6)


def test_closed_form_two_transition_episode():
    ep=[Step((0,)*5,0,1.,(0,)*5,False),Step((0,)*5,0,2.,(0,)*5,True)]
    for lam in [0.,.5,1.]:
        t=lambda_returns([ep],torch.tensor([10.,4.]),.9,lam)
        assert math.isclose(float(t[1]),2.,abs_tol=1e-6)
        assert math.isclose(float(t[0]),1.+.9*((1-lam)*10. +lam*2.),abs_tol=1e-6)


def test_wrong_bootstrap_or_nonfinite_rejected():
    eps=collect(5,3,5)
    with pytest.raises(ValueError,match='bootstrap_shape'):
        lambda_returns(eps,torch.zeros(3),.9,.7)
    data=torch.zeros(15);data[0]=float('nan')
    with pytest.raises(ValueError,match='nonfinite_bootstrap'):
        lambda_returns(eps,data,.9,.7)


@pytest.mark.parametrize('bad',[
    {'train_episodes':5},{'validation_episodes':1},{'test_episodes':1},
    {'horizon':1},{'epochs':0},{'gamma':float('nan')},
    {'lam':1.01},{'learning_rate':0.}, {'seed':True}
])
def test_invalid_plan_failclosed(bad):
    with pytest.raises(ValueError):Plan(**bad)


def test_training_preserves_oracle_independence_and_cost_trace():
    result=run(Plan(train_episodes=48,validation_episodes=16,test_episodes=20,epochs=20))
    assert result['oracle_external_independence'] is False
    assert result['scientific_verdict']=='INSTRUMENT_PROTOTYPE_ONLY_REAL_ENV_AND_DNCA_UNTESTED'
    assert result['policies_cost_matched'] is False
    assert result['reward_leakage_into_action_selection'] is False
    assert len(set(result['dataset_sha256'].values()))==3
    for model in result['models'].values():
        assert math.isfinite(model['holdout_return_mse'])
        assert len(model['checkpoint_sha256'])==64
        assert model['train_seconds']>=0
        assert model['forward_MACs_upper_bound_per_state']>0
    assert result['models']['td_lambda_neural']['parameter_count'] > result['models']['td_lambda_linear']['parameter_count']


def test_reproducible_checkpoint_and_holdout_error():
    p=Plan(train_episodes=48,validation_episodes=16,test_episodes=20,epochs=20)
    x,y=run(p),run(p)
    for name in x['models']:
        assert x['models'][name]['checkpoint_sha256']==y['models'][name]['checkpoint_sha256']
        assert x['models'][name]['holdout_return_mse']==y['models'][name]['holdout_return_mse']


def test_separate_process_oracle_approves_authentic_and_detects_tampering():
    from experiments.dopa_signal_validity.h5_td_lambda import separate_process_oracle
    rows=collect(71,4,5)
    receipt=separate_process_oracle(rows)
    assert receipt['transitions']==20
    assert receipt['status']=='CONSISTENT_WITH_DECLARED_REWARD_FUNCTION'
    assert len(receipt['trajectory_sha256'])==64
    rows[0][0]=replace(rows[0][0],reward=rows[0][0].reward+0.3)
    with pytest.raises(ValueError,match='separate_oracle_rejected'):
        separate_process_oracle(rows)


def test_oracle_cannot_use_model_parameters():
    import inspect
    from experiments.dopa_signal_validity.h5_td_lambda import separate_process_oracle
    assert set(inspect.signature(separate_process_oracle).parameters)=={'trajectories'}


def test_training_outputs_frozen_safe_tensor_handoff():
    from experiments.dopa_signal_validity.h5_td_lambda import prepare_frozen_value_checkpoint
    p=Plan(train_episodes=48,validation_episodes=16,test_episodes=20,epochs=10)
    weights,digest,meta=prepare_frozen_value_checkpoint(p)
    assert len(digest)==64
    assert set(weights)=={'0.weight','0.bias','2.weight','2.bias'}
    assert tuple(weights['0.weight'].shape)==(16,8)
    assert tuple(weights['2.weight'].shape)==(1,16)
    assert all(isinstance(x,torch.Tensor) and torch.isfinite(x).all() for x in weights.values())
    assert meta['domain']=='STOCHASTIC_SOFTWARE_ENV_NOT_FIELD_DATA'


def test_forged_derived_markov_features_rejected():
    eps=collect(8,5,6)
    s=list(eps[0][0].state)
    s[5]+=0.4
    eps[0][0]=replace(eps[0][0],state=tuple(s))
    with pytest.raises(ValueError,match='forged_derived_features'):
        audit_oracle(eps)
    from experiments.dopa_signal_validity.h5_td_lambda import separate_process_oracle
    with pytest.raises(ValueError,match='separate_oracle_rejected'):
        separate_process_oracle(eps)
