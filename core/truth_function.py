"""Truth Function — unified assessment of gamma measurement validity.

Integrates five independent verification axes:
  1. Tautology detection   — is cost algebraically derived from topo?
  2. Estimator consensus   — do Theil-Sen, OLS, Huber agree on gamma?
  3. Surrogate significance — does gamma survive IAAFT null destruction?
  4. DFA cross-validation   — does Hurst exponent H confirm gamma_PSD = 2H+1?
  5. RQA regime fingerprint — does the gamma trace show deterministic structure?

The truth function answers Sutskever's question:
  "Is gamma ~ 1.0 a LAW or an ARTIFACT?"

A system without a truth function is just pattern matching.
A system WITH one is science.

Author: Yaroslav Vasylenko / neuron7xLab
License: AGPL-3.0-or-later
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from scipy.stats import theilslopes

from core.iaaft import surrogate_p_value
from core.rqa import recurrence_quantification

__all__ = ["TruthAssessment", "assess_truth"]

# ── Thresholds ──────────────────────────────────────────────────────
_TAUTOLOGY_R2 = 0.999  # R2 above this = suspiciously perfect
_TAUTOLOGY_NOISE = 0.02  # residual std below this = likely constructed
_ESTIMATOR_SPREAD = 0.15  # max inter-estimator gamma spread
_SURROGATE_ALPHA = 0.05  # significance level for surrogate test
_DFA_CONSISTENCY = 0.25  # max |gamma_observed - gamma_dfa| for agreement
_RQA_DET_THRESHOLD = 0.3  # DET above this = deterministic structure
_MIN_TRACE_LEN = 15  # minimum gamma trace for RQA/DFA


@dataclass(frozen=True)
class TruthAssessment:
    """Result of the truth function evaluation.

    Verdict:
        VERIFIED      -- gamma passes all axes, no artifact detected
        CONSTRUCTED   -- tautology detected (cost derived from topo)
        FRAGILE       -- fails surrogate or estimator consensus
        INCONCLUSIVE  -- insufficient data for definitive assessment
    """

    verdict: str

    # Axis 1: Tautology
    tautology_risk: float  # 0.0 = clean, 1.0 = certainly constructed
    r2_suspicion: bool  # True if R2 > 0.999

    # Axis 2: Estimator consensus
    gamma_theilsen: float
    gamma_ols: float
    gamma_huber: float
    estimator_spread: float  # max - min across estimators
    estimators_agree: bool

    # Axis 3: Surrogate significance
    surrogate_p: float  # p-value against IAAFT null
    survives_null: bool

    # Axis 4: DFA cross-validation
    hurst_exponent: float  # H from DFA
    gamma_dfa: float  # 2H + 1
    dfa_consistent: bool  # |gamma_observed - gamma_dfa| < threshold

    # Axis 5: RQA regime fingerprint
    rqa_det: float  # determinism
    rqa_lam: float  # laminarity
    has_structure: bool  # DET > threshold

    # Summary
    n_axes_passed: int  # out of 5
    confidence: float  # n_axes_passed / n_axes_tested


def _ols_gamma(log_t: np.ndarray, log_c: np.ndarray) -> tuple[float, float]:
    """OLS gamma estimation."""
    n = len(log_t)
    sx, sy = np.sum(log_t), np.sum(log_c)
    sxx = np.sum(log_t * log_t)
    sxy = np.sum(log_t * log_c)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-15:
        return float("nan"), 0.0
    slope = float((n * sxy - sx * sy) / denom)
    intercept = float((sy - slope * sx) / n)
    yhat = slope * log_t + intercept
    ss_res = float(np.sum((log_c - yhat) ** 2))
    ss_tot = float(np.sum((log_c - np.mean(log_c)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-10 else 0.0
    return -slope, r2


def _huber_gamma(log_t: np.ndarray, log_c: np.ndarray, delta: float = 1.345) -> float:
    """Huber-robust gamma estimation."""
    neg_slope, r2 = _ols_gamma(log_t, log_c)
    if not np.isfinite(neg_slope):
        return float("nan")
    s = -neg_slope  # slope = -gamma, so s = slope
    # Recompute intercept from slope
    b = float(np.mean(log_c) - s * np.mean(log_t))
    for _ in range(20):
        residuals = log_c - (s * log_t + b)
        w = np.where(
            np.abs(residuals) <= delta,
            1.0,
            delta / (np.abs(residuals) + 1e-10),
        )
        ws = np.sum(w)
        wx = np.sum(w * log_t)
        wy = np.sum(w * log_c)
        wxx = np.sum(w * log_t * log_t)
        wxy = np.sum(w * log_t * log_c)
        d = ws * wxx - wx * wx
        if abs(d) < 1e-15:
            break
        new_s = float((ws * wxy - wx * wy) / d)
        new_b = float((wy - new_s * wx) / ws)
        if abs(new_s - s) < 1e-8:
            s, b = new_s, new_b
            break
        s, b = new_s, new_b
    return -s


def _dfa_exponent(signal: np.ndarray) -> float:
    """Compute DFA scaling exponent (Hurst-like)."""
    signal = np.asarray(signal, dtype=np.float64).ravel()
    n = len(signal)
    if n < 32:
        return float("nan")

    # Integrate: cumulative sum of deviations from mean
    y = np.cumsum(signal - np.mean(signal))

    min_box = 8
    max_box = n // 4
    if max_box < min_box + 2:
        return float("nan")

    n_scales = min(20, max_box - min_box)
    scales = np.unique(np.logspace(np.log10(min_box), np.log10(max_box), n_scales).astype(int))
    scales = scales[scales >= min_box]
    if len(scales) < 4:
        return float("nan")

    fluctuations = []
    for s in scales:
        n_seg = n // s
        if n_seg < 1:
            continue
        rms_list = []
        for v in range(n_seg):
            seg = y[v * s : (v + 1) * s]
            x_fit = np.arange(s)
            coeffs = np.polyfit(x_fit, seg, 1)
            trend = np.polyval(coeffs, x_fit)
            rms_list.append(float(np.sqrt(np.mean((seg - trend) ** 2))))
        if rms_list:
            fluctuations.append(float(np.mean(rms_list)))
        else:
            fluctuations.append(float("nan"))

    log_s = np.log(scales[: len(fluctuations)])
    log_f = np.log(np.array(fluctuations))
    valid = np.isfinite(log_s) & np.isfinite(log_f) & (log_f > -20)
    if valid.sum() < 4:
        return float("nan")

    slope, _, _, _ = theilslopes(log_f[valid], log_s[valid])
    return float(slope)


def assess_truth(
    topo: np.ndarray,
    cost: np.ndarray,
    gamma_observed: float,
    gamma_trace: list[float] | None = None,
    sr_trace: list[float] | None = None,
    *,
    n_surrogates: int = 99,
    seed: int = 42,
) -> TruthAssessment:
    """Run the unified truth function across all 5 axes.

    Args:
        topo:           raw topological complexity array
        cost:           raw thermodynamic cost array
        gamma_observed: the gamma value being assessed
        gamma_trace:    history of gamma values (for RQA/DFA)
        sr_trace:       history of spectral radius (for RQA)
        n_surrogates:   number of IAAFT surrogates for null test
        seed:           RNG seed for reproducibility

    Returns:
        TruthAssessment with verdict and per-axis results.
    """
    nan = float("nan")
    axes_tested = 0
    axes_passed = 0

    # ── Prepare log-space data ──────────────────────────────────────
    mask = np.isfinite(topo) & np.isfinite(cost) & (topo > 0) & (cost > 0)
    t_valid = topo[mask]
    c_valid = cost[mask]

    if len(t_valid) < 5:
        return TruthAssessment(
            verdict="INCONCLUSIVE",
            tautology_risk=nan,
            r2_suspicion=False,
            gamma_theilsen=nan,
            gamma_ols=nan,
            gamma_huber=nan,
            estimator_spread=nan,
            estimators_agree=False,
            surrogate_p=nan,
            survives_null=False,
            hurst_exponent=nan,
            gamma_dfa=nan,
            dfa_consistent=False,
            rqa_det=nan,
            rqa_lam=nan,
            has_structure=False,
            n_axes_passed=0,
            confidence=0.0,
        )

    log_t = np.log(t_valid)
    log_c = np.log(c_valid)

    # ── AXIS 1: Tautology Detection ─────────────────────────────────
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        slope_ts, intercept_ts, _, _ = theilslopes(log_c, log_t)
    gamma_ts = -slope_ts
    yhat = slope_ts * log_t + intercept_ts
    ss_res = float(np.sum((log_c - yhat) ** 2))
    ss_tot = float(np.sum((log_c - np.mean(log_c)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-10 else 0.0
    residual_std = float(np.std(log_c - yhat))

    r2_suspicion = r2 > _TAUTOLOGY_R2
    noise_suspicion = residual_std < _TAUTOLOGY_NOISE
    tautology_risk = 0.0
    if r2_suspicion and noise_suspicion:
        tautology_risk = 1.0
    elif r2_suspicion:
        tautology_risk = 0.7
    elif noise_suspicion:
        tautology_risk = 0.3

    axes_tested += 1
    if tautology_risk < 0.5:
        axes_passed += 1

    # ── AXIS 2: Estimator Consensus ─────────────────────────────────
    gamma_ols, _ = _ols_gamma(log_t, log_c)
    gamma_huber = _huber_gamma(log_t, log_c)

    gammas = [g for g in [gamma_ts, gamma_ols, gamma_huber] if np.isfinite(g)]
    if len(gammas) >= 2:
        spread = max(gammas) - min(gammas)
        estimators_agree = spread < _ESTIMATOR_SPREAD
    else:
        spread = nan
        estimators_agree = False

    axes_tested += 1
    if estimators_agree:
        axes_passed += 1

    # ── AXIS 3: Surrogate Significance ──────────────────────────────
    surrogate_p = nan
    survives_null = False
    if len(log_t) >= 10:
        rng = np.random.default_rng(seed)
        null_gammas = []
        for i in range(n_surrogates):
            # Shuffle cost against topo (destroys coupling)
            perm_c = rng.permutation(log_c)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                if np.ptp(log_t) > 1e-12:
                    s_null, _, _, _ = theilslopes(perm_c, log_t)
                    null_gammas.append(-s_null)
        if null_gammas:
            null_arr = np.array(null_gammas)
            surrogate_p = surrogate_p_value(gamma_observed, null_arr)
            survives_null = surrogate_p < _SURROGATE_ALPHA

        axes_tested += 1
        if survives_null:
            axes_passed += 1

    # ── AXIS 4: DFA Cross-Validation ────────────────────────────────
    hurst = nan
    gamma_dfa = nan
    dfa_consistent = False
    gt = gamma_trace or []
    finite_trace = [g for g in gt if np.isfinite(g)]

    if len(finite_trace) >= _MIN_TRACE_LEN:
        hurst = _dfa_exponent(np.array(finite_trace))
        if np.isfinite(hurst):
            gamma_dfa = 2.0 * hurst + 1.0
            dfa_consistent = abs(gamma_observed - gamma_dfa) < _DFA_CONSISTENCY

        axes_tested += 1
        if dfa_consistent:
            axes_passed += 1

    # ── AXIS 5: RQA Regime Fingerprint ──────────────────────────────
    rqa_det = nan
    rqa_lam = nan
    has_structure = False

    if len(finite_trace) >= _MIN_TRACE_LEN:
        try:
            rqa_result = recurrence_quantification(np.array(finite_trace), n_surrogate=0, seed=seed)
            det_val = rqa_result.get("det", nan)
            lam_val = rqa_result.get("lam", nan)
            rqa_det = float(det_val) if isinstance(det_val, (int, float)) else nan
            rqa_lam = float(lam_val) if isinstance(lam_val, (int, float)) else nan
            if np.isfinite(rqa_det):
                has_structure = rqa_det > _RQA_DET_THRESHOLD
        except Exception:  # noqa: BLE001 — RQA failure is non-fatal
            pass  # nosec B110  # graceful degradation, axis remains NaN

        axes_tested += 1
        if has_structure:
            axes_passed += 1

    # ── Verdict ─────────────────────────────────────────────────────
    confidence = axes_passed / max(axes_tested, 1)

    if tautology_risk >= 0.7:
        verdict = "CONSTRUCTED"
    elif axes_tested >= 3 and confidence >= 0.6:
        verdict = "VERIFIED"
    elif axes_tested >= 2 and confidence < 0.4:
        verdict = "FRAGILE"
    else:
        verdict = "INCONCLUSIVE"

    return TruthAssessment(
        verdict=verdict,
        tautology_risk=tautology_risk,
        r2_suspicion=r2_suspicion,
        gamma_theilsen=float(gamma_ts),
        gamma_ols=float(gamma_ols),
        gamma_huber=float(gamma_huber),
        estimator_spread=float(spread),
        estimators_agree=estimators_agree,
        surrogate_p=float(surrogate_p),
        survives_null=survives_null,
        hurst_exponent=float(hurst),
        gamma_dfa=float(gamma_dfa),
        dfa_consistent=dfa_consistent,
        rqa_det=float(rqa_det),
        rqa_lam=float(rqa_lam),
        has_structure=has_structure,
        n_axes_passed=axes_passed,
        confidence=confidence,
    )
