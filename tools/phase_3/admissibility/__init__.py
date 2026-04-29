"""Estimator Admissibility Trial — Phase 3 P0 measurement-operator gate.

This package answers a single metrological question: is the canonical
γ estimator (Theil–Sen on log–log of K vs C) usable as a *ruler*?

If the ruler is unstable, every downstream null-screen p-value, every
verdict label, every substrate claim built on top of it is structurally
invalid. The trial therefore gates Phase 3: a hypothesis test cannot
be admitted before the operator measuring its statistic has been
admitted.

The trial sweeps a synthetic-data grid (γ_true × N × σ × estimator),
computes 8 per-cell metrics, applies an admissibility rule (A1–A4),
and emits a six-field verdict block. The verdict is data-driven and
appears verbatim in the output JSON; nothing in this package may
soften, curate, or pre-judge a verdict.

Authoritative protocol: ``docs/audit/ESTIMATOR_ADMISSIBILITY_PROTOCOL.md``.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "ADMISSIBILITY_VERSION",
    "MIN_TRAJECTORY_LENGTH",
    "VERDICT_FIELDS",
]

ADMISSIBILITY_VERSION: str = "1.0.0"

#: Admissibility floor on trajectory length N from the M=100 reference
#: verdict (``result_hash: ed619996…``); downstream substrate adapters
#: must respect this lower bound for canonical-estimator outputs.
MIN_TRAJECTORY_LENGTH: Final[int] = 128

#: Closed, ordered list of required fields in every verdict block.
#: Spelling and casing are part of the contract — verdict consumers may
#: hash against this set.
VERDICT_FIELDS: tuple[str, ...] = (
    "ESTIMATOR_ADMISSIBILITY",
    "MINIMUM_TRAJECTORY_LENGTH",
    "CANONICAL_ESTIMATOR",
    "REPLACEMENT_ESTIMATOR",
    "HYPOTHESIS_TEST_STATUS",
    "FINAL_VERDICT",
)
