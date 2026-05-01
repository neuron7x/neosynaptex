"""Integrity v2 — honest substrates, correct parameters, real data.

Tests verify:
1. BN-Syn uses real branching dynamics, not synthetic 1/f
2. Kuramoto operates at true Kc
3. HRV produces gamma from real PhysioNet data
4. All substrates' gamma values are reproducible
5. Negative controls separate from unity
6. Tier classification boundaries correct
"""

import inspect
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.gamma import compute_gamma

_RUN_NETWORK_TESTS = os.environ.get("NEOSYNAPTEX_RUN_NETWORK_TESTS") == "1"
_HRV_FLOOR_MIN_SUBJECTS = 3


def _try_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


# ── BN-Syn integrity ──


class TestBnSynIntegrity:
    def test_no_synthetic_1f(self):
        """BN-Syn must NOT contain _generate_1f_noise or hardcoded gamma=1.0."""
        from substrates.bn_syn import adapter as mod

        source = inspect.getsource(mod)
        assert "_generate_1f_noise" not in source, "Synthetic 1/f generator found — tautological"
        # Check no hardcoded gamma=1.0 in noise generation context
        assert "gamma=1.0, seed" not in source, "Hardcoded gamma=1.0 in noise generation"

    def test_branching_ratio(self):
        """Branching ratio σ = p × k must equal 1.0."""
        from substrates.bn_syn.adapter import BnSynAdapter

        adapter = BnSynAdapter(seed=42)
        sigma = adapter._p_transmit * adapter._k
        assert abs(sigma - 1.0) < 1e-10, f"σ = {sigma}, expected 1.0"

    def test_honest_gamma(self):
        """BN-Syn gamma must NOT be near 1.0 (finite-size effects expected)."""
        from substrates.bn_syn.adapter import BnSynAdapter

        adapter = BnSynAdapter(seed=42)
        topos, costs = adapter.get_all_pairs()
        r = compute_gamma(topos, costs)
        # With N=200, k=10: expect gamma ≈ 0.47, NOT near 1.0
        assert r.gamma < 0.7, f"BN-Syn gamma={r.gamma:.3f} suspiciously close to 1.0"


# ── Kuramoto integrity ──


class TestKuramotoIntegrity:
    def test_at_kc(self):
        """Kuramoto must operate at K = Kc = 1.0, not 1.14."""
        from substrates.kuramoto.adapter import KuramotoAdapter

        adapter = KuramotoAdapter(seed=42)
        assert abs(adapter._K - 1.0) < 0.01, f"K = {adapter._K}, expected Kc = 1.0"

    def test_gamma_near_unity(self):
        """Kuramoto at Kc should yield gamma in metastable band."""
        from substrates.kuramoto.adapter import KuramotoAdapter

        adapter = KuramotoAdapter(seed=42)
        topos, costs = [], []
        for _ in range(200):
            adapter.state()
            t, c = adapter.topo(), adapter.thermo_cost()
            if t > 1e-6 and c > 1e-6:
                topos.append(t)
                costs.append(c)
        r = compute_gamma(np.array(topos), np.array(costs))
        assert abs(r.gamma - 1.0) < 0.15, f"Kuramoto gamma={r.gamma:.3f} outside metastable"


# ── Gray-Scott ──


class TestGrayScott:
    def test_gamma_metastable(self):
        from substrates.gray_scott.adapter import GrayScottAdapter

        adapter = GrayScottAdapter(seed=42)
        topos, costs = [], []
        for _ in range(100):
            adapter.state()
            t, c = adapter.topo(), adapter.thermo_cost()
            if t > 1e-6 and c > 1e-6:
                topos.append(t)
                costs.append(c)
        r = compute_gamma(np.array(topos), np.array(costs))
        assert abs(r.gamma - 1.0) < 0.15, f"Gray-Scott gamma={r.gamma:.3f}"


# ── Zebrafish ──


class TestZebrafish:
    @pytest.mark.skipif(
        not Path("/home/neuro7/data/zebrafish/data/sample_inputs").exists(),
        reason="Zebrafish data not available",
    )
    def test_real_data(self):
        from substrates.zebrafish.adapter import ZebrafishAdapter

        adapter = ZebrafishAdapter(phenotype="WT", seed=42)
        adapter._ensure_loaded()
        assert adapter._loaded
        assert adapter._n_days > 30


# ── HRV PhysioNet ──
#
# The substrate is validated on three orthogonal axes:
#   1. test_compute_gamma_recovers_unity_from_synthetic_1f
#        Pure math: compute_gamma on a synthetic 1/f PSD (the same VLF band
#        the adapter uses) must recover γ ≈ 1.0. No network, no wfdb.
#   2. test_floor_minimum_enforced
#        Behaviour: _ensure_loaded raises when fewer than the floor of subjects
#        survive. Driven via monkeypatch — no network.
#   3. test_real_data_gamma_in_range
#        Integration: wfdb / PhysioNet NSR2DB yield physiological γ.
#        Opt-in via NEOSYNAPTEX_RUN_NETWORK_TESTS=1, since PhysioNet is an
#        external dependency that flakes; this lane stays off the PR critical
#        path and is exercised in a dedicated CI job.


