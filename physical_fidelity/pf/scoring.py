"""The scoring oracle S (GAP-O-01) -- the meta-gap.

The audit's central finding: the target ``88-92/100`` is undefined because no
measurement function, reference, or baseline exists. This module supplies all
three so the score becomes computable -- but it is an **admissibility** score
(does the apparatus reproduce known physics?), never a science claim.

    S = sum_i w_i * s_i(m_i, r_i) / sum_i w_i

where m_i is the measured value of metric i, r_i its analytic reference, w_i its
weight, and s_i a monotone-in-accuracy scoring function mapping to [0, 100].

Honesty contract (per project standing guidance):
* S is reported with the tier label ADMISSIBILITY, not VALIDATED/PROVEN.
* No metric is hand-set; every s_i is computed from a verifier in this package.
* The baseline S0 is whatever the apparatus actually measures -- we do not
  reverse-engineer inputs to hit a target band.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def relative_accuracy_score(measured: float, reference: float, *, tol: float) -> float:
    """Monotone score in [0,100]: 100 at exact match, decaying past tolerance.

    s = 100 * exp(-(rel_err / tol)^2), rel_err normalized by |reference| (or by
    the measured scale if reference ~ 0). Smooth and monotone in accuracy.
    """
    scale = max(abs(reference), abs(measured), 1e-12)
    rel_err = abs(measured - reference) / scale
    return float(100.0 * np.exp(-((rel_err / tol) ** 2)))


def boolean_score(passed: bool) -> float:
    """Hard pass/fail metric -> {100, 0}."""
    return 100.0 if passed else 0.0


@dataclass
class MetricResult:
    """One scored metric on the card."""

    key: str
    measured: float
    reference: float
    score: float
    weight: float
    tier: str  # ANCHORED (analytic ref) | MEASURED | NOT_IMPLEMENTED
    note: str = ""


@dataclass
class ScoreCard:
    """Aggregate admissibility scorecard with explicit oracle S."""

    metrics: list[MetricResult] = field(default_factory=list)
    classification: str = "ADMISSIBILITY"  # never VALIDATED

    def add(self, m: MetricResult) -> None:
        self.metrics.append(m)

    @property
    def score(self) -> float:
        if not self.metrics:
            return float("nan")
        wsum = sum(m.weight for m in self.metrics)
        if wsum <= 0:
            return float("nan")
        return float(sum(m.score * m.weight for m in self.metrics) / wsum)

    def to_dict(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            "S_admissibility": round(self.score, 2),
            "n_metrics": len(self.metrics),
            "metrics": [
                {
                    "key": m.key,
                    "measured": m.measured,
                    "reference": m.reference,
                    "score": round(m.score, 2),
                    "weight": m.weight,
                    "tier": m.tier,
                    "note": m.note,
                }
                for m in self.metrics
            ],
        }
