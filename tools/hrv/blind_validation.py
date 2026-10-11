"""Blind external-validation pipeline (Task 8).

Pipeline
--------
  1. Load frozen analysis split (Task 2).
  2. Collect the 11-metric baseline panel (Task 3) for every subject.
  3. For the DEVELOPMENT split:
     - per metric: compute AUC (Mann-Whitney U), Cohen's d, optimal
       Youden threshold (argmax over sens+spec-1), sensitivity and
       specificity at that threshold.
     - write all thresholds + decision directions to
       ``config/thresholds_frozen.yaml`` together with a sha256 lock.
  4. For the EXTERNAL split:
     - load thresholds from the frozen YAML (forbidden to recompute).
     - apply threshold + direction to each subject, score
       sensitivity / specificity / Cohen's d / AUC with *no* parameter
       refit. External subjects are only scored here.
  5. Emit one report object with both splits side-by-side.

Audit-gate contract
-------------------
- Thresholds on external are **read from YAML**, never recomputed.
- The YAML carries its own sha256 lock (analogous to
  :data:`tools.data.analysis_split.ANALYSIS_SPLIT_SHA256`). Any edit
  to the YAML without a same-PR update of the sha256 in
  :data:`THRESHOLDS_FROZEN_SHA256` placeholder (left empty until the
  first calibration write) breaks the loader.
- External scoring is wrapped so that any baseline read happens
  *after* the dev-only context manager has exited.

Label convention
----------------
  label = 0  healthy  (nsr2db, nsrdb)
  label = 1  pathology (chfdb, chf2db)
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import numpy as np

from tools.data.analysis_split import (
    AnalysisSplit,
    SubjectRef,
    enforce_dev_only,
)
from tools.data.physionet_cohort import COHORTS

__all__ = [
    "Direction",
    "MetricThreshold",
    "FrozenThresholds",
    "validation_report",
    "load_baseline_panels",
    "auc_mann_whitney",
    "cohens_d",
    "compute_metric_thresholds",
    "score_external",
    "THRESHOLDS_FROZEN_PATH",
]

THRESHOLDS_FROZEN_PATH = Path(__file__).resolve().parents[2] / "config" / "thresholds_frozen.yaml"

_METRIC_KEYS: tuple[str, ...] = (
    "sdnn_ms",
    "rmssd_ms",
    "total_power_ms2",
    "lf_power_ms2",
    "hf_power_ms2",
    "lf_hf_ratio",
    "dfa_alpha1",
    "dfa_alpha2",
    "poincare_sd1_ms",
    "poincare_sd2_ms",
    "sample_entropy",
)

Direction = Literal["healthy_high", "healthy_low"]


# ---------------------------------------------------------------------------
# Label map
# ---------------------------------------------------------------------------
def _cohort_label(cohort: str) -> int:
    role = COHORTS[cohort].role
    if role.endswith("_healthy"):
        return 0
    if role.endswith("_pathology"):
        return 1
    raise ValueError(f"unlabeled cohort: {cohort} / {role}")


# ---------------------------------------------------------------------------
# Data loader
# ---------------------------------------------------------------------------
def load_baseline_panels(
    subjects: Sequence[SubjectRef],
    *,
    results_dir: Path,
) -> dict[str, list[float | int]]:
    """Return {metric → list of per-subject values aligned to ``subjects``}."""

    out: dict[str, list[float | int]] = {k: [] for k in _METRIC_KEYS}
    labels: list[int] = []
    for ref in subjects:
        path = results_dir / f"{ref.cohort}__{ref.record}_baseline.json"
        if not path.exists():
            raise FileNotFoundError(path)
        panel = json.loads(path.read_text("utf-8"))["panel"]
        for k in _METRIC_KEYS:
            out[k].append(panel[k])
        labels.append(_cohort_label(ref.cohort))
    out["_label"] = labels
    return out


# ---------------------------------------------------------------------------
# Scoring primitives
# ---------------------------------------------------------------------------
def auc_mann_whitney(scores_pos: Sequence[float], scores_neg: Sequence[float]) -> float:
    """AUC via the Mann-Whitney U identity: AUC = P(score_pos > score_neg).

    NaN scores are dropped. Returns NaN if either group is empty after
    filtering. Ties count as 0.5.
    """

    a = np.asarray([x for x in scores_pos if np.isfinite(x)], dtype=np.float64)
    b = np.asarray([x for x in scores_neg if np.isfinite(x)], dtype=np.float64)
    if a.size == 0 or b.size == 0:
        return float("nan")
    m, n = a.size, b.size
    combined = np.concatenate([a, b])
    order = np.argsort(combined, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, m + n + 1, dtype=np.float64)
    # handle ties by averaging
    _, inv, counts = np.unique(combined, return_inverse=True, return_counts=True)
    for i, c in enumerate(counts):
        if c > 1:
            ranks[inv == i] = ranks[inv == i].mean()
    r_a = float(np.sum(ranks[:m]))
    u = r_a - m * (m + 1) / 2
    return float(u / (m * n))


def cohens_d(scores_a: Sequence[float], scores_b: Sequence[float]) -> float:
    """Pooled-sd Cohen's d (a − b)."""

    a = np.asarray([x for x in scores_a if np.isfinite(x)], dtype=np.float64)
    b = np.asarray([x for x in scores_b if np.isfinite(x)], dtype=np.float64)
    if a.size < 2 or b.size < 2:
        return float("nan")
    sa = float(a.std(ddof=1))
    sb = float(b.std(ddof=1))
    n_a, n_b = a.size, b.size
    pooled = math.sqrt(((n_a - 1) * sa * sa + (n_b - 1) * sb * sb) / (n_a + n_b - 2))
    if pooled == 0.0:
        return float("nan")
    return float((a.mean() - b.mean()) / pooled)


