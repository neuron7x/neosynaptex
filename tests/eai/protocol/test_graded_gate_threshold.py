"""Tests for the graded IEV-gate threshold modulation.

CONTRACT pinned:
- required_revalidation_paths is monotone non-decreasing in conflict_strength
- conflict_strength == 0 reproduces legacy IEV gate behaviour
- threshold scaling: c=0.5 -> 2 paths required; c=1.0 -> 3 paths required
- artifact with insufficient paths at c>0 -> QUARANTINED with
  reason "graded_threshold_unmet"
- emergency exit, retention_hash invalid, revalidation_passed=False
  short-circuit before threshold check
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.eai.graded_gate import (
    GradedGateDecision,
    decide_with_graded_threshold,
    required_revalidation_paths,
)
from core.eai.intelligence_cycle import (
    BoundaryCard,
    ClaimCard,
    ClaimType,
    EvidenceArtifact,
    FalsificationReport,
    ReproducibilityManifest,
)


def _artifact(paths: list[str]) -> EvidenceArtifact:
    return EvidenceArtifact(
        artifact_id="EVD-X",
        claim=ClaimCard("CLM-X", "bounded local claim", ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-X", ["local"], ["global"], ["local"], ["global"]),
        falsification_report=FalsificationReport(["gate_falsification"], True),
        reproducibility=ReproducibilityManifest(["pytest"], "test", "a" * 64),
        integration_permission=True,
        revalidation_evidence_paths=paths,
    )


def test_required_paths_monotone_in_conflict() -> None:
    assert required_revalidation_paths(0.0) == 1
    assert required_revalidation_paths(0.25) == 2
    assert required_revalidation_paths(0.5) == 2
    assert required_revalidation_paths(0.75) == 3
    assert required_revalidation_paths(1.0) == 3
    # Out-of-range inputs clamp
    assert required_revalidation_paths(-1.0) == 1
    assert required_revalidation_paths(5.0) == 3


def test_zero_conflict_with_one_path_promotes_to_evidence() -> None:
    art = _artifact(["path_a"])
    d = decide_with_graded_threshold(
        art, retention_hash="a" * 64, revalidation_passed=True, conflict_strength=0.0
    )
    assert d.status == "EVIDENCE"
    assert d.reason == "promotion_allowed"
    assert d.required_paths == 1


def test_half_conflict_requires_two_paths() -> None:
    art_low = _artifact(["only_one"])
    d_low = decide_with_graded_threshold(
        art_low, retention_hash="a" * 64, revalidation_passed=True, conflict_strength=0.5
    )
    assert d_low.status == "QUARANTINED"
    assert d_low.reason == "graded_threshold_unmet"
    assert d_low.required_paths == 2

    art_ok = _artifact(["one", "two"])
    d_ok = decide_with_graded_threshold(
        art_ok, retention_hash="a" * 64, revalidation_passed=True, conflict_strength=0.5
    )
    assert d_ok.status == "EVIDENCE"


def test_full_conflict_requires_three_paths() -> None:
    art_low = _artifact(["one", "two"])
    d_low = decide_with_graded_threshold(
        art_low, retention_hash="a" * 64, revalidation_passed=True, conflict_strength=1.0
    )
    assert d_low.status == "QUARANTINED"
    assert d_low.required_paths == 3

    art_ok = _artifact(["one", "two", "three"])
    d_ok = decide_with_graded_threshold(
        art_ok, retention_hash="a" * 64, revalidation_passed=True, conflict_strength=1.0
    )
    assert d_ok.status == "EVIDENCE"


def test_revalidation_not_passed_short_circuits_before_threshold() -> None:
    art = _artifact(["one", "two", "three", "four"])
    d = decide_with_graded_threshold(
        art, retention_hash="a" * 64, revalidation_passed=False, conflict_strength=0.0
    )
    assert d.status == "QUARANTINED"
    assert d.reason == "revalidation_not_passed"


def test_invalid_retention_hash_short_circuits() -> None:
    art = _artifact(["one"])
    d = decide_with_graded_threshold(
        art, retention_hash="not-hex", revalidation_passed=True, conflict_strength=0.0
    )
    assert d.status == "QUARANTINED"
    assert d.reason == "retention_hash_invalid"


def test_can_be_promoted_false_yields_killed() -> None:
    # Boundary with empty valid_for -> can_be_promoted False
    bad_artifact = EvidenceArtifact(
        artifact_id="EVD-Y",
        claim=ClaimCard("CLM-Y", "x", ClaimType.FACTUAL),
        boundary=BoundaryCard("BND-Y", [], ["g"], [], ["g"]),
        falsification_report=FalsificationReport(["t"], True),
        reproducibility=ReproducibilityManifest(["pytest"], "test", "a" * 64),
        integration_permission=True,
        revalidation_evidence_paths=["one"],
    )
    d = decide_with_graded_threshold(
        bad_artifact,
        retention_hash="a" * 64,
        revalidation_passed=True,
        conflict_strength=0.0,
    )
    assert d.status == "KILLED"
    assert d.reason == "can_be_promoted_false"


def test_emergency_exit_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAI_EMERGENCY_EXIT", "true")
    art = _artifact(["one"])
    d = decide_with_graded_threshold(
        art, retention_hash="a" * 64, revalidation_passed=True, conflict_strength=0.0
    )
    assert d.status == "QUARANTINED"
    assert d.reason == "emergency_exit"


def test_decision_is_frozen_dataclass() -> None:
    """Codex P2 fix: use FrozenInstanceError-specific raises,
    so successful mutation propagates AttributeError and fails."""
    d = GradedGateDecision(status="EVIDENCE", reason="ok", required_paths=1, available_paths=1)
    with pytest.raises(FrozenInstanceError):
        d.status = "KILLED"  # type: ignore[misc]
