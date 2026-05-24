from __future__ import annotations

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


def run_controls(
    claims: list[ClaimSignal],
    priorities: list[float],
    seed: int,
) -> ControlResults:
    if not claims or not priorities:
        return ControlResults(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False)

    rng = random.Random(seed)  # nosec B311: deterministic simulation control, not crypto.
    n = len(claims)
    main_mean = sum(priorities) / n
    random_mean = sum(rng.random() for _ in claims) / n
    margin_mean = sum(max(0.0, c.evidence_risk - c.uncertainty) for c in claims) / n
    no_dopa_mean = sum(c.evidence_risk for c in claims) / n
    permuted = priorities[:]
    rng.shuffle(permuted)
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

    passed = all(
        main_mean > baseline
        for baseline in (
            random_mean,
            margin_mean,
            no_dopa_mean,
            overactivation_mean,
            trivial_majority,
        )
    )
    return ControlResults(
        random_mean,
        margin_mean,
        no_dopa_mean,
        permuted_mean,
        overactivation_mean,
        trivial_majority,
        passed,
    )