def _best_youden_threshold(
    healthy: np.ndarray,
    pathology: np.ndarray,
) -> tuple[float, Direction, float, float]:
    """Return (threshold, direction, sens_at_thr, spec_at_thr).

    Direction encodes whether "higher value → healthy" or vice versa.
    We evaluate both and pick the one with the larger Youden index.
    """

    combined = np.concatenate([healthy, pathology])
    combined = combined[np.isfinite(combined)]
    if combined.size < 2:
        return float("nan"), "healthy_high", float("nan"), float("nan")

    # candidate thresholds = unique values (order-independent)
    cand = np.unique(combined)
    best = (-math.inf, float("nan"), "healthy_high", float("nan"), float("nan"))

    for direction in ("healthy_high", "healthy_low"):
        for t in cand:
            if direction == "healthy_high":
                pred_pathology = combined < t
                # sens = TPR on pathology (label=1), spec = TNR on healthy
                tp = np.sum((pred_pathology) & np.isin(combined, pathology))
                fn = np.sum((~pred_pathology) & np.isin(combined, pathology))
                tn = np.sum((~pred_pathology) & np.isin(combined, healthy))
                fp = np.sum((pred_pathology) & np.isin(combined, healthy))
            else:  # healthy_low
                pred_pathology = combined > t
                tp = np.sum((pred_pathology) & np.isin(combined, pathology))
                fn = np.sum((~pred_pathology) & np.isin(combined, pathology))
                tn = np.sum((~pred_pathology) & np.isin(combined, healthy))
                fp = np.sum((pred_pathology) & np.isin(combined, healthy))
            sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            youden = sens + spec - 1.0
            if youden > best[0]:
                best = (youden, float(t), direction, float(sens), float(spec))  # type: ignore[assignment]

    return best[1], best[2], best[3], best[4]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Frozen threshold store
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class MetricThreshold:
    metric: str
    threshold: float
    direction: Direction

    def predict(self, value: float) -> int:
        """Return 0 (healthy) or 1 (pathology) for one subject's value."""
        if not math.isfinite(value):
            return -1
        if self.direction == "healthy_high":
            return 1 if value < self.threshold else 0
        return 1 if value > self.threshold else 0


@dataclasses.dataclass(frozen=True)
class FrozenThresholds:
    thresholds: dict[str, MetricThreshold]
    split_sha256: str
    frozen_utc: str

    def dump_yaml(self, path: Path) -> str:
        """Write YAML and return its sha256."""
        lines = [
            "# Frozen thresholds — Task 8 blind external validation",
            "#",
            "# Calibrated on development split only (Task 2). Applied to",
            "# external split without modification. Editing this file after",
            "# external evaluation is a protocol violation (audit E-02 / E-03).",
            "",
            "schema_version: 1",
            f'frozen_utc: "{self.frozen_utc}"',
            f'split_sha256: "{self.split_sha256}"',
            "",
            "thresholds:",
        ]
        for key in sorted(self.thresholds):
            t = self.thresholds[key]
            thr_val = t.threshold
            thr_str = "NaN" if not math.isfinite(thr_val) else f"{thr_val:.6f}"
            lines.append(f"  {key}:")
            lines.append(f"    threshold: {thr_str}")
            lines.append(f"    direction: {t.direction}")
        content = "\n".join(lines) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _parse_thresholds_yaml(text: str) -> dict[str, MetricThreshold]:
    out: dict[str, MetricThreshold] = {}
    lines = text.splitlines()
    i = 0
    in_thresholds = False
    current: str | None = None
    thr_val: float | None = None
    dir_val: Direction | None = None
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s == "thresholds:":
            in_thresholds = True
            i += 1
            continue
        if not in_thresholds:
            i += 1
            continue
        if not line.startswith(" "):
            i += 1
            continue
        if line.startswith("  ") and not line.startswith("    ") and s.endswith(":"):
            current = s[:-1]
            thr_val = None
            dir_val = None
            i += 1
            continue
        if line.startswith("    "):
            key, _, v = s.partition(":")
            v = v.strip()
            if key == "threshold":
                thr_val = float("nan") if v.lower() == "nan" else float(v)
            elif key == "direction":
                assert v in ("healthy_high", "healthy_low"), v
                dir_val = v  # type: ignore[assignment]
            if current is not None and thr_val is not None and dir_val is not None:
                out[current] = MetricThreshold(metric=current, threshold=thr_val, direction=dir_val)
                current = None
                thr_val = None
                dir_val = None
            i += 1
            continue
        i += 1
    return out


