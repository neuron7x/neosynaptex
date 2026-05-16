"""Construct-validity guards for DOPA-VALIDITY-001.

These tests do not check whether DOPA-CLOSURE is true. They check that the
*instrument* cannot lie: that an INADMISSIBLE verdict is a first-class success,
that the negative control is a real sign inversion (never a |vRPE| complement),
that a KILL/SURVIVED is impossible unless admissibility genuinely passed, and
that every constant comes from a single source.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from experiments import dopa_validity_001 as exp
from experiments import dopa_validity_001_config as cfg


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return exp.run()


@pytest.fixture(scope="module")
def schema() -> dict[str, object]:
    return json.loads(cfg.SCHEMA_PATH.read_text())


def test_result_validates_against_schema(
    result: dict[str, object], schema: dict[str, object]
) -> None:
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)


def test_inadmissible_is_allowed_and_not_a_failure(
    result: dict[str, object], schema: dict[str, object]
) -> None:
    """A clean INADMISSIBLE verdict is the designed success mode, not an error."""
    verdict = result["verdict"]
    assert verdict in cfg.ALL_VERDICTS
    if isinstance(verdict, str) and verdict.startswith("INADMISSIBLE"):
        # still a fully-formed, schema-valid artifact — success, not a crash
        Draft202012Validator(schema).validate(result)
        assert result["policy_scores"] == dict.fromkeys(cfg.POLICIES)
        assert result["p_value"] is None


def test_schema_enum_is_single_source() -> None:
    """The verdict vocabulary in the schema must equal the config SSOT."""
    schema = json.loads(cfg.SCHEMA_PATH.read_text())
    enum = schema["properties"]["verdict"]["enum"]
    assert tuple(enum) == cfg.ALL_VERDICTS


def test_config_constants_not_duplicated_in_experiment() -> None:
    """Experiment module must not redefine SSOT constants (config/code drift
    was an explicit RETRACTION invalidator)."""
    for name in ("SEED", "N_ITEMS", "BUDGET_FRACTION", "ALPHA", "DELTA_MIN"):
        assert not hasattr(exp, name), f"{name} duplicated in experiment module"
    assert exp.cfg is cfg


def test_signed_vrpe_sign_flip_is_mathematically_real() -> None:
    """Negative control = vRPE -> -vRPE: a genuine negation, and it must
    actually reorder routing when signs are mixed."""
    vrpe = np.array([-0.9, -0.2, 0.1, 0.4, 0.8], dtype=np.float64)
    dopa = -vrpe
    dopa_inverted = np.negative(dopa)
    assert np.allclose(dopa_inverted, vrpe)  # true sign inversion
    order = np.argsort(-dopa, kind="stable")
    order_inv = np.argsort(-dopa_inverted, kind="stable")
    assert not np.array_equal(order, order_inv)  # non-degenerate flip


def test_abs_complement_is_forbidden_as_inverted_sign() -> None:
    """The forbidden #199 control: complement of |vRPE|. It must NOT equal the
    true sign-flip control whenever any vRPE is non-zero."""
    vrpe = np.array([-0.9, -0.2, 0.1, 0.4, 0.8], dtype=np.float64)
    dopa = -vrpe
    true_flip = np.negative(dopa)
    abs_complement = float(np.abs(vrpe).max()) - np.abs(vrpe)
    assert not np.allclose(true_flip, abs_complement)
    # abs-complement is sign-blind; the true flip is not
    assert np.any(np.sign(true_flip) != np.sign(abs_complement + 1e-12))


def test_majority_and_random_baselines_are_computed(result: dict[str, object]) -> None:
    assert isinstance(result["majority_baseline"], float)
    assert isinstance(result["random_baseline"], float)
    assert 0.0 <= float(result["majority_baseline"]) <= 1.0  # type: ignore[arg-type]
    assert float(result["random_baseline"]) == 0.5  # type: ignore[arg-type]


def test_majority_baseline_matches_task() -> None:
    task = exp._make_task(cfg.SEED)
    p = float(task.truth_valid.mean())
    assert exp.majority_baseline(task) == max(p, 1.0 - p)


def test_verifier_must_beat_majority_before_kill_or_survived(
    result: dict[str, object],
) -> None:
    """No KILLED/SURVIVED verdict may stand unless the verification action
    genuinely beat both majority and random baselines."""
    verdict = result["verdict"]
    if verdict in (cfg.VERDICT_KILLED, cfg.VERDICT_SURVIVED):
        va = result["verifier_admissibility"]
        assert isinstance(va, dict)
        assert va["beats_majority"] is True
        assert va["beats_random"] is True
        assert va["signal_is_truth_correlated"] is True


def test_b2_seed_band_is_independent_of_decision_draws() -> None:
    """RETRACTION precondition #3: the truth-correlation must be shown
    *independently*. The B2 seed band must not overlap the Step-D routing
    seeds nor the Step-B1 seed."""
    b2 = set(exp._b2_seeds())
    routing = {cfg.SEED + s for s in range(cfg.N_SEEDS)}
    assert cfg.SEED not in b2
    assert b2.isdisjoint(routing)
    assert len(b2) == cfg.N_B2_SEEDS
    # data_hash must cover every decision seed, B2 band included
    decision = set(exp._decision_seeds())
    assert b2 <= decision and routing <= decision and cfg.SEED in decision


def test_b2_gate_is_fail_closed_unanimous() -> None:
    """The B2 gate may declare the signal truth-correlated only if it passed
    on EVERY independent seed (B2_REQUIRED_FRACTION == 1.0). A single
    borderline draw can never license a KILL/SURVIVED."""
    assert cfg.B2_REQUIRED_FRACTION == 1.0
    handle = exp.load_dopamine_operator()
    if handle is None:
        pytest.skip("DNCA DopamineOperator not executable in this environment")
    b2 = exp.b2_truth_correlation(handle)
    if b2["signal_is_truth_correlated"]:
        assert b2["b2_seeds_passing"] == b2["b2_seeds_total"]
    assert 0 <= b2["b2_seeds_passing"] <= b2["b2_seeds_total"] == cfg.N_B2_SEEDS


def test_no_unscoped_dopa_closure_kill(result: dict[str, object]) -> None:
    """The instrument may never assert 'DOPA-CLOSURE killed'. A KILL is only
    ever scoped to this implementation (KILL-0979B)."""
    blob = json.dumps(result).lower()
    assert "dopa-closure killed" not in blob
    assert "dopa_closure killed" not in blob
    if result["verdict"] == cfg.VERDICT_KILLED:
        cfg.KILL_PATH.unlink(missing_ok=True)
        exp._write_artifacts(result)
        scoped = json.loads(cfg.KILL_PATH.read_text())
        assert scoped["kill_id"] == "KILL-0979B_DNCA_DOPA_ROUTING"
        assert "UNTESTED" in scoped["scope"]


def test_kill_or_survived_requires_admissibility_passed(
    result: dict[str, object],
) -> None:
    """Step ordering: a verdict of KILLED/SURVIVED implies Steps A, B1, B2, C
    all passed (delta/p/effect populated, signal truth-correlated)."""
    if result["verdict"] in (cfg.VERDICT_KILLED, cfg.VERDICT_SURVIVED):
        assert result["delta_dopa_vs_uncertainty"] is not None
        assert result["p_value"] is not None
        assert result["effect_size"] is not None
        nc = result["negative_control_result"]
        assert isinstance(nc, dict)
        assert nc["is_true_sign_flip"] is True


def test_repro_hash_binds_the_verdict(result: dict[str, object]) -> None:
    """The repro hash must protect the conclusion, not just a number: mutating
    the verdict must change the hash (RETRACTION critique)."""
    mutated_verdict = (
        cfg.VERDICT_KILLED if result["verdict"] != cfg.VERDICT_KILLED else cfg.VERDICT_SURVIVED
    )
    payload = {
        "verdict": mutated_verdict,
        "config_hash": result["config_hash"],
        "data_hash": result["data_hash"],
        "verifier_admissibility": result["verifier_admissibility"],
        "majority_baseline": result["majority_baseline"],
        "random_baseline": result["random_baseline"],
        "policy_scores": result["policy_scores"],
        "delta_dopa_vs_uncertainty": result["delta_dopa_vs_uncertainty"],
        "p_value": result["p_value"],
        "effect_size": result["effect_size"],
        "negative_control_result": result["negative_control_result"],
    }
    assert exp._repro_hash(payload) != result["repro_hash"]


def test_dnca_signal_is_the_real_executable_operator() -> None:
    """Step A must use the actual DNCA DopamineOperator, never a sklearn/TF-IDF
    proxy (the core #199 invalidator)."""
    handle = exp.load_dopamine_operator()
    if handle is None:
        pytest.skip("DNCA DopamineOperator not executable in this environment")
    src = cfg.DNCA_SIGNAL_MODULE
    assert src == "neuron7x_agents.dnca.neuromodulators.dopamine"
    assert "sklearn" not in src and "tfidf" not in src.lower()
    task = exp._make_task(cfg.SEED)
    vrpe = exp.signed_vrpe(handle, task)
    assert vrpe.shape == (cfg.N_ITEMS,)
    assert np.all(np.isfinite(vrpe))
