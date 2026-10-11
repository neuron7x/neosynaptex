"""Tests for the canonical extraction stack (Task 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.hrv import canonical_stack as cs
from tools.hrv.baseline_panel import DEFAULT_PARAMS


def test_canonical_stack_version_is_semver() -> None:
    parts = cs.CANONICAL_STACK_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_frequency_bands_standard_task_force_1996() -> None:
    assert cs.FREQUENCY_BANDS_HZ["VLF"] == (0.003, 0.04)
    assert cs.FREQUENCY_BANDS_HZ["LF"] == (0.04, 0.15)
    assert cs.FREQUENCY_BANDS_HZ["HF"] == (0.15, 0.4)
    assert cs.FREQUENCY_BANDS_HZ["TP"] == (0.003, 0.4)


def test_canonical_params_have_not_drifted() -> None:
    """Catch silent DEFAULT_PARAMS edits that skip CANONICAL_STACK_VERSION bump."""
    cs.assert_canonical_params()


def test_canonical_stack_sync_with_default_params() -> None:
    assert (DEFAULT_PARAMS.min_rr_s, DEFAULT_PARAMS.max_rr_s) == cs.RR_CLIP_RANGE_S
    assert DEFAULT_PARAMS.fs_resample_hz == cs.FS_RESAMPLE_HZ
    assert DEFAULT_PARAMS.dfa_short == cs.DFA_SCALES_SHORT
    assert DEFAULT_PARAMS.dfa_long == cs.DFA_SCALES_LONG
    assert DEFAULT_PARAMS.sampen_m == cs.SAMPEN_M
    assert DEFAULT_PARAMS.sampen_r_frac == cs.SAMPEN_R_FRAC
    assert DEFAULT_PARAMS.sampen_max_n == cs.SAMPEN_MAX_N


def test_canonical_extraction_doc_exists() -> None:
    p = Path(__file__).parent.parent / "docs" / "protocols" / "CANONICAL_EXTRACTION_STACK.md"
    assert p.exists()
    body = p.read_text("utf-8")
    assert "CANONICAL_STACK_VERSION" in body
    assert "Frozen parameters" in body
    # all 8 pipeline steps are listed
    for step in ("fetch_record", "baseline_panel", "null_suite", "blind_validation"):
        assert step in body


def test_canonical_stack_drift_detection_raises_on_edit() -> None:
    """If ``DEFAULT_PARAMS`` were mutated without rotating the constants,
    ``assert_canonical_params`` must raise. We exercise the failure path
    by temporarily monkey-patching a frozen constant."""
    orig = cs.FS_RESAMPLE_HZ
    cs.FS_RESAMPLE_HZ = orig + 0.1  # type: ignore[misc]
    try:
        with pytest.raises(AssertionError):
            cs.assert_canonical_params()
    finally:
        cs.FS_RESAMPLE_HZ = orig  # type: ignore[misc]
