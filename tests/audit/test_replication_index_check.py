"""Deterministic tests for the replication-index ratchet."""

from __future__ import annotations

import json
import pathlib
import textwrap

import pytest

from tools.audit.replication_index_check import (
    ALLOWED_SUBSTRATE_CLASSES,
    ALLOWED_VERDICTS,
    REQUIRED_ENTRY_KEYS,
    IntegrityError,
    load_baseline,
    load_registry,
    run_check,
)


def _write_registry(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / "registry.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _write_baseline(tmp_path: pathlib.Path, count: int) -> pathlib.Path:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"min_replications_count": count}), encoding="utf-8")
    return path


_EMPTY_REGISTRY = textwrap.dedent(
    """\
    schema_version: 1
    protocol: docs/REPLICATION_PROTOCOL.md
    replications: []
    """
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_required_entry_keys_is_non_empty_and_stable():
    # A changing key-set means the registry schema drifted; the detector
    # must fail loudly if either side moves without the other.
    assert "id" in REQUIRED_ENTRY_KEYS
    assert "prereg_path" in REQUIRED_ENTRY_KEYS
    assert "verdict" in REQUIRED_ENTRY_KEYS
    assert "substrate_class" in REQUIRED_ENTRY_KEYS
    assert len(REQUIRED_ENTRY_KEYS) >= 7


def test_substrate_classes_and_verdicts_match_protocol():
    # Neural classes (original REPLICATION_PROTOCOL.md scope).
    neural = {"in_vivo_cns", "neuronal_culture", "simulated_agent"}
    # γ-program extensions per CLAIM_BOUNDARY.md §3.2.
    gamma_program = {
        "market_macro",
        "market_microstructure",
        "developmental_transcriptome",
        "physiological_cardiac",
        "reaction_diffusion",
        "synchronisation",
    }
    assert neural | gamma_program == ALLOWED_SUBSTRATE_CLASSES
    assert {
        "support",
        "falsification",
        "theory_revision",
        "pending",
    } == ALLOWED_VERDICTS


# ---------------------------------------------------------------------------
# load_registry
# ---------------------------------------------------------------------------


def test_load_registry_empty_is_valid(tmp_path):
    path = _write_registry(tmp_path, _EMPTY_REGISTRY)
    data = load_registry(path)
    assert data["replications"] == []


def test_load_registry_missing_file_raises(tmp_path):
    with pytest.raises(IntegrityError, match="not found"):
        load_registry(tmp_path / "nope.yaml")


def test_load_registry_rejects_missing_replications_key(tmp_path):
    path = _write_registry(tmp_path, "schema_version: 1\n")
    with pytest.raises(IntegrityError, match="replications"):
        load_registry(path)


# ---------------------------------------------------------------------------
# load_baseline
# ---------------------------------------------------------------------------


def test_load_baseline_returns_int(tmp_path):
    assert load_baseline(_write_baseline(tmp_path, 3)) == 3


def test_load_baseline_missing(tmp_path):
    with pytest.raises(IntegrityError, match="not found"):
        load_baseline(tmp_path / "x.json")


def test_load_baseline_rejects_negative(tmp_path):
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"min_replications_count": -1}), encoding="utf-8")
    with pytest.raises(IntegrityError, match="non-negative int"):
        load_baseline(path)


# ---------------------------------------------------------------------------
# run_check — integrity + ratchet
# ---------------------------------------------------------------------------


def test_run_check_passes_on_empty_registry_with_zero_baseline(tmp_path):
    registry = _write_registry(tmp_path, _EMPTY_REGISTRY)
    baseline = _write_baseline(tmp_path, 0)
    code, msg = run_check(registry, baseline, repo_root=tmp_path)
    assert code == 0, msg
    assert "0 replication" in msg


def test_run_check_fails_on_regressed_count(tmp_path):
    registry = _write_registry(tmp_path, _EMPTY_REGISTRY)
    baseline = _write_baseline(tmp_path, 2)
    code, msg = run_check(registry, baseline, repo_root=tmp_path)
    assert code == 2
    assert "regressed" in msg
    assert "baseline=2" in msg


def test_run_check_fails_on_missing_prereg_path(tmp_path):
    body = textwrap.dedent(
        """\
        schema_version: 1
        protocol: docs/REPLICATION_PROTOCOL.md
        replications:
          - id: test-rep
            date: 2026-05-01
            substrate_class: simulated_agent
            lab: internal
            prereg_path: evidence/replications/test-rep/does_not_exist.yaml
            verdict: pending
            commit_sha: 0000000000000000000000000000000000000000
            claim_tested: test claim
            interpretation_boundary: test boundary
        """
    )
    registry = _write_registry(tmp_path, body)
    baseline = _write_baseline(tmp_path, 0)
    code, msg = run_check(registry, baseline, repo_root=tmp_path)
    assert code == 2
    assert "prereg_path" in msg
    assert "missing" in msg


