"""Phase 3 — Null Screen stack.

Implements the empirical question:

    Does γ ≈ 1.0 separate the substrate signal from null/surrogate
    controls, or is it an estimator artefact?

Authoritative spec: ``docs/audit/PHASE_3_NULL_SCREEN_PLAN.md`` and
``docs/audit/PHASE_3_PROTOCOL.md``.

Phase 3 NEVER auto-promotes any substrate. Every ledger update is a
proposal only; the actual mutation lives in a separate human-reviewed
PR. ``CANON_VALIDATED_FROZEN`` is not touched.
"""

from __future__ import annotations

__all__ = [
    "PHASE_3_VERSION",
    "VERDICTS",
]

PHASE_3_VERSION: str = "3.0.0"

#: The full closed set of global verdicts a Phase 3 run may emit.
#: No softening words; no "PROBABLY", no "BORDERLINE", no "MARGINAL".
VERDICTS: tuple[str, ...] = (
    "SIGNAL_SEPARATES_FROM_NULL",
    "NULL_NOT_REJECTED",
    "ESTIMATOR_ARTIFACT_SUSPECTED",
    "INCONCLUSIVE",
)
