"""Tests for the STN-analog falsifiability experiment.

CONTRACT pinned:
- v1_1 dataset has 150 rows: 120 from v1 + 20 subtle KILL + 10 negative-control EVIDENCE
- runner produces deterministic byte-identical reports across two runs
- verdict is one of {HYPOTHESIS_SUPPORTED, HYPOTHESIS_FALSIFIED, NULL_RESULT}
- if SUPPORTED: graded.true_positive_evidence == binary.true_positive_evidence
- the experiment is PRE-REGISTERED: this test does NOT permit
  the verdict to be tuned via post-hoc constant adjustment.
  The verdict on the current ledger state is recorded here as a
  regression anchor — changing it requires a fresh, documented
  pre-registration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.eai.run_falsifiability_test import run_falsifiability_test

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATASET = _REPO_ROOT / "data" / "eai_calibration" / "false_promotion_benchmark_v1_1.jsonl"


def _load_rows() -> list[dict[str, object]]:
    return [json.loads(s) for s in _DATASET.read_text(encoding="utf-8").splitlines() if s.strip()]


def test_dataset_has_150_rows() -> None:
    rows = _load_rows()
    assert len(rows) == 150


def test_subtle_slice_has_20_kill_and_10_negative_control_evidence() -> None:
    rows = _load_rows()
    subtle_kill = [
        r
        for r in rows
        if r.get("subtle") and not r.get("negative_control") and r["expected_status"] == "KILLED"
    ]
    neg_evidence = [
        r
        for r in rows
        if r.get("subtle") and r.get("negative_control") and r["expected_status"] == "EVIDENCE"
    ]
    assert len(subtle_kill) == 20
    assert len(neg_evidence) == 10


def test_experiment_is_deterministic_across_two_runs() -> None:
    a = run_falsifiability_test(_DATASET)
    b = run_falsifiability_test(_DATASET)
    # Audit-identity fields must be byte-identical
    for k in (
        "schema_version",
        "dataset_sha256",
        "total_rows",
        "binary",
        "graded",
        "verdict",
        "verdict_reason",
        "per_row_binary",
        "per_row_graded",
    ):
        assert a[k] == b[k], f"non-deterministic field: {k}"


def test_verdict_is_one_of_three_canonical_values() -> None:
    report = run_falsifiability_test(_DATASET)
    assert report["verdict"] in {
        "HYPOTHESIS_SUPPORTED",
        "HYPOTHESIS_FALSIFIED",
        "NULL_RESULT",
    }


def test_no_false_kill_on_evidence_slice() -> None:
    """Graded gate MUST NOT regress true evidence to KILLED.

    This is the hard floor — if it ever fires, the verdict is
    FALSIFIED and the graded gate must be reverted (per
    pre-registered task order, ABORT_PR6_FALSIFIED).
    """
    report = run_falsifiability_test(_DATASET)
    assert (
        report["graded"]["true_positive_evidence"] >= report["binary"]["true_positive_evidence"]
    ), (
        "graded gate regressed true evidence — STN-analog hypothesis FALSIFIED; "
        f"binary TP={report['binary']['true_positive_evidence']}, "
        f"graded TP={report['graded']['true_positive_evidence']}"
    )


def test_current_verdict_is_null_result_regression_anchor() -> None:
    """REGRESSION ANCHOR.

    On the current ledger state (constants +0.4 / +0.15, threshold
    ceil(1 + c*2), available_paths=2), the experiment produces
    NULL_RESULT — no measurable improvement on the subtle slice.

    This is the HONEST FINDING preserved as artifact under
    [[feedback_failure_signal_priority]]. Changing this anchor
    requires:
      1. A fresh pre-registration document with new constants.
      2. A new experiment run with updated dataset or threshold.
      3. Operator authorization.

    Naked constant tuning to chase HYPOTHESIS_SUPPORTED is forbidden
    by the task order rule "do not adjust constants to chase
    SUPPORTED".
    """
    report = run_falsifiability_test(_DATASET)
    assert report["verdict"] == "NULL_RESULT", (
        f"Verdict drifted from NULL_RESULT to {report['verdict']}. "
        "Either the dataset changed, the graded constants were tuned, "
        "or the threshold rule was modified. A fresh pre-registration "
        "is required before this regression-anchor is updated."
    )


def test_dataset_sha256_is_real_file_digest() -> None:
    report = run_falsifiability_test(_DATASET)
    expected = hashlib.sha256(_DATASET.read_bytes()).hexdigest()
    assert report["dataset_sha256"] == expected


def test_per_row_binary_and_graded_have_same_length() -> None:
    report = run_falsifiability_test(_DATASET)
    assert len(report["per_row_binary"]) == len(report["per_row_graded"]) == report["total_rows"]


def test_binary_substring_gate_misses_subtle_slice() -> None:
    """Construction-test: substring-only gate MUST miss almost all
    subtle-slice KILL rows (that's the definition of the slice).
    This protects against accidental full-substring contamination
    of the subtle rows.
    """
    report = run_falsifiability_test(_DATASET)
    binary_subtle_promo = report["binary"]["subtle_slice_false_promotion"]
    subtle_total = report["binary"]["subtle_slice_total"]
    # We allow up to 1 accidental substring match; if more leak, the
    # dataset construction is broken.
    assert subtle_total - binary_subtle_promo <= 1, (
        f"binary substring gate caught {subtle_total - binary_subtle_promo} of "
        f"{subtle_total} subtle rows — slice is not subtle enough; "
        "rebuild dataset"
    )


def test_negative_controls_pass_in_both_modes() -> None:
    report = run_falsifiability_test(_DATASET)
    assert report["binary"]["negative_control_passed_as_evidence"] == 10
    assert report["graded"]["negative_control_passed_as_evidence"] == 10