class TestHRV:
    def test_compute_gamma_recovers_unity_from_synthetic_1f(self) -> None:
        from scipy.signal import welch

        rng = np.random.default_rng(42)
        n = 2**14
        fs = 4.0
        white = rng.standard_normal(n)
        spec = np.fft.rfft(white)
        freqs_full = np.fft.rfftfreq(n, d=1.0 / fs)
        amp = np.where(freqs_full > 0, freqs_full ** (-0.5), 0.0)
        pink = np.fft.irfft(spec * amp, n=n)

        f, psd = welch(pink, fs=fs, nperseg=1024)
        mask = (f >= 0.003) & (f <= 0.04) & (psd > 0)
        r = compute_gamma(f[mask], psd[mask])

        assert 0.7 <= r.gamma <= 1.3, f"synthetic 1/f gamma={r.gamma:.3f}"

    def test_floor_minimum_enforced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from substrates.hrv_physionet.adapter import HRVPhysioNetAdapter

        def _fake_load_below_floor(self_: HRVPhysioNetAdapter) -> None:
            self_._loaded = True
            self_._subj_gammas = [1.0] * (_HRV_FLOOR_MIN_SUBJECTS - 1)

        monkeypatch.setattr(HRVPhysioNetAdapter, "_load", _fake_load_below_floor)
        adapter = HRVPhysioNetAdapter(n_subjects=_HRV_FLOOR_MIN_SUBJECTS)
        with pytest.raises(RuntimeError, match="Insufficient HRV data"):
            adapter._ensure_loaded()

    @pytest.mark.skipif(
        not (_try_import("wfdb") and _RUN_NETWORK_TESTS),
        reason="set NEOSYNAPTEX_RUN_NETWORK_TESTS=1 to exercise PhysioNet",
    )
    def test_real_data_gamma_in_range(self) -> None:
        from substrates.hrv_physionet.adapter import HRVPhysioNetAdapter

        adapter = HRVPhysioNetAdapter()
        result = adapter.get_gamma_result()
        assert 0.5 <= result["gamma"] <= 1.5, f"HRV gamma={result['gamma']}"


# ── EEG PhysioNet ──


class TestEEG:
    @pytest.mark.skipif(
        not (_try_import("mne") and _try_import("specparam")),
        reason="mne or specparam not installed",
    )
    def test_gamma_in_range(self):
        from substrates.eeg_physionet.adapter import EEGPhysioNetAdapter

        adapter = EEGPhysioNetAdapter(n_subjects=3)
        result = adapter.get_gamma_result()
        assert 0.5 <= result["gamma"] <= 2.0, f"EEG gamma={result['gamma']}"


# ── Negative controls ──


class TestNegativeControls:
    def test_white_noise_separated(self):
        rng = np.random.default_rng(42)
        t = np.sort(rng.uniform(1, 100, 200))
        c = rng.uniform(1, 100, 200)
        r = compute_gamma(t, c)
        assert abs(r.gamma - 1.0) > 0.3 or r.verdict == "LOW_R2"

    def test_random_walk_separated(self):
        rng = np.random.default_rng(42)
        t = np.cumsum(rng.exponential(1.0, 200))
        c = rng.exponential(1.0, 200)
        r = compute_gamma(t, c)
        assert abs(r.gamma - 1.0) > 0.3 or r.verdict == "LOW_R2"

    def test_supercritical_separated(self):
        rng = np.random.default_rng(42)
        t = np.linspace(1, 100, 200)
        c = 100.0 / (t**2.0) + rng.normal(0, 0.01, 200)
        c = np.maximum(c, 1e-6)
        r = compute_gamma(t, c)
        assert abs(r.gamma - 1.0) > 0.3, f"Supercritical gamma={r.gamma:.3f}"


# ── Determinism ──


class TestDeterminism:
    def test_compute_gamma_deterministic(self):
        rng = np.random.default_rng(99)
        t = np.sort(rng.lognormal(2, 0.5, 100))
        c = 10.0 / t**1.0 + rng.normal(0, 0.1, 100)
        c = np.maximum(c, 1e-6)
        r1 = compute_gamma(t, c, seed=42)
        r2 = compute_gamma(t, c, seed=42)
        assert r1.gamma == r2.gamma
        assert r1.ci_low == r2.ci_low


# ── Tier classification ──


class TestTierClassification:
    def test_metastable_boundary(self):
        """|gamma - 1.0| < 0.15 → METASTABLE."""
        rng = np.random.default_rng(42)
        t = np.sort(rng.lognormal(2, 0.5, 100))
        c = 10.0 / t**1.05 + rng.normal(0, 0.05, 100)
        c = np.maximum(c, 1e-6)
        r = compute_gamma(t, c)
        if abs(r.gamma - 1.0) < 0.15 and r.r2 >= 0.3:
            assert r.verdict == "METASTABLE"

    def test_collapse_boundary(self):
        """|gamma - 1.0| >= 0.50 → COLLAPSE."""
        rng = np.random.default_rng(42)
        t = np.sort(rng.lognormal(2, 0.5, 100))
        c = 10.0 / t**2.0 + rng.normal(0, 0.05, 100)
        c = np.maximum(c, 1e-6)
        r = compute_gamma(t, c)
        if abs(r.gamma - 1.0) >= 0.50 and r.r2 >= 0.3:
            assert r.verdict == "COLLAPSE"
