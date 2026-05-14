"""Tests for graded falsification (FalsificationResult + conflict_strength).

CONTRACT pinned:
- conflict_strength = 0.0 on clean claim
- conflict_strength = 1.0 on physical-impossibility violation
- conflict_strength rises monotonically with full-substring hits
- token-overlap-only contributes lower per-hit weight than full substring
- clamp to [0.0, 1.0]
- legacy falsification_decision tuple signature preserved (backwards compat)
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.falsification_engine import (
    FalsificationResult,
    falsification_decision,
    falsification_decision_graded,
)


def test_clean_claim_has_zero_conflict_strength() -> None:
    r = falsification_decision_graded("bounded local claim on test bed t1", [])
    assert r.passed is True
    assert r.reason == "passed"
    assert r.conflict_strength == 0.0


def test_physical_impossibility_gives_max_conflict_strength() -> None:
    r = falsification_decision_graded(
        "Device demonstrates perpetual motion under standard lab conditions.", []
    )
    assert r.passed is False
    assert r.reason == "physical_plausibility_violation"
    assert r.conflict_strength == 1.0


def test_single_full_substring_marker_yields_0_4() -> None:
    r = falsification_decision_graded(
        "Function always exceeds 1 on normalised vectors.", ["always exceeds 1"]
    )
    assert r.passed is False
    assert r.reason == "contradiction_marker_hit"
    assert abs(r.conflict_strength - 0.4) < 1e-9


def test_two_full_substring_markers_clamp_below_one() -> None:
    r = falsification_decision_graded(
        "Function always exceeds 1 and guaranteed 100% on adversarial inputs.",
        ["always exceeds 1", "guaranteed 100%"],
    )
    assert r.passed is False
    # 0.4 + 0.4 = 0.8
    assert abs(r.conflict_strength - 0.8) < 1e-9


def test_token_overlap_only_yields_smaller_increment() -> None:
    # No substring of "all problem sizes without restriction" appears
    # in the claim text, but the tokens {all, problem, sizes, without,
    # restriction} overlap with the token set of the claim text by at
    # least 2 unique tokens.
    r = falsification_decision_graded(
        "Algorithm correctness holds for all sizes of problems without any restriction.",
        ["all problem sizes without restriction"],
    )
    assert r.passed is True  # binary level: no substring hit
    assert r.reason == "passed_with_token_overlap_conflict"
    assert abs(r.conflict_strength - 0.15) < 1e-9


def test_token_overlap_less_than_full_substring() -> None:
    full = falsification_decision_graded("always exceeds 1 in the system", ["always exceeds 1"])
    token = falsification_decision_graded(
        "the system handles every input universally", ["universal coverage every input"]
    )
    assert full.conflict_strength > token.conflict_strength


def test_clamp_to_one_when_many_hits() -> None:
    markers = ["always exceeds 1"] * 10  # 10 * 0.4 = 4.0, must clamp
    r = falsification_decision_graded("Function always exceeds 1 in tests.", markers)
    assert r.conflict_strength == 1.0


def test_legacy_falsification_decision_unchanged() -> None:
    # Existing callers receive (bool, str) — preserved.
    passed, reason = falsification_decision(
        "Function always exceeds 1 on normalised vectors.", ["always exceeds 1"]
    )
    assert passed is False
    assert reason == "contradiction_marker_hit"


def test_falsification_result_is_frozen_dataclass() -> None:
    """If FalsificationResult ever becomes mutable, this test MUST
    fail. Codex P2: a bare ``except Exception`` would swallow the
    ``AssertionError`` raised on unexpected successful mutation,
    making the test ineffective. Use ``pytest.raises`` with the
    specific ``FrozenInstanceError`` so a successful mutation
    propagates an uncaught AttributeError and fails the test.
    """
    r = FalsificationResult(passed=True, reason="passed", conflict_strength=0.0)
    with pytest.raises(FrozenInstanceError):
        r.passed = False  # type: ignore[misc]


def test_single_token_overlap_below_two_is_not_a_hit() -> None:
    # One unique-token overlap is below threshold (>=2 needed) -> no token hit
    r = falsification_decision_graded(
        "The system tested handles synthetic data on bench T.",
        [
            "universally adversarial input"
        ],  # only "universally" / "adversarial" / "input" — overlap = 0
    )
    assert r.conflict_strength == 0.0
