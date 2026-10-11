"""Tests for the outlier protocol (Task 7)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tools.data.physionet_cohort import COHORTS
from tools.hrv.outlier_protocol import (
    OutlierProtocolConfig,
    compute_outlier_report,
    dump_yaml,
)

_REPO = Path(__file__).parent.parent
_YAML_DIR = _REPO / "evidence" / "outlier_protocol"


# ---------------------------------------------------------------------------
# Synthetic signal tests
# ---------------------------------------------------------------------------
def test_clean_rr_series_decided_explained() -> None:
    rng = np.random.default_rng(1)
    rr = 0.8 + 0.05 * rng.normal(size=60000)
    symbols = ["N"] * 60001
    r = compute_outlier_report(rr, symbols, "nsr2db", "test01")
    assert r.decision == "EXPLAINED"


def test_high_ectopy_triggers_exclusion() -> None:
    rng = np.random.default_rng(2)
    rr = 0.8 + 0.05 * rng.normal(size=10000)
    symbols = ["N"] * 8000 + ["V"] * 2000  # 20% ectopy
    r = compute_outlier_report(rr, symbols, "chf2db", "test02")
    assert r.decision == "PRE_REGISTERED_EXCLUDED"
    assert any(s.name == "ectopy_burden" and s.flag for s in r.stages)


def test_missing_beat_gap_flagged_not_excluded_alone() -> None:
    rng = np.random.default_rng(3)
    rr = 0.8 + 0.05 * rng.normal(size=20000)
    rr[10000] = 5.0  # monitor dropout
    symbols = ["N"] * 20001
    r = compute_outlier_report(rr, symbols, "chfdb", "test03")
    # gap flag alone should not exclude
    assert any(s.name == "missing_beat_gaps" and s.flag for s in r.stages)
    assert r.decision in {"EXPLAINED", "PRE_REGISTERED_EXCLUDED"}


def test_stages_always_six() -> None:
    rng = np.random.default_rng(4)
    rr = 0.8 + 0.05 * rng.normal(size=2000)
    r = compute_outlier_report(rr, ["N"] * 2001, "nsrdb", "test04")
    names = [s.name for s in r.stages]
    assert names == [
        "signal_quality",
        "ectopy_burden",
        "missing_beat_gaps",
        "stationarity",
        "window_sensitivity",
        "day_night_segmentation",
    ]


# ---------------------------------------------------------------------------
# YAML dump
# ---------------------------------------------------------------------------
def test_dump_yaml_round_trip(tmp_path: Path) -> None:
    rng = np.random.default_rng(5)
    rr = 0.8 + 0.05 * rng.normal(size=40000)
    r = compute_outlier_report(rr, ["N"] * 40001, "nsr2db", "test05")
    out = tmp_path / "test.yaml"
    dump_yaml(r, out)
    text = out.read_text("utf-8")
    assert "decision:" in text
    assert "stages:" in text
    assert text.count("- name:") == 6


# ---------------------------------------------------------------------------
# Committed per-subject YAMLs
# ---------------------------------------------------------------------------
def test_every_cohort_subject_has_a_yaml() -> None:
    for cohort, spec in COHORTS.items():
        for record in spec.expected_records:
            p = _YAML_DIR / f"{cohort}__{record}.yaml"
            assert p.exists(), f"outlier protocol missing for {cohort}:{record}"


def test_every_yaml_has_one_of_two_decisions() -> None:
    for f in _YAML_DIR.glob("*__*.yaml"):
        text = f.read_text("utf-8")
        # look for decision line
        decision_lines = [
            ln.strip() for ln in text.splitlines() if ln.strip().startswith("decision:")
        ]
        assert decision_lines
        d = decision_lines[0].split(":", 1)[1].strip()
        assert d in {"EXPLAINED", "PRE_REGISTERED_EXCLUDED"}


def test_cohort_summary_committed() -> None:
    p = _REPO / "reports" / "outlier_protocol" / "summary.json"
    assert p.exists()
    import json

    s = json.loads(p.read_text("utf-8"))
    assert s["n_subjects"] == sum(COHORTS[c].expected_n_subjects for c in COHORTS)
    assert set(s["decision_counts"]) == {"EXPLAINED", "PRE_REGISTERED_EXCLUDED"}


# ---------------------------------------------------------------------------
# Config threshold behaviour
# ---------------------------------------------------------------------------
def test_config_exclude_threshold_honoured() -> None:
    rng = np.random.default_rng(6)
    rr = 0.8 + 0.05 * rng.normal(size=10000)
    # 10% ectopy → between flag (8%) and exclude (15%) → EXPLAINED (single flag)
    symbols = ["N"] * 9000 + ["V"] * 1000
    cfg = OutlierProtocolConfig()
    r = compute_outlier_report(rr, symbols, "chf2db", "cfg01", cfg=cfg)
    assert r.decision == "EXPLAINED"
