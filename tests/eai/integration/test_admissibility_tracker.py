"""Tests for the longitudinal admissibility tracker.

Pinned invariants:
- A fresh history is seeded with verdict ``first_row``, no regression.
- Re-running with identical inputs produces no regression (same
  ledger_sha256 + bridge_module_sha256 → deterministic match).
- A synthetic decrease in admissibility_rate triggers regression.
- A synthetic increase in admissibility_rate is permitted (monotone
  non-decreasing).
- Determinism drift (same input hashes, different rate) is treated
  as regression (data corruption / gate change).
- The history-digest function ignores the wall-clock ``recorded_at``
  field so audit identity is rate-and-input-only.
- The CLI exit code is 2 on regression iff ``--check-regression`` is set.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.eai.track_admissibility import (
    _build_row,
    _check_regression,
    append_row,
    compute_history_digest,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _REPO_ROOT / "evidence" / "gamma_ledger.json"
_BRIDGE_MODULE = _REPO_ROOT / "core" / "eai" / "gamma_bridge.py"


def _fresh_history(tmp_path: Path) -> Path:
    return tmp_path / "admissibility_history.jsonl"


def test_first_row_is_seeded_without_regression(tmp_path: Path) -> None:
    history = _fresh_history(tmp_path)
    row = _build_row(_LEDGER, _BRIDGE_MODULE)
    is_regression, reason = append_row(history, row, check_regression=True)
    assert not is_regression
    assert reason == "first_row"
    rows = [json.loads(line) for line in history.read_text().splitlines() if line]
    assert len(rows) == 1
    assert rows[0]["admissibility_rate"] == row["admissibility_rate"]


def test_repeated_same_input_run_is_deterministic_match(tmp_path: Path) -> None:
    history = _fresh_history(tmp_path)
    row1 = _build_row(_LEDGER, _BRIDGE_MODULE)
    append_row(history, row1, check_regression=True)
    row2 = _build_row(_LEDGER, _BRIDGE_MODULE)
    is_regression, reason = append_row(history, row2, check_regression=True)
    assert not is_regression
    assert reason == "deterministic_match_prior"


def test_synthetic_regression_is_detected(tmp_path: Path) -> None:
    history = _fresh_history(tmp_path)
    base = _build_row(_LEDGER, _BRIDGE_MODULE)
    append_row(history, base, check_regression=True)

    regressed = dict(base)
    regressed["ledger_sha256"] = "b" * 64  # different inputs → not the same-input branch
    regressed["bridge_module_sha256"] = "c" * 64
    regressed["admissibility_rate"] = base["admissibility_rate"] - 0.01

    is_regression, reason = append_row(history, regressed, check_regression=True)
    assert is_regression
    assert "regression" in reason


def test_synthetic_improvement_is_permitted(tmp_path: Path) -> None:
    history = _fresh_history(tmp_path)
    base = _build_row(_LEDGER, _BRIDGE_MODULE)
    append_row(history, base, check_regression=True)

    improved = dict(base)
    improved["ledger_sha256"] = "d" * 64
    improved["bridge_module_sha256"] = "e" * 64
    improved["admissibility_rate"] = min(1.0, base["admissibility_rate"] + 0.05)

    is_regression, reason = append_row(history, improved, check_regression=True)
    assert not is_regression
    assert reason == "non_decreasing_rate"


def test_determinism_drift_is_treated_as_regression(tmp_path: Path) -> None:
    history = _fresh_history(tmp_path)
    base = _build_row(_LEDGER, _BRIDGE_MODULE)
    append_row(history, base, check_regression=True)

    # Same inputs hashes but mutated rate ⇒ determinism drift
    drift = dict(base)
    drift["admissibility_rate"] = base["admissibility_rate"] - 0.05

    is_regression, reason = append_row(history, drift, check_regression=True)
    assert is_regression
    assert "determinism drift" in reason


def test_check_regression_pure_function() -> None:
    base = {
        "ledger_sha256": "a" * 64,
        "bridge_module_sha256": "b" * 64,
        "admissibility_rate": 0.5,
    }
    # First row
    is_reg, _ = _check_regression([], base)
    assert not is_reg

    # Same inputs, same rate → match
    is_reg, reason = _check_regression([base], dict(base))
    assert not is_reg and reason == "deterministic_match_prior"

    # Same inputs, different rate → drift
    drifted = dict(base)
    drifted["admissibility_rate"] = 0.4
    is_reg, reason = _check_regression([base], drifted)
    assert is_reg and "determinism drift" in reason

    # Different inputs, lower rate → regression
    different = {
        "ledger_sha256": "c" * 64,
        "bridge_module_sha256": "d" * 64,
        "admissibility_rate": 0.4,
    }
    is_reg, reason = _check_regression([base], different)
    assert is_reg and "regression" in reason

    # Different inputs, higher rate → ok
    better = dict(different)
    better["admissibility_rate"] = 0.6
    is_reg, reason = _check_regression([base], better)
    assert not is_reg and reason == "non_decreasing_rate"


def test_rollback_to_older_inputs_with_lower_rate_is_regression() -> None:
    """Regression: same-input determinism check must NOT bypass the
    monotone-vs-recent guard. Reverting code/data to an older hash
    pair whose recorded rate sits below the most-recent committed
    rate must be flagged.

    Scenario:
      row1 (inputs A, rate 0.30) — older legitimate measurement
      row2 (inputs B, rate 0.50) — most recent committed
      new  (inputs A, rate 0.30) — rollback to A; same-inputs match
                                  exists in history, but 0.30 < 0.50.
    """

    row_a = {
        "ledger_sha256": "a" * 64,
        "bridge_module_sha256": "a" * 64,
        "admissibility_rate": 0.30,
    }
    row_b = {
        "ledger_sha256": "b" * 64,
        "bridge_module_sha256": "b" * 64,
        "admissibility_rate": 0.50,
    }
    rollback = dict(row_a)  # inputs A again, rate 0.30
    is_reg, reason = _check_regression([row_a, row_b], rollback)
    assert is_reg, "rollback to A with rate < most-recent must be regression"
    assert "regression vs most-recent" in reason


def test_same_input_same_rate_with_newer_lower_recent_is_accepted() -> None:
    """Edge case: if the most-recent row has a LOWER rate than the
    same-inputs match (which should not normally happen, since
    history is monotone non-decreasing), the same-inputs determinism
    path still permits an exact rate match because the rate equals
    the same-inputs row.
    """

    row_a = {
        "ledger_sha256": "a" * 64,
        "bridge_module_sha256": "a" * 64,
        "admissibility_rate": 0.50,
    }
    # Most-recent row with lower rate (pathological history)
    row_recent = {
        "ledger_sha256": "b" * 64,
        "bridge_module_sha256": "b" * 64,
        "admissibility_rate": 0.45,
    }
    new = dict(row_a)  # rate 0.50, ≥ 0.45 so guard 2 is satisfied
    is_reg, reason = _check_regression([row_a, row_recent], new)
    assert not is_reg
    assert reason == "deterministic_match_prior"


def test_compute_history_digest_ignores_recorded_at() -> None:
    row_a = {
        "ledger_sha256": "a" * 64,
        "admissibility_rate": 0.5,
        "recorded_at": "2026-05-13T16:00:00+00:00",
    }
    row_b = {
        "ledger_sha256": "a" * 64,
        "admissibility_rate": 0.5,
        "recorded_at": "2030-12-31T23:59:59+00:00",
    }
    assert compute_history_digest([row_a]) == compute_history_digest([row_b])


def test_history_digest_changes_when_rate_changes() -> None:
    a = {"ledger_sha256": "a" * 64, "admissibility_rate": 0.5}
    b = {"ledger_sha256": "a" * 64, "admissibility_rate": 0.6}
    assert compute_history_digest([a]) != compute_history_digest([b])


def test_cli_exits_2_on_regression(tmp_path: Path) -> None:
    history = tmp_path / "h.jsonl"
    # Seed with high prior so a real run regresses
    history.write_text(
        json.dumps(
            {
                "schema_version": "EAI-GAMMA-ADMISSIBILITY-HISTORY-v1",
                "recorded_at": "2026-05-13T15:00:00+00:00",
                "ledger_path": "evidence/gamma_ledger.json",
                "ledger_version": "9.9.9-synthetic",
                "ledger_sha256": "9" * 64,
                "bridge_module_sha256": "9" * 64,
                "total_entries": 10,
                "gate_verdict_counts": {"EVIDENCE": 10},
                "hash_bound_count": 10,
                "candidate_total": 10,
                "admissible_evidence": 10,
                "admissibility_rate": 1.0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.eai.track_admissibility",
            "--history",
            str(history),
            "--check-regression",
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        check=False,
    )
    assert result.returncode == 2, (result.stdout, result.stderr)
    # The forensic row should still be appended
    lines = history.read_text().splitlines()
    assert len(lines) == 2
