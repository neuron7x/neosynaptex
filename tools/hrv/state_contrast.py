"""Within-subject state contrast — Task 9 of the γ-program protocol.

For every subject we split the RR series into halves (proxy for
day/night when the recording covers ≥ 20 h) and into stable/unstable
segments, and we also recompute the primary DFA α₂ at three window
lengths (256 / 512 / 1024 beats). The per-subject delta is the
short-term test of "is α₂ driven by within-subject regime variation?".

Interpretation rule
-------------------
  If ``|Δα₂|_median`` across the cohort exceeds ``regime_delta``,
  α₂ is flagged as *regime-dependent*. Regime dependence does NOT
  invalidate the marker — but it forbids universal-γ claims until
  the regime axis is separately characterised.
"""

from __future__ import annotations

import dataclasses
import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from tools.hrv.baseline_panel import HRVPreprocessingParams, _preprocess, dfa_alpha

__all__ = [
    "StateContrastConfig",
    "StateContrastReport",
    "compute_state_contrast",
    "emit_cohort_state_contrast",
]


@dataclasses.dataclass(frozen=True)
class StateContrastConfig:
    dfa_scales: tuple[int, ...] = (16, 22, 30, 40, 54, 64)
    window_beats: tuple[int, ...] = (256, 512, 1024)
    regime_delta: float = 0.20
    stable_unstable_quantile: float = 0.5  # median-SD split


DEFAULT_CFG = StateContrastConfig()


@dataclasses.dataclass(frozen=True)
class StateContrastReport:
    cohort: str
    record: str
    alpha2_full: float
    alpha2_first_half: float
    alpha2_second_half: float
    delta_half: float
    alpha2_stable: float
    alpha2_unstable: float
    delta_stable_unstable: float
    alpha2_by_window: dict[str, float]
    regime_dependent: bool

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _segment_stable_unstable(
    rr: np.ndarray, window_beats: int, quantile: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return (stable_rr, unstable_rr) concatenations split by windowed SDNN."""

    if rr.size < 2 * window_beats:
        return rr, np.asarray([], dtype=np.float64)
    n_w = rr.size // window_beats
    windows = rr[: n_w * window_beats].reshape(n_w, window_beats)
    sdnns = windows.std(axis=1, ddof=1)
    thr = float(np.quantile(sdnns, quantile))
    stable = windows[sdnns <= thr].reshape(-1)
    unstable = windows[sdnns > thr].reshape(-1)
    return stable, unstable


def _alpha2_at_window(rr: np.ndarray, window_beats: int, scales: np.ndarray) -> float:
    """Mean α₂ across sliding non-overlap windows of ``window_beats``."""

    if rr.size < 2 * window_beats or window_beats < max(scales) * 2:
        return float("nan")
    n_w = rr.size // window_beats
    vals: list[float] = []
    for i in range(n_w):
        w = rr[i * window_beats : (i + 1) * window_beats]
        a = dfa_alpha(w, scales)
        if np.isfinite(a):
            vals.append(float(a))
    if not vals:
        return float("nan")
    return float(statistics.mean(vals))


def compute_state_contrast(
    rr_raw_s: np.ndarray,
    cohort: str,
    record: str,
    cfg: StateContrastConfig = DEFAULT_CFG,
) -> StateContrastReport:
    rr, _ = _preprocess(rr_raw_s, HRVPreprocessingParams(min_rr_s=0.3, max_rr_s=2.0))
    scales = np.asarray(cfg.dfa_scales, dtype=np.int64)

    a_full = dfa_alpha(rr, scales) if rr.size >= 4 * max(cfg.dfa_scales) else float("nan")
    mid = rr.size // 2
    a_first = dfa_alpha(rr[:mid], scales) if mid >= 4 * max(cfg.dfa_scales) else float("nan")
    a_second = (
        dfa_alpha(rr[mid:], scales) if (rr.size - mid) >= 4 * max(cfg.dfa_scales) else float("nan")
    )
    delta_half = (
        abs(a_first - a_second) if np.isfinite(a_first) and np.isfinite(a_second) else float("nan")
    )

    stable, unstable = _segment_stable_unstable(rr, 256, cfg.stable_unstable_quantile)
    a_stable = dfa_alpha(stable, scales) if stable.size >= 4 * max(cfg.dfa_scales) else float("nan")
    a_unstable = (
        dfa_alpha(unstable, scales) if unstable.size >= 4 * max(cfg.dfa_scales) else float("nan")
    )
    delta_su = (
        abs(a_stable - a_unstable)
        if np.isfinite(a_stable) and np.isfinite(a_unstable)
        else float("nan")
    )

    alpha_by_window = {str(wb): _alpha2_at_window(rr, wb, scales) for wb in cfg.window_beats}

    regime_dependent = (np.isfinite(delta_half) and delta_half > cfg.regime_delta) or (
        np.isfinite(delta_su) and delta_su > cfg.regime_delta
    )

    return StateContrastReport(
        cohort=cohort,
        record=record,
        alpha2_full=float(a_full),
        alpha2_first_half=float(a_first),
        alpha2_second_half=float(a_second),
        delta_half=float(delta_half),
        alpha2_stable=float(a_stable),
        alpha2_unstable=float(a_unstable),
        delta_stable_unstable=float(delta_su),
        alpha2_by_window=alpha_by_window,
        regime_dependent=bool(regime_dependent),
    )


def emit_cohort_state_contrast(
    out_path: Path,
    cache_dir: Path,
    cohorts: dict[str, Any],
    cfg: StateContrastConfig = DEFAULT_CFG,
) -> dict[str, Any]:
    """Run state contrast on every cached subject; emit one aggregate JSON."""

    rows: list[dict[str, Any]] = []
    for cohort, spec in cohorts.items():
        for record in spec.expected_records:
            path = cache_dir / cohort / f"{record}.rr.npy"
            if not path.exists():
                continue
            rr = np.load(path, allow_pickle=False)
            r = compute_state_contrast(rr, cohort, record, cfg)
            rows.append(r.as_dict())

    deltas_half = [r["delta_half"] for r in rows if np.isfinite(r["delta_half"])]
    deltas_su = [
        r["delta_stable_unstable"] for r in rows if np.isfinite(r["delta_stable_unstable"])
    ]
    regime_count = sum(1 for r in rows if r["regime_dependent"])

    aggregate = {
        "schema_version": 1,
        "n_subjects": len(rows),
        "regime_dependent_count": regime_count,
        "regime_dependent_fraction": regime_count / len(rows) if rows else 0.0,
        "median_delta_half": float(statistics.median(deltas_half)) if deltas_half else float("nan"),
        "median_delta_stable_unstable": float(statistics.median(deltas_su))
        if deltas_su
        else float("nan"),
        "regime_delta_threshold": cfg.regime_delta,
        "subjects": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return aggregate
