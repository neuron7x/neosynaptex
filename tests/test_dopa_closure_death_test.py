"""Offline deterministic tests for the DOPA-CLOSURE death-test.

No network. Uses the committed 50-item smoke fixture by forcing the loader
away from the (git-ignored) full SciFact release.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "experiments"))

import dopa_closure_death_test as dt  # noqa: E402


@pytest.fixture
def smoke(monkeypatch: pytest.MonkeyPatch) -> tuple[list[dt.Item], list[dt.Item], str]:
    # force fixture path (no network, no full dataset dependency)
    monkeypatch.setattr(dt, "_SCIFACT", _ROOT / "tests" / "fixtures" / "__none__")
    return dt.load_items()


def test_fixture_loads_binary(smoke: tuple[list[dt.Item], list[dt.Item], str]) -> None:
    train, dev, src = smoke
    assert src == "scifact_smoke_fixture"
    assert len(train) > 0 and len(dev) > 0
    assert all(it.label in (0, 1) for it in train + dev)


def test_substrate_identical_across_policies(
    smoke: tuple[list[dt.Item], list[dt.Item], str],
) -> None:
    train, dev, _ = smoke
    s = dt.build_substrate(train, dev, seed=42)
    assert len(s.gold) == len(dev)
    assert len(s.cheap_pred) == len(s.margin) == len(s.ensemble_pred)


def test_equal_budget_invariant(
    smoke: tuple[list[dt.Item], list[dt.Item], str],
) -> None:
    train, dev, _ = smoke
    s = dt.build_substrate(train, dev, seed=42)
    _, dopa_b = dt.policy_dopa(s, invert=False)
    _, unc_b = dt.policy_uncertainty_only(s, dopa_b)
    # budget-matched policies never exceed dopa's extra budget
    assert unc_b <= dopa_b
    assert dt.policy_cheap_only(s)[1] == 0


def test_determinism(smoke: tuple[list[dt.Item], list[dt.Item], str]) -> None:
    train, dev, _ = smoke
    r1 = dt.run_seed(train, dev, 101)
    r2 = dt.run_seed(train, dev, 101)
    assert r1 == r2


def test_inverted_is_true_negative_control(
    smoke: tuple[list[dt.Item], list[dt.Item], str],
) -> None:
    train, dev, _ = smoke
    s = dt.build_substrate(train, dev, seed=42)
    v_dopa, _ = dt.policy_dopa(s, invert=False)
    v_inv, _ = dt.policy_dopa(s, invert=True)
    # the control must select a genuinely different verify set (not decoration)
    assert v_dopa != v_inv or s.cheap_pred == s.ensemble_pred


def test_result_schema_valid_if_present() -> None:
    res = _ROOT / "evidence" / "dopa_closure" / "death_test_result.json"
    schema = json.loads((_ROOT / "schemas" / "dopa_death_test_result.schema.json").read_text())
    if res.exists():
        jsonschema.validate(json.loads(res.read_text()), schema)
