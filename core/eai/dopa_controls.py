"""Priority-only diagnostic controls; never evidence of verified closure.

A permutation preserves the sample mean. Comparing priority means with
different-scale proxy features cannot qualify an experimental verifier.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

from core.eai.dopa_types import ClaimSignal


@dataclass(frozen=True)
class ControlResults:
    random_routing_mean_priority: float
    margin_baseline_mean_priority: float
    no_dopamine_mean_priority: float
    permutation_break_mean_priority: float
    overactivation_mean_priority: float
    trivial_majority_mean_priority: float
    passed: bool
    validity: str = "UNTESTED"
    reason: str = "priority_means_cannot_validate_verification_benefit"


def run_controls(
    claims: list[ClaimSignal],
    priorities: list[float],
    seed: int,
) -> ControlResults:
    """Return legacy diagnostic scalars, never construct-valid negative controls.

    Meaningful controls require matched actions/costs and an independent
    outcome oracle. These proxy means alone do NOT permit a PASS verdict.
    """
    if len(claims) != len(priorities):
        raise ValueError("control_claim_priority_length_mismatch")
    if any(isinstance(x, bool) or not isinstance(x, (float, int))
           or not math.isfinite(x) or x < 0 for x in priorities):
        raise ValueError("control_priority_invalid")
    if not claims:
        return ControlResults(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False)

    rng = random.Random(seed)  # deterministic simulation, not cryptographic.
    n = len(claims)
    random_mean = sum(rng.random() for _ in claims) / n
    margin_mean = sum(max(0.0, c.evidence_risk - c.uncertainty) for c in claims) / n
    no_dopa_mean = sum(c.evidence_risk for c in claims) / n
    permuted = priorities[:]
    rng.shuffle(permuted)
    # A permutation leaves this statistic invariant; diagnostic, not evidence.
    permuted_mean = sum(permuted) / n
    overactivation_mean = sum(p * 0.2 for p in priorities) / n

    majority_load = Counter(round(c.load, 2) for c in claims).most_common(1)[0][0]
    trivial_majority = (
        sum(
            max(0.0, 1.0 - abs(c.load - majority_load)) * c.evidence_risk
            for c in claims
        )
        / n
    )
    return ControlResults(
        random_mean,
        margin_mean,
        no_dopa_mean,
        permuted_mean,
        overactivation_mean,
        trivial_majority,
        False,
    )
