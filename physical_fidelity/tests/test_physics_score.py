"""Oracle smoke + regression tests (NFI-PROMPT-002 Phase 1)."""

from __future__ import annotations

from physical_fidelity import physics_score


def test_compute_score_returns_numbers_in_range():
    result = physics_score.compute_score()
    assert 0.0 <= result["S_total"] <= 100.0
    assert result["classification"] == "ADMISSIBILITY"
    for axis in result["axes"]:
        assert 0.0 <= axis["value"] <= 100.0


def test_all_axes_present():
    result = physics_score.compute_score()
    ids = {a["id"] for a in result["axes"]}
    assert ids == set(physics_score.SCORERS)
    assert len(ids) == 10


def test_score_does_not_regress_below_baseline():
    # Regression guard: the reference apparatus must stay fully admissible.
    result = physics_score.compute_score()
    assert result["S_total"] >= 95.0, result


def test_trace_map_files_exist():
    for entry in physics_score.EQUATION_TRACE:
        code = physics_score.ROOT / entry["code_path"].split("::")[0]
        test = physics_score.ROOT / entry["test"].split("::")[0]
        assert code.exists(), entry["code_path"]
        assert test.exists(), entry["test"]
