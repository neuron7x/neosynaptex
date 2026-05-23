"""Hallucination Thermodynamics Benchmark.

Task 4 deliverable: validates that entropy change (ΔS), dissipation, and
coherence predict hallucination events.  Generates canonical scenarios
(clean / ambiguous / adversarial), runs them through the coherence
state-space model, and computes accuracy, calibration, and robustness
metrics.

Design
------
* ΔS_t = S_{t+1} − S_t.  A trajectory with *cumulative* ΔS ≤ 0 signals
  coherence collapse → hallucination predicted.
* Self-contained: all scenarios are synthesised from ``CoherenceStateSpace``.
* Deterministic given a seed.
* numpy-only, mypy --strict clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from core.coherence_state_space import (
    CoherenceState,
    CoherenceStateSpace,
)

__all__ = [
    "BenchmarkScenario",
    "BenchmarkResult",
    "BenchmarkSummary",
    "HallucinationBenchmark",
]

FloatArray = NDArray[np.float64]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

_VALID_CATEGORIES: Final[frozenset[str]] = frozenset({"clean", "ambiguous", "adversarial"})


@dataclass(frozen=True)
class BenchmarkScenario:
    """A single benchmark scenario with ground-truth label."""

    name: str
    category: str
    initial_state: CoherenceState
    inputs: FloatArray
    expected_hallucination: bool
    description: str

    def __post_init__(self) -> None:
        if self.category not in _VALID_CATEGORIES:
            raise ValueError(
                f"category must be one of {sorted(_VALID_CATEGORIES)}, got {self.category!r}"
            )
        if self.inputs.ndim != 2 or self.inputs.shape[1] != 2:
            raise ValueError(f"inputs must have shape (n_steps, 2), got {self.inputs.shape}")


@dataclass(frozen=True)
class BenchmarkResult:
    """Result of running a single scenario."""

    scenario_name: str
    delta_S_trajectory: FloatArray  # noqa: N815
    final_delta_S: float  # noqa: N815
    predicted_hallucination: bool
    actual_hallucination: bool
    correct: bool
    coherence_trajectory: FloatArray
    gamma_trajectory: FloatArray


@dataclass(frozen=True)
class BenchmarkSummary:
    """Aggregate metrics across all benchmark results."""

    total: int
    correct: int
    accuracy: float
    precision: float
    recall: float
    delta_s_distribution: FloatArray
    calibration_error: float
    category_accuracy: dict[str, float]


# ---------------------------------------------------------------------------
# Benchmark engine
# ---------------------------------------------------------------------------

_N_STEPS: Final[int] = 60


class HallucinationBenchmark:
    """Generates and evaluates hallucination-thermodynamics scenarios.

    Parameters
    ----------
    model : CoherenceStateSpace
        The coherence state-space model used to generate trajectories.
    delta_s_threshold : float
        Cumulative ΔS below (or equal to) this value → hallucination predicted.
    """

    def __init__(
        self,
        model: CoherenceStateSpace,
        delta_s_threshold: float = 0.0,
    ) -> None:
        self._model = model
        self._threshold = delta_s_threshold

    # -- Scenario catalogue -------------------------------------------

    def scenarios(self) -> list[BenchmarkScenario]:
        """Return the canonical set of ≥15 benchmark scenarios."""
        out: list[BenchmarkScenario] = []
        n = _N_STEPS

        # --- 5 clean scenarios: stable γ≈1, low noise, no adversarial input ---
        for i in range(5):
            s0 = 0.45 + 0.02 * i  # 0.45 … 0.53
            out.append(
                BenchmarkScenario(
                    name=f"clean_{i}",
                    category="clean",
                    initial_state=CoherenceState(S=s0, gamma=1.0, E_obj=0.0, sigma2=1e-4),
                    inputs=np.zeros((n, 2), dtype=np.float64),
                    expected_hallucination=False,
                    description=f"Stable start S={s0:.2f}, γ=1, no adversarial load",
                )
            )

        # --- 5 ambiguous scenarios: γ near boundary, moderate noise ---
        ambig_params: list[tuple[float, float, float, float, bool]] = [
            (0.40, 0.90, 0.10, 5e-3, False),
            (0.35, 0.85, 0.15, 8e-3, True),
            (0.50, 1.10, 0.05, 4e-3, False),
            (0.30, 0.80, 0.20, 1e-2, True),
            (0.45, 0.95, 0.12, 6e-3, False),
        ]
        for i, (s0, g0, e0, v0, exp) in enumerate(ambig_params):
            # Moderate positive u_E to sustain objection pressure
            inp = np.zeros((n, 2), dtype=np.float64)
            inp[:, 1] = 0.05 * (i + 1) / 5  # 0.01 … 0.05
            out.append(
                BenchmarkScenario(
                    name=f"ambiguous_{i}",
                    category="ambiguous",
                    initial_state=CoherenceState(S=s0, gamma=g0, E_obj=e0, sigma2=v0),
                    inputs=inp,
                    expected_hallucination=exp,
                    description=(f"Boundary regime S={s0}, γ={g0}, E={e0}, σ²={v0}"),
                )
            )

        # --- 5 adversarial scenarios: high E_obj, γ far from 1, high noise ---
        for i in range(5):
            g0 = 0.5 - 0.05 * i  # 0.50 … 0.30
            e0 = 0.5 + 0.1 * i  # 0.50 … 0.90
            v0 = 0.02 + 0.01 * i
            inp = np.zeros((n, 2), dtype=np.float64)
            inp[:, 1] = 0.3 + 0.1 * i  # strong adversarial E drive
            out.append(
                BenchmarkScenario(
                    name=f"adversarial_{i}",
                    category="adversarial",
                    initial_state=CoherenceState(S=0.50, gamma=g0, E_obj=e0, sigma2=v0),
                    inputs=inp,
                    expected_hallucination=True,
                    description=(
                        f"Adversarial: γ={g0:.2f}, E_obj={e0:.1f}, σ²={v0}, strong u_E drive"
                    ),
                )
            )

        return out

    # -- Run ----------------------------------------------------------

    def run_scenario(
        self,
        scenario: BenchmarkScenario,
        rng: np.random.Generator,
    ) -> BenchmarkResult:
        """Execute a single scenario and return the result."""
        n_steps = scenario.inputs.shape[0]
        traj = self._model.rollout(
            scenario.initial_state,
            n_steps=n_steps,
            inputs=scenario.inputs,
            rng=rng,
        )

        coherence = traj[:, 0].copy()
        gamma = traj[:, 1].copy()

        # ΔS_t = S_{t+1} - S_t
        delta_s = np.diff(coherence)
        cumulative_delta_s = float(np.sum(delta_s))

        predicted = cumulative_delta_s <= self._threshold

        return BenchmarkResult(
            scenario_name=scenario.name,
            delta_S_trajectory=delta_s,
            final_delta_S=cumulative_delta_s,
            predicted_hallucination=predicted,
            actual_hallucination=scenario.expected_hallucination,
            correct=(predicted == scenario.expected_hallucination),
            coherence_trajectory=coherence,
            gamma_trajectory=gamma,
        )

    def run_all(
        self,
        rng: np.random.Generator,
    ) -> list[BenchmarkResult]:
        """Run every canonical scenario."""
        return [self.run_scenario(s, rng) for s in self.scenarios()]

    # -- Summary ------------------------------------------------------

    @staticmethod
    def summary(results: list[BenchmarkResult]) -> BenchmarkSummary:
        """Compute aggregate metrics from a list of benchmark results."""
        total = len(results)
        if total == 0:
            return BenchmarkSummary(
                total=0,
                correct=0,
                accuracy=0.0,
                precision=0.0,
                recall=0.0,
                delta_s_distribution=np.array([], dtype=np.float64),
                calibration_error=0.0,
                category_accuracy={},
            )

        correct = sum(1 for r in results if r.correct)
        accuracy = correct / total

        # Precision / recall for hallucination prediction
        tp = sum(1 for r in results if r.predicted_hallucination and r.actual_hallucination)
        fp = sum(1 for r in results if r.predicted_hallucination and not r.actual_hallucination)
        fn = sum(1 for r in results if not r.predicted_hallucination and r.actual_hallucination)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        delta_s_dist = np.array([r.final_delta_S for r in results], dtype=np.float64)

        # Calibration error: |predicted hallucination rate - actual hallucination rate|
        predicted_rate = sum(1 for r in results if r.predicted_hallucination) / total
        actual_rate = sum(1 for r in results if r.actual_hallucination) / total
        calibration_error = abs(predicted_rate - actual_rate)

        # Per-category accuracy
        cat_correct: dict[str, list[bool]] = {}
        for r in results:
            # Infer category from scenario name prefix
            cat = _category_from_name(r.scenario_name)
            cat_correct.setdefault(cat, []).append(r.correct)

        category_accuracy = {cat: sum(v) / len(v) for cat, v in cat_correct.items()}

        return BenchmarkSummary(
            total=total,
            correct=correct,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            delta_s_distribution=delta_s_dist,
            calibration_error=calibration_error,
            category_accuracy=category_accuracy,
        )

    # -- Perturbation robustness -------------------------------------

    def perturb_and_rerun(
        self,
        scenario: BenchmarkScenario,
        n_perturbations: int,
        noise_scale: float,
        rng: np.random.Generator,
    ) -> list[BenchmarkResult]:
        """Rerun a scenario with small input perturbations.

        For each perturbation, Gaussian noise N(0, noise_scale) is added
        to every element of ``scenario.inputs``.  Returns one result per
        perturbation.
        """
        results: list[BenchmarkResult] = []
        for i in range(n_perturbations):
            # Spawn a child RNG so perturbation noise is isolated from model noise
            child = np.random.default_rng(rng.integers(0, 2**63))
            perturbed_inputs = scenario.inputs + child.normal(
                0.0, noise_scale, size=scenario.inputs.shape
            )
            perturbed = BenchmarkScenario(
                name=scenario.name,
                category=scenario.category,
                initial_state=scenario.initial_state,
                inputs=perturbed_inputs,
                expected_hallucination=scenario.expected_hallucination,
                description=scenario.description,
            )
            model_rng = np.random.default_rng(rng.integers(0, 2**63))
            results.append(self.run_scenario(perturbed, model_rng))
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _category_from_name(name: str) -> str:
    """Extract category prefix from a scenario name."""
    for cat in ("clean", "ambiguous", "adversarial"):
        if name.startswith(cat):
            return cat
    return "unknown"
