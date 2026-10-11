"""Tests for EVL Channel B — collector + analyzer + truth criterion.

7 improvement areas covered:
1. Task generator determinism (seeded)
2. Regime classification integration
3. Full EVL pipeline test coverage
4. DFA as second H estimator
5. Phase contrast effect sizes
6. Truth criterion integration with analyzer
7. Cross-session aggregation

Author: Yaroslav Vasylenko / neuron7xLab
License: AGPL-3.0-or-later
"""

import importlib.util

import numpy as np
import pytest


# ===================================================================
# 1. Task generator determinism
# ===================================================================
class TestTaskDeterminism:
    def test_arithmetic_reproducible(self):
        import random

        from evl.collector import gen_arithmetic

        random.seed(42)
        t1 = gen_arithmetic(2)
        random.seed(42)
        t2 = gen_arithmetic(2)
        assert t1.ground_truth == t2.ground_truth
        assert t1.prompt == t2.prompt

    def test_all_generators_produce_valid_tasks(self):
        import random

        from evl.collector import GENERATORS, Task

        random.seed(0)
        for gen in GENERATORS:
            for diff in range(1, 6):
                task = gen(diff)
                assert isinstance(task, Task)
                assert task.ground_truth != ""
                assert task.difficulty == diff
                assert task.task_type != ""

    def test_ground_truth_correctness_arithmetic(self):
        import random

        from evl.collector import gen_arithmetic

        random.seed(99)
        for _ in range(50):
            t = gen_arithmetic(2)
            # Parse and verify
            parts = t.prompt.replace("Compute: ", "").split()
            a, op, b = int(parts[0]), parts[1], int(parts[2])
            if op == "+":
                expected = a + b
            elif op == "-":
                expected = a - b
            else:
                expected = a * b
            assert str(expected) == t.ground_truth, f"{t.prompt} -> {t.ground_truth} != {expected}"

    def test_ground_truth_correctness_modular(self):
        import random

        from evl.collector import gen_modular

        random.seed(99)
        for _ in range(30):
            t = gen_modular(2)
            # Parse (a * b) mod m
            prompt = t.prompt
            inner = prompt.split("(")[1].split(")")[0]
            a, b = inner.split(" * ")
            m = int(prompt.split("mod ")[1].split(" ")[0])
            expected = (int(a) * int(b)) % m
            assert str(expected) == t.ground_truth

    def test_logic_ground_truth(self):
        import random

        from evl.collector import gen_logic

        random.seed(42)
        for _ in range(20):
            t = gen_logic(2)
            assert t.ground_truth in ("True", "False")


# ===================================================================
# 2. Regime classification integration
# ===================================================================
class TestRegimeIntegration:
    def test_psd_regime_labels(self):
        from evl.analyze import compute_psd_slope

        # White noise -> beta ~ 0
        rng = np.random.default_rng(42)
        white = rng.standard_normal(200).tolist()
        r = compute_psd_slope(white, fs=1.0)
        if r["status"] == "OK":
            assert isinstance(r["beta"], float)

    def test_regime_from_gamma_thresholds(self):
        from contracts.invariants import gamma_regime

        # These are the canonical thresholds
        assert gamma_regime(1.0) == "METASTABLE"
        assert gamma_regime(0.55) == "CRITICAL"
        assert gamma_regime(0.3) == "COLLAPSE"


