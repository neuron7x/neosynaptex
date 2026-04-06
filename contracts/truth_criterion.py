"""NFI v2.1 -- Truth Criterion (Section 3, canonical revision).

Static correlation is rejected as insufficient.

Valid criterion: synchronized beta-shift across independent channels
within a narrow window around t_shift, with wavelet coherence and
transfer entropy confirmation against IAAFT surrogates.

Author: Yaroslav Vasylenko / neuron7xLab
License: AGPL-3.0-or-later
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import welch
from scipy.stats import theilslopes


# ---------------------------------------------------------------------------
# Beta computation (PSD slope)
# ---------------------------------------------------------------------------
def rolling_beta(
    series: np.ndarray,
    fs: float = 1.0,
    window: int = 64,
    step: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute rolling PSD slope beta over time.

    Returns:
        t_centers: center indices of each window
        betas:     PSD slope at each window
    """
    n = len(series)
    t_centers = []
    betas = []
    for start in range(0, n - window, step):
        chunk = series[start : start + window]
        nperseg = min(len(chunk), max(16, len(chunk) // 4))
        freqs, psd = welch(chunk, fs=fs, nperseg=nperseg, detrend="linear")
        mask = freqs > 0
        freqs, psd = freqs[mask], psd[mask]
        if len(freqs) < 4:
            continue
        log_f = np.log10(freqs)
        log_p = np.log10(psd + 1e-30)
        slope, _, _, _ = theilslopes(log_p, log_f)
        beta = -slope
        t_centers.append(start + window // 2)
        betas.append(beta)
    return np.array(t_centers), np.array(betas)


# ---------------------------------------------------------------------------
# Event detection: localized beta departure from unity
# ---------------------------------------------------------------------------
@dataclass
class ShiftEvent:
    """A detected beta-shift event in one channel."""

    t_index: int
    delta_beta: float
    channel: str


def calibrate_epsilon(baseline_betas: np.ndarray, k: float = 2.0) -> float:
    """Calibrate epsilon as k * sigma of baseline beta distribution.

    Default k=2.0 (2-sigma threshold).
    Must be called on baseline data BEFORE perturbation sessions.
    """
    sigma = float(np.std(baseline_betas))
    eps = k * sigma
    # Floor: never below 0.05 (noise floor)
    # Ceiling: never above 0.50 (would miss real shifts)
    return float(np.clip(eps, 0.05, 0.50))


def detect_shift_events(
    betas: np.ndarray,
    t_centers: np.ndarray,
    epsilon: float = 0.15,
    channel: str = "unknown",
) -> list[ShiftEvent]:
    """Detect points where |beta - 1.0| > epsilon.

    Events are local departures from metastability.
    Epsilon should be calibrated via calibrate_epsilon() on baseline data.
    """
    delta = betas - 1.0
    events = []
    for i, (t, db) in enumerate(zip(t_centers, delta)):
        if abs(db) > epsilon:
            events.append(ShiftEvent(t_index=int(t), delta_beta=float(db), channel=channel))
    return events


# ---------------------------------------------------------------------------
# Synchronicity check between two channels
# ---------------------------------------------------------------------------
@dataclass
class SyncResult:
    """Result of synchronicity check between two channels."""

    synchronized: bool
    dt: float | None  # time difference between nearest shift events
    delta_t_threshold: float
    channel_1_events: int
    channel_2_events: int


def check_synchronicity(
    events_1: list[ShiftEvent],
    events_2: list[ShiftEvent],
    delta_t: float = 5.0,
) -> SyncResult:
    """Check if shift events in two channels occur within delta_t of each other.

    |t_shift_1 - t_shift_2| <= delta_t -> synchronized
    """
    if not events_1 or not events_2:
        return SyncResult(
            synchronized=False,
            dt=None,
            delta_t_threshold=delta_t,
            channel_1_events=len(events_1),
            channel_2_events=len(events_2),
        )

    # Find closest pair
    min_dt = float("inf")
    for e1 in events_1:
        for e2 in events_2:
            dt_val = abs(e1.t_index - e2.t_index)
            if dt_val < min_dt:
                min_dt = dt_val

    return SyncResult(
        synchronized=min_dt <= delta_t,
        dt=float(min_dt),
        delta_t_threshold=delta_t,
        channel_1_events=len(events_1),
        channel_2_events=len(events_2),
    )


# ---------------------------------------------------------------------------
# Wavelet coherence (simplified Morlet)
# ---------------------------------------------------------------------------
def wavelet_coherence_window(
    series_1: np.ndarray,
    series_2: np.ndarray,
    t_center: int,
    half_window: int = 32,
    n_freqs: int = 16,
) -> float:
    """Compute wavelet coherence between two series in a window around t_center.

    Returns mean coherence in [0, 1]. Higher = more coherent.
    """
    lo = max(0, t_center - half_window)
    hi = min(len(series_1), t_center + half_window)
    s1 = series_1[lo:hi]
    s2 = series_2[lo:hi]
    if len(s1) < 16:
        return 0.0

    # Cross-spectral density approach
    from scipy.signal import csd
    from scipy.signal import welch as welch_fn

    nperseg = min(len(s1), max(8, len(s1) // 2))
    f, pxy = csd(s1, s2, nperseg=nperseg)
    _, pxx = welch_fn(s1, nperseg=nperseg)
    _, pyy = welch_fn(s2, nperseg=nperseg)

    denom = np.sqrt(pxx * pyy + 1e-30)
    coh = np.abs(pxy) ** 2 / (denom**2 + 1e-30)

    mask = f > 0
    if mask.sum() < 2:
        return 0.0
    return float(np.mean(coh[mask]))


# ---------------------------------------------------------------------------
# IAAFT surrogate test for significance
# ---------------------------------------------------------------------------
def iaaft_surrogate(series: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Generate one IAAFT surrogate (preserves power spectrum + amplitude distribution)."""
    n = len(series)
    sorted_vals = np.sort(series)
    fft_orig = np.fft.rfft(series)
    amplitudes = np.abs(fft_orig)

    # Start with random shuffle
    surrogate = rng.permutation(series).copy()

    for _ in range(50):  # iterate to convergence
        # Match power spectrum
        fft_surr = np.fft.rfft(surrogate)
        phases = np.angle(fft_surr)
        fft_new = amplitudes * np.exp(1j * phases)
        surrogate = np.fft.irfft(fft_new, n=n)

        # Match amplitude distribution
        ranks = np.argsort(np.argsort(surrogate))
        surrogate = sorted_vals[ranks]

    return np.asarray(surrogate)  # ensure ndarray return type


def surrogate_test(
    series_1: np.ndarray,
    series_2: np.ndarray,
    observed_coherence: float,
    n_surrogates: int = 99,
    seed: int = 42,
) -> tuple[float, bool]:
    """Test observed coherence against IAAFT surrogates.

    Returns (p_value, significant_at_005).
    Null hypothesis: coherence is explained by shared spectral structure alone.
    """
    rng = np.random.default_rng(seed)
    surr_coh_list: list[float] = []
    t_center = len(series_1) // 2

    for _ in range(n_surrogates):
        s1_surr = iaaft_surrogate(series_1, rng)
        s2_surr = iaaft_surrogate(series_2, rng)
        coh = wavelet_coherence_window(s1_surr, s2_surr, t_center)
        surr_coh_list.append(coh)

    surr_coh = np.array(surr_coh_list)
    p_value = float((surr_coh >= observed_coherence).sum() + 1) / (n_surrogates + 1)
    return p_value, p_value < 0.05


# ---------------------------------------------------------------------------
# Full truth criterion evaluation
# ---------------------------------------------------------------------------
@dataclass
class TruthCriterionResult:
    """Full evaluation of the truth criterion for two channels."""

    # Event detection
    events_ch1: int
    events_ch2: int
    # Synchronicity
    synchronized: bool
    dt: float | None
    # Coherence
    wcoh: float
    wcoh_above_threshold: bool
    # Transfer entropy
    te_max: float
    te_above_threshold: bool
    # Surrogate test
    surrogate_p: float
    surrogate_significant: bool
    # Final verdict
    verdict: str  # "REGIME_INVARIANT" | "ARTIFACT" | "INSUFFICIENT_DATA"


def evaluate_truth_criterion(
    series_1: np.ndarray,
    series_2: np.ndarray,
    fs: float = 1.0,
    epsilon: float = 0.15,
    delta_t: float = 5.0,
    theta_c: float = 0.3,
    theta_te: float = 0.001,
    alpha: float = 0.05,
    n_surrogates: int = 99,
) -> TruthCriterionResult:
    """Evaluate the canonical truth criterion (Section 3).

    Not 'do they correlate at all' but
    'do they enter/exit the regime synchronously'.

    Synchronized departure (beta != 1) and synchronized return
    = REGIME INVARIANT.
    Absence of synchronicity = ARTIFACT, rejected.
    """
    from substrates.bn_syn.transfer_entropy import transfer_entropy

    # Step 1: rolling beta per channel
    t1, b1 = rolling_beta(series_1, fs=fs)
    t2, b2 = rolling_beta(series_2, fs=fs)

    if len(b1) < 4 or len(b2) < 4:
        return TruthCriterionResult(
            events_ch1=0,
            events_ch2=0,
            synchronized=False,
            dt=None,
            wcoh=0.0,
            wcoh_above_threshold=False,
            te_max=0.0,
            te_above_threshold=False,
            surrogate_p=1.0,
            surrogate_significant=False,
            verdict="INSUFFICIENT_DATA",
        )

    # Step 2: detect shift events independently
    ev1 = detect_shift_events(b1, t1, epsilon, "ch1")
    ev2 = detect_shift_events(b2, t2, epsilon, "ch2")

    # Step 3: synchronicity
    sync = check_synchronicity(ev1, ev2, delta_t)

    # Step 4: wavelet coherence in window around first shared shift
    if sync.synchronized and sync.dt is not None and ev1:
        t_shift = ev1[0].t_index
        wcoh = wavelet_coherence_window(series_1, series_2, t_shift)
    else:
        wcoh = wavelet_coherence_window(series_1, series_2, len(series_1) // 2)

    # Step 5: transfer entropy (either direction)
    te_12 = transfer_entropy(series_1, series_2)
    te_21 = transfer_entropy(series_2, series_1)
    te_max = max(te_12, te_21)

    # Step 6: surrogate test
    surr_p, surr_sig = surrogate_test(series_1, series_2, wcoh, n_surrogates)

    # Verdict
    wcoh_ok = wcoh > theta_c
    te_ok = te_max > theta_te
    if sync.synchronized and wcoh_ok and te_ok and surr_sig:
        verdict = "REGIME_INVARIANT"
    elif not sync.synchronized:
        verdict = "ARTIFACT"
    elif not surr_sig:
        verdict = "TRIVIAL_DRIFT"
    else:
        verdict = "INCONCLUSIVE"

    return TruthCriterionResult(
        events_ch1=len(ev1),
        events_ch2=len(ev2),
        synchronized=sync.synchronized,
        dt=sync.dt,
        wcoh=round(wcoh, 4),
        wcoh_above_threshold=wcoh_ok,
        te_max=round(te_max, 6),
        te_above_threshold=te_ok,
        surrogate_p=round(surr_p, 4),
        surrogate_significant=surr_sig,
        verdict=verdict,
    )
