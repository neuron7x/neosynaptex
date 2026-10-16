import pytest
from core.eai.dnca_first_step_contract import expected_first_step_valence, assert_one_step_zero_reward_construct

@pytest.mark.parametrize('v',[-999,-1,-0.5,0,0.5,1,999])
def test_identity(v):
    expected = max(-1,min(1,0.99*v))
    assert expected_first_step_valence(v)==expected
    assert_one_step_zero_reward_construct(current_value=v,observed_valence=expected,discount=0.99,previous_value=0.,reward=0.)

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,'value'])
def test_bad_value(bad):
    with pytest.raises(ValueError):expected_first_step_valence(bad)

def test_reward_drift():
    with pytest.raises(ValueError,match='requires_zero_reward'):
        assert_one_step_zero_reward_construct(current_value=0,observed_valence=0,discount=0.99,previous_value=0,reward=1)

def test_prior_value_drift():
    with pytest.raises(ValueError,match='requires_zero_reward'):
        assert_one_step_zero_reward_construct(current_value=0,observed_valence=0,discount=0.99,previous_value=0.1,reward=0)

def test_wrong_discount():
    with pytest.raises(ValueError,match='not_default'):
        assert_one_step_zero_reward_construct(current_value=0,observed_valence=0,discount=0.90,previous_value=0,reward=0)

def test_wrong_model_value_observed():
    with pytest.raises(ValueError,match='identity_violated'):
        assert_one_step_zero_reward_construct(current_value=0.2,observed_valence=-0.6,discount=0.99,previous_value=0,reward=0)

def test_clipping_and_noise():
    assert_one_step_zero_reward_construct(current_value=0.4,observed_valence=0.396000003,discount=0.99,previous_value=0,reward=0)

@pytest.mark.slow
def test_real_dopamine_operator_first_step_identity():
    torch=pytest.importorskip("torch")
    module=pytest.importorskip("neuron7x_agents.dnca.neuromodulators.dopamine")
    dopamine=module.DopamineOperator(state_dim=16,hidden_dim=32)
    sensory=torch.linspace(-0.2,0.3,16)
    with torch.no_grad():
        expected_value=dopamine.value_net(sensory).item()
        result=dopamine.modulate({
            "sensory":sensory,
            "reward_context":torch.tensor([0.0]),
            "temporal_discount":torch.tensor([0.99]),
        })
    assert_one_step_zero_reward_construct(
        current_value=expected_value,
        observed_valence=float(result["valence"].item()),
        discount=0.99,previous_value=0.0,reward=0.0
    )