def test_run_check_fails_on_bad_verdict(tmp_path):
    # Create a prereg stub so path existence passes and verdict is the
    # only failure surface.
    prereg_dir = tmp_path / "evidence/replications/test-rep"
    prereg_dir.mkdir(parents=True)
    (prereg_dir / "prereg.yaml").write_text("stub\n", encoding="utf-8")

    body = textwrap.dedent(
        """\
        schema_version: 1
        protocol: docs/REPLICATION_PROTOCOL.md
        replications:
          - id: test-rep
            date: 2026-05-01
            substrate_class: simulated_agent
            lab: internal
            prereg_path: evidence/replications/test-rep/prereg.yaml
            verdict: maybe
            commit_sha: 0000000000000000000000000000000000000000
            claim_tested: test claim
            interpretation_boundary: test boundary
        """
    )
    registry = _write_registry(tmp_path, body)
    baseline = _write_baseline(tmp_path, 0)
    code, msg = run_check(registry, baseline, repo_root=tmp_path)
    assert code == 2
    assert "verdict" in msg


def test_run_check_fails_on_bad_substrate_class(tmp_path):
    prereg_dir = tmp_path / "evidence/replications/test-rep"
    prereg_dir.mkdir(parents=True)
    (prereg_dir / "prereg.yaml").write_text("stub\n", encoding="utf-8")

    body = textwrap.dedent(
        """\
        schema_version: 1
        protocol: docs/REPLICATION_PROTOCOL.md
        replications:
          - id: test-rep
            date: 2026-05-01
            substrate_class: llm_stateless
            lab: internal
            prereg_path: evidence/replications/test-rep/prereg.yaml
            verdict: pending
            commit_sha: 0000000000000000000000000000000000000000
            claim_tested: test claim
            interpretation_boundary: test boundary
        """
    )
    registry = _write_registry(tmp_path, body)
    baseline = _write_baseline(tmp_path, 0)
    code, msg = run_check(registry, baseline, repo_root=tmp_path)
    assert code == 2
    assert "substrate_class" in msg


def test_run_check_fails_on_missing_required_key(tmp_path):
    prereg_dir = tmp_path / "evidence/replications/test-rep"
    prereg_dir.mkdir(parents=True)
    (prereg_dir / "prereg.yaml").write_text("stub\n", encoding="utf-8")

    body = textwrap.dedent(
        """\
        schema_version: 1
        protocol: docs/REPLICATION_PROTOCOL.md
        replications:
          - id: test-rep
            date: 2026-05-01
            substrate_class: simulated_agent
            prereg_path: evidence/replications/test-rep/prereg.yaml
            verdict: pending
            commit_sha: 0000000000000000000000000000000000000000
            claim_tested: test claim
        """
    )
    registry = _write_registry(tmp_path, body)
    baseline = _write_baseline(tmp_path, 0)
    code, msg = run_check(registry, baseline, repo_root=tmp_path)
    assert code == 2
    assert "missing keys" in msg


def test_run_check_passes_on_valid_single_entry(tmp_path):
    prereg_dir = tmp_path / "evidence/replications/test-rep"
    prereg_dir.mkdir(parents=True)
    (prereg_dir / "prereg.yaml").write_text("stub\n", encoding="utf-8")

    body = textwrap.dedent(
        """\
        schema_version: 1
        protocol: docs/REPLICATION_PROTOCOL.md
        replications:
          - id: test-rep
            date: 2026-05-01
            substrate_class: simulated_agent
            lab: internal
            prereg_path: evidence/replications/test-rep/prereg.yaml
            verdict: pending
            commit_sha: 0000000000000000000000000000000000000000
            claim_tested: test claim, minimum admissible form
            interpretation_boundary: does not license generalisation
        """
    )
    registry = _write_registry(tmp_path, body)
    baseline = _write_baseline(tmp_path, 1)
    code, msg = run_check(registry, baseline, repo_root=tmp_path)
    assert code == 0, msg
    assert "1 replication" in msg


# ---------------------------------------------------------------------------
# Live repo invariant
# ---------------------------------------------------------------------------


def test_repo_canonical_state_passes_ratchet():
    code, msg = run_check()
    assert code == 0, msg
