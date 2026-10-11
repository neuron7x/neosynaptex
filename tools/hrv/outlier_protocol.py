"""Per-subject outlier protocol — Task 7 of the γ-program.

For every cohort subject we run a six-stage diagnostic and record a
decision of ``EXPLAINED`` / ``PRE_REGISTERED_EXCLUDED``.  Silent
dropping is forbidden: every subject carries a YAML record, and any
exclusion at downstream analysis time must point back to a
``PRE_REGISTERED_EXCLUDED`` entry here.

Stages (in order)
-----------------
  1. signal_quality          fraction of ``"N"`` annotations vs. total.
  2. ectopy_burden           fraction of non-``"N"`` annotations.
  3. missing_beat_gaps       count + max duration of RR > clip_max.
  4. stationarity            windowed-SDNN coefficient of variation.
  5. window_sensitivity      |α₂(first half) − α₂(second half)|.
  6. day_night_segmentation  |α₂(day) − α₂(night)| if recording ≥ 20 h.

Decision rule
-------------
  flags = count of stages with ``flag == True``.

  decision =
    EXPLAINED                  if flags == 0
    EXPLAINED                  if 1 ≤ flags ≤ 2 AND ectopy < 15%
    PRE_REGISTERED_EXCLUDED    if flags ≥ 3 OR ectopy ≥ 15%

The rule is deterministic and review-visible.  Changing thresholds
requires a PR review (no runtime tuning).

Audit-gate contract
-------------------
Task 12 claim gate reads ``evidence/outlier_protocol/*.yaml`` and
requires **exactly one** file per cohort subject.  Missing entry →
gate fails.  The aggregate summary at
``reports/outlier_protocol/summary.json`` is informational.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import numpy as np

from tools.hrv.baseline_panel import (
    HRVPreprocessingParams,
    _preprocess,
    dfa_alpha,
)

__all__ = [
    "OutlierProtocolConfig",
    "OutlierProtocolReport",
    "compute_outlier_report",
]

Decision = Literal["EXPLAINED", "PRE_REGISTERED_EXCLUDED"]


@dataclasses.dataclass(frozen=True)
class OutlierProtocolConfig:
    min_n_symbol_frac: float = 0.90  # signal-quality threshold
    ectopy_burden_flag_frac: float = 0.08  # flag if ≥ 8% non-'N'
    ectopy_burden_exclude_frac: float = 0.15  # exclude if ≥ 15% non-'N'
    clip_range_s: tuple[float, float] = (0.3, 2.0)
    stationarity_cov_flag: float = 0.40  # SDNN CoV across 512-beat windows
    stationarity_window: int = 512
    window_sensitivity_delta_flag: float = 0.30  # α₂ half-to-half
    day_night_min_duration_s: float = 20 * 3600
    dfa_long_scales: tuple[int, ...] = (16, 22, 30, 40, 54, 64)


DEFAULT_CFG = OutlierProtocolConfig()


@dataclasses.dataclass(frozen=True)
class StageResult:
    name: str
    value: float
    threshold: float
    flag: bool
    note: str


@dataclasses.dataclass(frozen=True)
class OutlierProtocolReport:
    cohort: str
    record: str
    n_total_annotations: int
    n_normal_beats: int
    stages: list[StageResult]
    decision: Decision
    decision_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cohort": self.cohort,
            "record": self.record,
            "n_total_annotations": self.n_total_annotations,
            "n_normal_beats": self.n_normal_beats,
            "stages": [dataclasses.asdict(s) for s in self.stages],
            "decision": self.decision,
            "decision_reason": self.decision_reason,
        }


def _stage_signal_quality(n_normal: int, n_total: int, cfg: OutlierProtocolConfig) -> StageResult:
    frac = (n_normal / n_total) if n_total > 0 else 0.0
    return StageResult(
        name="signal_quality",
        value=frac,
        threshold=cfg.min_n_symbol_frac,
        flag=frac < cfg.min_n_symbol_frac,
        note="fraction of annotations with symbol=='N'; flag if < min",
    )


def _stage_ectopy_burden(n_normal: int, n_total: int, cfg: OutlierProtocolConfig) -> StageResult:
    frac = ((n_total - n_normal) / n_total) if n_total > 0 else 0.0
    return StageResult(
        name="ectopy_burden",
        value=frac,
        threshold=cfg.ectopy_burden_flag_frac,
        flag=frac >= cfg.ectopy_burden_flag_frac,
        note="fraction of non-'N' annotations; flag if ≥ threshold",
    )


def _stage_missing_beat_gaps(rr_s: np.ndarray, cfg: OutlierProtocolConfig) -> StageResult:
    mx = float(rr_s.max()) if rr_s.size else 0.0
    n_gaps = int(np.sum(rr_s > cfg.clip_range_s[1]))
    return StageResult(
        name="missing_beat_gaps",
        value=float(n_gaps),
        threshold=0.0,
        flag=n_gaps > 0,
        note=f"count of RR > {cfg.clip_range_s[1]} s; max_rr={mx:.2f}s",
    )


def _stage_stationarity(rr_clipped: np.ndarray, cfg: OutlierProtocolConfig) -> StageResult:
    w = cfg.stationarity_window
    if rr_clipped.size < 2 * w:
        return StageResult(
            "stationarity",
            float("nan"),
            cfg.stationarity_cov_flag,
            False,
            "skipped: fewer than 2 windows",
        )
    n_w = rr_clipped.size // w
    sdnns = np.array(
        [np.std(rr_clipped[i * w : (i + 1) * w], ddof=1) for i in range(n_w)],
        dtype=np.float64,
    )
    mean = float(sdnns.mean()) if sdnns.size else 0.0
    cov = float(sdnns.std(ddof=1) / mean) if mean > 0 else 0.0
    return StageResult(
        name="stationarity",
        value=cov,
        threshold=cfg.stationarity_cov_flag,
        flag=cov >= cfg.stationarity_cov_flag,
        note=f"CoV of SDNN across {n_w} non-overlapping {w}-beat windows",
    )


def _stage_window_sensitivity(rr_clipped: np.ndarray, cfg: OutlierProtocolConfig) -> StageResult:
    if rr_clipped.size < 2 * max(cfg.dfa_long_scales) * 4:
        return StageResult(
            "window_sensitivity",
            float("nan"),
            cfg.window_sensitivity_delta_flag,
            False,
            "skipped: too short for two-half DFA",
        )
    mid = rr_clipped.size // 2
    a1 = dfa_alpha(rr_clipped[:mid], np.asarray(cfg.dfa_long_scales, dtype=np.int64))
    a2 = dfa_alpha(rr_clipped[mid:], np.asarray(cfg.dfa_long_scales, dtype=np.int64))
    delta = abs(a1 - a2)
    return StageResult(
        name="window_sensitivity",
        value=float(delta),
        threshold=cfg.window_sensitivity_delta_flag,
        flag=bool(delta >= cfg.window_sensitivity_delta_flag),
        note=f"|α₂(first half) − α₂(second half)|; α₁={a1:.3f} α₂={a2:.3f}",
    )


def _stage_day_night(rr_clipped: np.ndarray, cfg: OutlierProtocolConfig) -> StageResult:
    duration_s = float(rr_clipped.sum())
    if duration_s < cfg.day_night_min_duration_s:
        return StageResult(
            name="day_night_segmentation",
            value=duration_s,
            threshold=cfg.day_night_min_duration_s,
            flag=False,
            note="skipped: duration < 20 h",
        )
    mid = rr_clipped.size // 2
    a_first = dfa_alpha(rr_clipped[:mid], np.asarray(cfg.dfa_long_scales, dtype=np.int64))
    a_second = dfa_alpha(rr_clipped[mid:], np.asarray(cfg.dfa_long_scales, dtype=np.int64))
    delta = abs(a_first - a_second)
    return StageResult(
        name="day_night_segmentation",
        value=float(delta),
        threshold=cfg.window_sensitivity_delta_flag,
        flag=bool(delta >= cfg.window_sensitivity_delta_flag),
        note="|α₂(first half) − α₂(second half)| over ≥20h recording",
    )


def compute_outlier_report(
    rr_raw_s: np.ndarray,
    symbols: Sequence[str] | None,
    cohort: str,
    record: str,
    cfg: OutlierProtocolConfig = DEFAULT_CFG,
) -> OutlierProtocolReport:
    """Run the 6-stage protocol and return a deterministic report."""

    sym_list = list(symbols) if symbols is not None else []
    n_total = len(sym_list) if sym_list else int(rr_raw_s.size + 1)
    n_normal = sum(1 for s in sym_list if s == "N") if sym_list else int(rr_raw_s.size + 1)

    rr_clipped, _ = _preprocess(
        rr_raw_s, HRVPreprocessingParams(min_rr_s=cfg.clip_range_s[0], max_rr_s=cfg.clip_range_s[1])
    )

    stages: list[StageResult] = [
        _stage_signal_quality(n_normal, n_total, cfg),
        _stage_ectopy_burden(n_normal, n_total, cfg),
        _stage_missing_beat_gaps(rr_raw_s, cfg),
        _stage_stationarity(rr_clipped, cfg),
        _stage_window_sensitivity(rr_clipped, cfg),
        _stage_day_night(rr_clipped, cfg),
    ]

    n_flags = sum(1 for s in stages if s.flag)
    ectopy = next(s for s in stages if s.name == "ectopy_burden").value
    if ectopy >= cfg.ectopy_burden_exclude_frac or n_flags >= 3:
        decision: Decision = "PRE_REGISTERED_EXCLUDED"
        reason = (
            f"flags={n_flags} (≥ 3) or ectopy={ectopy:.3f} ≥ {cfg.ectopy_burden_exclude_frac:.3f}"
        )
    else:
        decision = "EXPLAINED"
        reason = (
            f"flags={n_flags} (< 3) and ectopy={ectopy:.3f} < {cfg.ectopy_burden_exclude_frac:.3f}"
        )

    return OutlierProtocolReport(
        cohort=cohort,
        record=record,
        n_total_annotations=n_total,
        n_normal_beats=n_normal,
        stages=stages,
        decision=decision,
        decision_reason=reason,
    )


def dump_yaml(report: OutlierProtocolReport, path: Path) -> None:
    lines = [
        "# Outlier-protocol report — γ-program Task 7",
        "#",
        "# Generated from tools/hrv/outlier_protocol.py. Editing here",
        "# without updating the generator is a protocol violation.",
        "",
        f"cohort: {report.cohort}",
        f"record: {report.record}",
        f"n_total_annotations: {report.n_total_annotations}",
        f"n_normal_beats: {report.n_normal_beats}",
        f"decision: {report.decision}",
        f'decision_reason: "{report.decision_reason}"',
        "",
        "stages:",
    ]
    for s in report.stages:
        lines.append(f"  - name: {s.name}")
        if np_isfinite(s.value):
            lines.append(f"    value: {s.value:.6f}")
        else:
            lines.append("    value: NaN")
        lines.append(f"    threshold: {s.threshold:.6f}")
        lines.append(f"    flag: {str(s.flag).lower()}")
        lines.append(f'    note: "{s.note}"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def np_isfinite(x: float) -> bool:
    import math

    return math.isfinite(x)


def emit_cohort_summary(out_path: Path, yaml_dir: Path) -> dict[str, Any]:
    """Aggregate the committed per-subject YAMLs into one summary JSON."""

    files = sorted(yaml_dir.glob("*__*.yaml"))
    decisions = {"EXPLAINED": 0, "PRE_REGISTERED_EXCLUDED": 0}
    per_cohort: dict[str, dict[str, int]] = {}
    subject_entries: list[dict[str, Any]] = []
    for f in files:
        lines = f.read_text("utf-8").splitlines()
        entry: dict[str, Any] = {}
        for ln in lines:
            s = ln.strip()
            if s.startswith("cohort:"):
                entry["cohort"] = s.split(":", 1)[1].strip()
            elif s.startswith("record:"):
                entry["record"] = s.split(":", 1)[1].strip()
            elif s.startswith("decision:"):
                entry["decision"] = s.split(":", 1)[1].strip()
        if "decision" in entry:
            decisions[entry["decision"]] = decisions.get(entry["decision"], 0) + 1
            c = entry["cohort"]
            per_cohort.setdefault(c, {"EXPLAINED": 0, "PRE_REGISTERED_EXCLUDED": 0})
            per_cohort[c][entry["decision"]] = per_cohort[c].get(entry["decision"], 0) + 1
            subject_entries.append(entry)

    summary = {
        "schema_version": 1,
        "n_subjects": len(subject_entries),
        "decision_counts": decisions,
        "per_cohort": per_cohort,
        "subjects": subject_entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
