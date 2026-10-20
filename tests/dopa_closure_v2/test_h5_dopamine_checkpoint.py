"""H5: actual DopamineOperator frozen-state integration; no false cognitive claim."""

import pytest
import torch

from experiments.dopa_signal_validity.h5_td_lambda import (
    Plan,
    prepare_frozen_value_checkpoint,
)


@pytest.fixture(scope="module")
def trained_tensors():
    p = Plan(train_episodes=48, validation_episodes=16, test_episodes=20, epochs=12)
    return prepare_frozen_value_checkpoint(p)


@pytest.mark.slow
def test_real_operator_consumes_frozen_td_lambda_weights(trained_tensors):
    mod = pytest.importorskip("neuron7x_agents.dnca.neuromodulators.dopamine")
    operator = mod.DopamineOperator(state_dim=8, hidden_dim=32)
    weights, digest, meta = trained_tensors
    assert operator.install_frozen_value_weights(weights, expected_sha256=digest) == digest
    assert all(not param.requires_grad for param in operator.value_net.parameters())
    assert operator.value_checkpoint_sha256 == digest
    assert operator.value_assurance_level == "FROZEN_WEIGHTS_NOT_EXTERNALLY_QUALIFIED"
    vector = torch.linspace(-0.5, 0.4, 8)
    previous = operator._prev_value
    ex_ante = operator.predict_value_ex_ante(vector)
    assert operator._prev_value == previous  # cannot consume future reward
    assert isinstance(ex_ante, float)
    assert meta["domain"] == "STOCHASTIC_SOFTWARE_ENV_NOT_FIELD_DATA"


@pytest.mark.slow
def test_tampered_h5_tensor_rejected_before_operator_mutation(trained_tensors):
    mod = pytest.importorskip("neuron7x_agents.dnca.neuromodulators.dopamine")
    operator = mod.DopamineOperator(state_dim=8, hidden_dim=32)
    weights, digest, _ = trained_tensors
    altered = dict(weights)
    altered["0.weight"] = weights["0.weight"].clone()
    altered["0.weight"][0, 0] += 1.0
    before = operator.value_net.state_dict()["0.weight"].detach().clone()
    with pytest.raises(ValueError, match="value_checkpoint_hash_mismatch"):
        operator.install_frozen_value_weights(altered, expected_sha256=digest)
    assert torch.equal(before, operator.value_net.state_dict()["0.weight"])
    with pytest.raises(ValueError, match="no_frozen_checkpoint_installed"):
        operator.predict_value_ex_ante(torch.zeros(8))


@pytest.mark.slow
def test_unsafe_dtype_nonfinite_or_bad_shape_are_rejected(trained_tensors):
    mod = pytest.importorskip("neuron7x_agents.dnca.neuromodulators.dopamine")
    weights, digest, _ = trained_tensors
    op = mod.DopamineOperator(state_dim=8, hidden_dim=32)
    for candidate in (
        weights["0.weight"].double(),
        torch.full_like(weights["0.weight"], float("nan")),
        weights["0.weight"][1:],
    ):
        altered = dict(weights)
        altered["0.weight"] = candidate
        with pytest.raises(ValueError):
            op.install_frozen_value_weights(altered, expected_sha256=digest)


def test_training_handoff_is_tensors_not_pickled_bytes(trained_tensors):
    weights, digest, meta = trained_tensors
    assert all(isinstance(value, torch.Tensor) for value in weights.values())
    assert set(weights) == {"0.weight", "0.bias", "2.weight", "2.bias"}
    assert tuple(weights["0.weight"].shape) == (16, 8)
    assert len(digest) == 64
    assert meta["train_receipt"]["status"] == "CONSISTENT_WITH_DECLARED_REWARD_FUNCTION"
