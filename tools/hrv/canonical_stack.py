"""Canonical cardiac γ-program extraction stack (Task 4).

Purpose
-------
Single source of truth for the HRV pipeline from annotation to features.
Every γ-program claim downstream is required to travel through this
module — no ad-hoc RR extraction, no one-off spectral fit, no rogue
DFA re-implementation. If a script needs a different path, it is
either a deliberate method-comparison study (Task 5 branch split) or
a protocol violation.

Canonical pipeline
------------------
  step 1   WFDB annotation fetch                tools.data.physionet_cohort.fetch_record
           ^ wfdb.rdann; filter symbol == "N"; diff samples / fs.

  step 2   Optional NN-interval resampling      tools.hrv.baseline_panel._resample_rr_to_uniform
           ^ linear interpolation onto uniform 4 Hz grid (Task Force 1996).

  step 3   Spectral features                    tools.hrv.baseline_panel._power_bands
           ^ scipy.signal.welch(nperseg=256 s, overlap 0.5); bands VLF/LF/HF/TP.

  step 4   Detrended fluctuation analysis       tools.hrv.baseline_panel.dfa_alpha
           ^ Peng et al. 1995, order-1 linear detrending, ≥ 4 segments per scale.

  step 5   Sample entropy                       tools.hrv.baseline_panel.sample_entropy
           ^ Richman & Moorman 2000, m=2, r=0.2σ, cap N≤5000.

  step 6   Poincaré SD1/SD2                     tools.hrv.baseline_panel._sd1_sd2_ms
           ^ Brennan et al. 2001 analytic identity.

  step 7   Five-layer null suite                tools.hrv.null_suite.compute_null_suite
           ^ L1 shuffled, L2 IAAFT, L3 AR(1), L4 Poisson, L5 latent GMM.

  step 8   Blind external validation            tools.hrv.blind_validation.validation_report
           ^ Youden threshold from dev, YAML-frozen, applied zero-refit on external.

Frozen parameters
-----------------
Every constant below is review-gated. Changing any of them requires
rotating CANONICAL_STACK_VERSION in this file — a public protocol event.
"""

from __future__ import annotations

from typing import Final

from tools.hrv.baseline_panel import DEFAULT_PARAMS

__all__ = [
    "CANONICAL_STACK_VERSION",
    "FREQUENCY_BANDS_HZ",
    "DFA_SCALES_SHORT",
    "DFA_SCALES_LONG",
    "RR_CLIP_RANGE_S",
    "WELCH_NPERSEG_S",
    "WELCH_OVERLAP",
    "FS_RESAMPLE_HZ",
    "SAMPEN_M",
    "SAMPEN_R_FRAC",
    "SAMPEN_MAX_N",
    "NULL_SURROGATES_PER_LAYER",
    "NULL_BEATS_CAP",
    "assert_canonical_params",
]

CANONICAL_STACK_VERSION: Final[str] = "1.0.0"

FREQUENCY_BANDS_HZ: Final[dict[str, tuple[float, float]]] = {
    "VLF": (0.003, 0.04),
    "LF": (0.04, 0.15),
    "HF": (0.15, 0.4),
    "TP": (0.003, 0.4),
}

DFA_SCALES_SHORT: Final[tuple[int, int]] = DEFAULT_PARAMS.dfa_short
DFA_SCALES_LONG: Final[tuple[int, int]] = DEFAULT_PARAMS.dfa_long
RR_CLIP_RANGE_S: Final[tuple[float, float]] = (DEFAULT_PARAMS.min_rr_s, DEFAULT_PARAMS.max_rr_s)
WELCH_NPERSEG_S: Final[float] = DEFAULT_PARAMS.welch_nperseg_s
WELCH_OVERLAP: Final[float] = DEFAULT_PARAMS.welch_overlap
FS_RESAMPLE_HZ: Final[float] = DEFAULT_PARAMS.fs_resample_hz
SAMPEN_M: Final[int] = DEFAULT_PARAMS.sampen_m
SAMPEN_R_FRAC: Final[float] = DEFAULT_PARAMS.sampen_r_frac
SAMPEN_MAX_N: Final[int] = DEFAULT_PARAMS.sampen_max_n

NULL_SURROGATES_PER_LAYER: Final[int] = 200
NULL_BEATS_CAP: Final[int] = 10_000


def assert_canonical_params() -> None:
    """Raise if :data:`tools.hrv.baseline_panel.DEFAULT_PARAMS` has drifted.

    Called by :mod:`tests.test_canonical_stack` on every CI run to catch
    silent parameter edits. Any edit to ``DEFAULT_PARAMS`` that is
    *intentional* must rotate :data:`CANONICAL_STACK_VERSION` at the same
    time (and sever the assertion until the constants below are
    updated).
    """

    frozen = {
        "min_rr_s": RR_CLIP_RANGE_S[0],
        "max_rr_s": RR_CLIP_RANGE_S[1],
        "fs_resample_hz": FS_RESAMPLE_HZ,
        "welch_nperseg_s": WELCH_NPERSEG_S,
        "welch_overlap": WELCH_OVERLAP,
        "dfa_short": DFA_SCALES_SHORT,
        "dfa_long": DFA_SCALES_LONG,
        "sampen_m": SAMPEN_M,
        "sampen_r_frac": SAMPEN_R_FRAC,
        "sampen_max_n": SAMPEN_MAX_N,
    }
    actual = {
        "min_rr_s": DEFAULT_PARAMS.min_rr_s,
        "max_rr_s": DEFAULT_PARAMS.max_rr_s,
        "fs_resample_hz": DEFAULT_PARAMS.fs_resample_hz,
        "welch_nperseg_s": DEFAULT_PARAMS.welch_nperseg_s,
        "welch_overlap": DEFAULT_PARAMS.welch_overlap,
        "dfa_short": DEFAULT_PARAMS.dfa_short,
        "dfa_long": DEFAULT_PARAMS.dfa_long,
        "sampen_m": DEFAULT_PARAMS.sampen_m,
        "sampen_r_frac": DEFAULT_PARAMS.sampen_r_frac,
        "sampen_max_n": DEFAULT_PARAMS.sampen_max_n,
    }
    drift = {k: (frozen[k], actual[k]) for k in frozen if frozen[k] != actual[k]}
    if drift:
        raise AssertionError(
            f"canonical stack drift: {drift}. Rotate CANONICAL_STACK_VERSION "
            f"(currently {CANONICAL_STACK_VERSION}) to register the change as "
            "a protocol event."
        )