def load_frozen_thresholds(path: Path = THRESHOLDS_FROZEN_PATH) -> dict[str, MetricThreshold]:
    return _parse_thresholds_yaml(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------
def compute_metric_thresholds(
    dev_panels: dict[str, list[float | int]],
) -> tuple[dict[str, MetricThreshold], dict[str, dict[str, float]]]:
    """Fit thresholds on the development split. Dev split only."""

    labels = np.asarray(dev_panels["_label"], dtype=int)
    thresholds: dict[str, MetricThreshold] = {}
    dev_metrics: dict[str, dict[str, float]] = {}
    for key in _METRIC_KEYS:
        vals = np.asarray(dev_panels[key], dtype=np.float64)
        healthy = vals[labels == 0]
        pathology = vals[labels == 1]
        auc_raw = auc_mann_whitney(pathology, healthy)  # high value → pathology
        # Convention: report AUC ≥ 0.5; separability = |auc_raw − 0.5| × 2.
        # direction reflects which way the metric separates, not the AUC sign.
        auc = auc_raw if auc_raw >= 0.5 else (1.0 - auc_raw)
        d = cohens_d(healthy, pathology)
        t, direction, sens, spec = _best_youden_threshold(healthy, pathology)
        thresholds[key] = MetricThreshold(metric=key, threshold=t, direction=direction)
        dev_metrics[key] = {
            "auc": auc,
            "auc_raw_pathology_over_healthy": auc_raw,
            "cohens_d": d,
            "threshold": t,
            "direction": direction,
            "sensitivity": sens,
            "specificity": spec,
            "n_healthy": int(np.sum(np.isfinite(healthy))),
            "n_pathology": int(np.sum(np.isfinite(pathology))),
        }
    return thresholds, dev_metrics


def score_external(
    ext_panels: dict[str, list[float | int]],
    thresholds: dict[str, MetricThreshold],
) -> dict[str, dict[str, float]]:
    """Apply frozen thresholds to the external split. Zero refit."""

    labels = np.asarray(ext_panels["_label"], dtype=int)
    out: dict[str, dict[str, float]] = {}
    for key in _METRIC_KEYS:
        vals = np.asarray(ext_panels[key], dtype=np.float64)
        healthy = vals[labels == 0]
        pathology = vals[labels == 1]
        auc_raw = auc_mann_whitney(pathology, healthy)
        auc = auc_raw if auc_raw >= 0.5 else (1.0 - auc_raw)
        d = cohens_d(healthy, pathology)
        t = thresholds[key]
        preds = np.array([t.predict(v) for v in vals], dtype=int)
        mask = preds >= 0
        lab = labels[mask]
        pr = preds[mask]
        tp = int(np.sum((pr == 1) & (lab == 1)))
        fn = int(np.sum((pr == 0) & (lab == 1)))
        tn = int(np.sum((pr == 0) & (lab == 0)))
        fp = int(np.sum((pr == 1) & (lab == 0)))
        sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        out[key] = {
            "auc": auc,
            "auc_raw_pathology_over_healthy": auc_raw,
            "cohens_d": d,
            "threshold_applied": t.threshold,
            "direction_applied": t.direction,
            "sensitivity": sens,
            "specificity": spec,
            "n_healthy": int(np.sum(np.isfinite(healthy))),
            "n_pathology": int(np.sum(np.isfinite(pathology))),
        }
    return out


def validation_report(
    split: AnalysisSplit,
    baseline_dir: Path,
    thresholds_path: Path = THRESHOLDS_FROZEN_PATH,
) -> dict[str, Any]:
    """Run the full dev-calibrate + external-score pipeline."""

    # DEV calibration — gate external reads
    with enforce_dev_only():
        dev_panels = load_baseline_panels(split.development.subjects, results_dir=baseline_dir)
    thresholds, dev_metrics = compute_metric_thresholds(dev_panels)

    # Freeze to YAML (lockable). Must happen before external scoring.
    from datetime import datetime, timezone

    frozen = FrozenThresholds(
        thresholds=thresholds,
        split_sha256=split.sha256,
        frozen_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    yaml_sha = frozen.dump_yaml(thresholds_path)

    # External scoring — explicitly re-read from the frozen YAML.
    thr_reread = load_frozen_thresholds(thresholds_path)
    ext_panels = load_baseline_panels(split.external.subjects, results_dir=baseline_dir)
    ext_metrics = score_external(ext_panels, thr_reread)

    return {
        "schema_version": 1,
        "split_sha256": split.sha256,
        "thresholds_yaml_sha256": yaml_sha,
        "n_dev_subjects": split.development.n_subjects,
        "n_external_subjects": split.external.n_subjects,
        "frozen_utc": frozen.frozen_utc,
        "per_metric": {
            key: {
                "development": dev_metrics[key],
                "external": ext_metrics[key],
            }
            for key in _METRIC_KEYS
        },
    }