# ===================================================================
# 3. EVL pipeline integration
# ===================================================================
class TestEVLPipeline:
    def _make_session(self, n_tasks=30, perturbation=False):
        """Create synthetic session data for testing."""
        rng = np.random.default_rng(42)
        decisions = []
        t = 0
        for i in range(n_tasks):
            t += int(rng.uniform(3e9, 15e9))  # 3-15s between tasks
            phase = "baseline"
            if perturbation and 10 <= i < 20:
                phase = "perturbation:time_pressure"
            elif perturbation and i >= 20:
                phase = "recovery"
            decisions.append(
                {
                    "t_ns": t,
                    "utc_ns": t,
                    "session_id": "test_session",
                    "task_id": f"t_{i:03d}",
                    "task_type": "arithmetic",
                    "difficulty": 2,
                    "phase": phase,
                    "latency_ms": round(float(rng.lognormal(8.0, 0.5)), 2),
                    "correct": int(rng.random() > 0.2),
                    "timed_out": 0,
                    "prompt": f"Compute: {rng.integers(100, 999)} + {rng.integers(100, 999)}",
                    "expected": str(rng.integers(200, 1998)),
                    "given": str(rng.integers(200, 1998)),
                }
            )
        return decisions

    def test_quality_gates_pass(self):
        from evl.analyze import check_quality

        decisions = self._make_session(30)
        gates = check_quality(decisions)
        assert gates["sufficient_data"] is True
        assert gates["has_correct_field"] is True
        assert gates["has_timestamps"] is True

    def test_quality_gates_fail_insufficient(self):
        from evl.analyze import check_quality

        gates = check_quality(self._make_session(5))
        assert gates["sufficient_data"] is False

    def test_compute_stats(self):
        from evl.analyze import compute_stats

        stats = compute_stats(self._make_session(30))
        assert stats["n_tasks"] == 30
        assert 0 <= stats["accuracy_pct"] <= 100
        assert stats["latency_mean_ms"] > 0
        assert stats["latency_cv"] is not None

    def test_phase_contrast(self):
        from evl.analyze import compute_phase_contrast

        contrast = compute_phase_contrast(self._make_session(30, perturbation=True))
        assert "baseline" in contrast
        assert "perturbation" in contrast
        assert "recovery" in contrast

    def test_psd_slope_on_synthetic(self):
        from evl.analyze import compute_psd_slope

        rng = np.random.default_rng(42)
        # 1/f noise (beta ~ 1.0)
        white = rng.standard_normal(256)
        pink = np.cumsum(white)  # integration -> beta += 2
        r = compute_psd_slope(pink.tolist(), fs=1.0)
        assert r["status"] == "OK"
        assert r["beta"] > 0.5  # should be brownian-ish

    def test_full_analyze_pipeline(self):
        from evl.analyze import (
            check_quality,
            compute_phase_contrast,
            compute_psd_slope,
            compute_stats,
        )

        decisions = self._make_session(40, perturbation=True)
        gates = check_quality(decisions)
        stats = compute_stats(decisions)
        lat = [d["latency_ms"] for d in decisions]
        compute_psd_slope(lat, fs=0.1)
        contrast = compute_phase_contrast(decisions)
        assert gates["sufficient_data"]
        assert stats["n_tasks"] == 40
        assert isinstance(contrast, dict)


# ===================================================================
# 4. DFA (Detrended Fluctuation Analysis)
# ===================================================================
class TestDFA:
    def test_dfa_white_noise(self):
        """White noise: H ~ 0.5."""
        from evl.dfa import dfa_exponent

        rng = np.random.default_rng(42)
        signal = rng.standard_normal(1024)
        H = dfa_exponent(signal)
        assert 0.3 < H < 0.7, f"White noise H={H}, expected ~0.5"

    def test_dfa_brownian(self):
        """Brownian (cumsum of white): H ~ 1.5 (or after detrending ~1.0+)."""
        from evl.dfa import dfa_exponent

        rng = np.random.default_rng(42)
        signal = np.cumsum(rng.standard_normal(1024))
        H = dfa_exponent(signal)
        assert H > 0.8, f"Brownian H={H}, expected >0.8"

    def test_dfa_short_signal(self):
        from evl.dfa import dfa_exponent

        assert dfa_exponent(np.array([1.0, 2.0, 3.0])) is None

    def test_dfa_gamma_conversion(self):
        """gamma_PSD = 2H + 1 verified through DFA."""
        from evl.dfa import dfa_exponent

        rng = np.random.default_rng(42)
        signal = rng.standard_normal(2048)
        H = dfa_exponent(signal)
        gamma = 2 * H + 1
        assert 1.5 < gamma < 2.5, f"gamma={gamma} from H={H}"


