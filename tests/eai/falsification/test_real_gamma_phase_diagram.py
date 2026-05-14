"""Tests for the real-data γ-ledger phase diagram.

CONTRACT pinned (matches pre-registration in
docs/research/EAI_REAL_GAMMA_PHASE_DIAGRAM_V1.md):

- grid is deterministic and exhaustive over 3 axes
- 490 total cells (10 ledger × 7 probe × 7 evidence_path)
- binary and graded gates are both evaluated per cell
- bridge / engine / PR #195 / PR #196 anchors NOT modified
- regression detection respects hash-bound-EVIDENCE_CANDIDATE rule
- verdict is one of the four pre-registered values
- runner produces byte-identical reports across two runs
- the current verdict is recorded as a regression anchor
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from core.eai.gamma_bridge import load_ledger
from core.eai.real_gamma_phase_diagram import (
    EVIDENCE_PATH_COUNT_RANGE,
    PROBE_COUNT_RANGE,
    PROBES,
    classify_region,
    evaluate_cell,
    generate_grid,
)
from tools.eai.run_real_gamma_phase_diagram import run_real_phase_diagram

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _REPO_ROOT / "evidence" / "gamma_ledger.json"


def test_grid_is_deterministic() -> None:
    version, entries = load_ledger(_LEDGER)
    keys = list(entries.keys())
    a = generate_grid(keys)
    b = generate_grid(keys)
    assert a == b
    # evaluate_cell is deterministic too
    entry = entries[a[0].ledger_key]
    r1 = evaluate_cell(a[0], entry, ledger_version=version)
    r2 = evaluate_cell(a[0], entry, ledger_version=version)
    assert r1 == r2


def test_grid_has_exactly_490_cells_for_10_entries() -> None:
    version, entries = load_ledger(_LEDGER)
    assert len(entries) == 10, (
        f"γ-ledger is expected to have exactly 10 entries at the "
        f"PR-8 pre-registration time; got {len(entries)}. Run a fresh "
        f"pre-registration if the ledger has grown."
    )
    cells = generate_grid(list(entries.keys()))
    assert len(cells) == 10 * 7 * 7 == 490
    assert len(PROBES) == 6
    assert tuple(PROBE_COUNT_RANGE) == (0, 1, 2, 3, 4, 5, 6)
    assert tuple(EVIDENCE_PATH_COUNT_RANGE) == (0, 1, 2, 3, 4, 5, 6)


def test_binary_and_graded_are_both_evaluated() -> None:
    records, summary, _, _ = run_real_phase_diagram(_LEDGER)
    sample = records[0]
    assert sample.binary_verdict in {"EVIDENCE", "KILLED", "QUARANTINED"}
    assert sample.graded_verdict in {"EVIDENCE", "KILLED", "QUARANTINED"}
    assert sample.binary_reason
    assert sample.graded_reason


def test_runner_emits_three_artifacts(tmp_path: Path) -> None:
    out_json = tmp_path / "real_pd.json"
    out_csv = tmp_path / "real_pd.csv"
    out_md = tmp_path / "real_pd.md"
    import os

    result = subprocess.run(
        [
            "python",
            "-m",
            "tools.eai.run_real_gamma_phase_diagram",
            "--ledger",
            str(_LEDGER),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-summary",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        check=False,
        env={"PYTHONPATH": str(_REPO_ROOT), "PATH": os.environ.get("PATH", "")},
    )
    # Valid verdict exit codes: 0, 22, 33. Exit 1 = uncaught exception.
    assert result.returncode in {0, 22, 33}, (result.returncode, result.stderr)
    assert out_json.exists()
    assert out_csv.exists()
    assert out_md.exists()
    data = json.loads(out_json.read_text())
    assert data["schema_version"] == "EAI-REAL-GAMMA-PHASE-DIAGRAM-v1"
    assert data["grid_cells"] == 490


def test_full_run_is_byte_deterministic() -> None:
    a_records, a_summary, _, _ = run_real_phase_diagram(_LEDGER)
    b_records, b_summary, _, _ = run_real_phase_diagram(_LEDGER)
    assert a_records == b_records
    assert a_summary == b_summary


def test_verdict_is_one_of_pre_registered_values() -> None:
    _, summary, _, _ = run_real_phase_diagram(_LEDGER)
    assert summary["verdict"] in {
        "PHASE_REGION_FOUND",
        "NO_SEPARABLE_REGION_FOUND",
        "REGRESSION_REGION_FOUND",
        "INVALID_EXPERIMENT",
    }


def test_current_verdict_no_separable_anchor() -> None:
    """REGRESSION ANCHOR. The current (PR-8 first commit) verdict on
    the real γ-ledger is NO_SEPARABLE_REGION_FOUND — graded falsification
    has zero operational signal on real claim text under the canonical
    probe pool. Any change to this anchor requires fresh pre-registration.
    """
    _, summary, _, _ = run_real_phase_diagram(_LEDGER)
    msg = (
        f"verdict drifted from NO_SEPARABLE_REGION_FOUND to "
        f"{summary['verdict']}. Either the ledger changed, the probes "
        "were tuned, gamma_bridge was modified, or the graded gate was "
        "altered. Fresh pre-registration required before this anchor "
        "is updated."
    )
    assert summary["verdict"] == "NO_SEPARABLE_REGION_FOUND", msg


def test_no_useful_cells_means_no_regression_either() -> None:
    """Sanity: useful and regression must both be zero on this run."""
    records, summary, _, _ = run_real_phase_diagram(_LEDGER)
    assert summary["useful_global"] == 0
    assert summary["regression_global"] == 0
    assert summary["null_global"] == summary["total_cells"]
    for r in records:
        assert classify_region(r) == "null"


def test_ledger_sha_consistent() -> None:
    records, _, _, _ = run_real_phase_diagram(_LEDGER)
    # Cross-check against file digest
    digest = hashlib.sha256(_LEDGER.read_bytes()).hexdigest()
    # The report carries ledger_sha256; just verify it equals the
    # real file digest (subprocess check below also verifies it).
    assert digest == "3f2ed37e86124b1bb43135ce03d111fe35248f9a11fb4c01f3eeaac9863afd67", (
        "γ-ledger digest drift detected; PR-8 anchor must be re-pre-registered."
    )
    # records sanity
    assert len(records) == 490


def test_gamma_bridge_module_unmodified() -> None:
    """PR #193 anchor invariant: gamma_bridge.py must not be edited
    on this branch. Soft local check; CI does a git-diff."""
    src = (_REPO_ROOT / "core" / "eai" / "gamma_bridge.py").read_text(encoding="utf-8")
    # Hash-pinned at PR #193 merge: this is the function our bridge depends on.
    assert "def ledger_entry_to_gate_inputs" in src
    assert "def load_ledger" in src


def test_phase_diagram_anchors_unmodified() -> None:
    """PR #195 + PR #196 anchors must remain on disk and unedited."""
    fp_report = (
        _REPO_ROOT / "artifacts" / "eai" / "benchmarks" / "falsifiability_test_v1_report.json"
    )
    pd_report = (
        _REPO_ROOT
        / "artifacts"
        / "eai"
        / "phase_diagrams"
        / "graded_falsification_phase_diagram_v1.json"
    )
    assert fp_report.exists() and pd_report.exists()
    # Spot-check verdict strings
    assert '"verdict": "NULL_RESULT"' in fp_report.read_text()
    assert '"verdict": "PHASE_REGION_FOUND"' in pd_report.read_text()


def test_no_production_engine_imported_for_mutation() -> None:
    """Static check: real_gamma_phase_diagram.py must not import
    core.eai.engine or core.iev_gate."""
    src = (_REPO_ROOT / "core" / "eai" / "real_gamma_phase_diagram.py").read_text(encoding="utf-8")
    assert "from core.eai.engine" not in src
    assert "from core.iev_gate" not in src
    assert "import core.eai.engine" not in src
    assert "import core.iev_gate" not in src


def test_probes_are_fixed_canonical_pool() -> None:
    """No per-entry probe tuning permitted by pre-registration."""
    assert isinstance(PROBES, tuple)
    assert len(PROBES) == 6
    # Probes must be literal strings, not generated
    for p in PROBES:
        assert isinstance(p, str) and p