# ===================================================================
# 5. Phase contrast effect size
# ===================================================================
class TestPhaseEffectSize:
    def test_cohens_d_computation(self):
        from evl.effect_size import cohens_d

        a = np.array([100, 110, 105, 95, 108])
        b = np.array([200, 210, 195, 205, 198])
        d = cohens_d(a, b)
        assert d < -2.0  # large effect: b much larger than a

    def test_cohens_d_zero(self):
        from evl.effect_size import cohens_d

        a = np.array([100, 100, 100])
        b = np.array([100, 100, 100])
        assert abs(cohens_d(a, b)) < 0.01

    def test_phase_contrast_with_effect(self):
        from evl.effect_size import phase_contrast_effect

        rng = np.random.default_rng(42)
        baseline_lat = rng.lognormal(7.0, 0.3, 20)
        stress_lat = rng.lognormal(7.5, 0.5, 15)
        result = phase_contrast_effect(baseline_lat, stress_lat)
        assert "cohens_d" in result
        assert "lat_ratio" in result
        assert result["lat_ratio"] > 1.0  # stress should be slower


# ===================================================================
# 6. Truth criterion integration (requires bn_syn.transfer_entropy)
# ===================================================================
def _can_import(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ModuleNotFoundError, ValueError):
        return False


@pytest.mark.skipif(
    not _can_import("substrates.bn_syn.transfer_entropy"),
    reason="substrates.bn_syn.transfer_entropy unavailable",
)
class TestTruthCriterionIntegration:
    def test_synchronized_channels(self):
        from contracts.truth_criterion import evaluate_truth_criterion

        rng = np.random.default_rng(42)
        T = 500
        base = np.cumsum(rng.standard_normal(T))
        shift = np.zeros(T)
        shift[240:260] = 3.0
        ch1 = base + shift + rng.standard_normal(T) * 0.5
        ch2 = base * 0.8 + shift * 1.2 + rng.standard_normal(T) * 0.5
        r = evaluate_truth_criterion(ch1, ch2, n_surrogates=49)
        assert r.synchronized is True
        assert r.wcoh_above_threshold is True
        assert r.te_above_threshold is True

    def test_independent_rejected(self):
        from contracts.truth_criterion import evaluate_truth_criterion

        rng = np.random.default_rng(99)
        ch1 = np.cumsum(rng.standard_normal(500))
        ch2 = np.cumsum(rng.standard_normal(500))
        r = evaluate_truth_criterion(ch1, ch2, n_surrogates=19)
        assert r.verdict != "REGIME_INVARIANT"

    def test_epsilon_calibration(self):
        from contracts.truth_criterion import calibrate_epsilon

        betas = np.array([0.9, 1.1, 0.95, 1.05, 1.0, 0.98, 1.02])
        eps = calibrate_epsilon(betas, k=2.0)
        assert 0.05 <= eps <= 0.50


# ===================================================================
# 7. Cross-session aggregator
# ===================================================================
class TestCrossSession:
    def test_aggregate_sessions(self):
        from evl.aggregator import aggregate_sessions

        sessions = [
            {"beta": 0.95, "accuracy_pct": 85, "n_tasks": 30, "session": "s1"},
            {"beta": 1.05, "accuracy_pct": 80, "n_tasks": 25, "session": "s2"},
            {"beta": 1.10, "accuracy_pct": 90, "n_tasks": 35, "session": "s3"},
        ]
        agg = aggregate_sessions(sessions)
        assert abs(agg["beta_mean"] - np.mean([0.95, 1.05, 1.10])) < 0.01
        assert agg["n_sessions"] == 3
        assert "beta_trajectory" in agg

    def test_convergence_detection(self):
        from evl.aggregator import detect_convergence

        betas = [1.5, 1.3, 1.2, 1.1, 1.05, 1.02, 1.01]
        result = detect_convergence(betas)
        assert bool(result["converging"]) is True
        assert result["slope"] < 0
