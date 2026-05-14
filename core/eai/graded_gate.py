"""Graded IEV-gate decision with conflict-modulated threshold (STN-analog v1).

CONTRACT:
    pre:  artifact: EvidenceArtifact; retention_hash: str;
          revalidation_passed: bool; conflict_strength: float in [0.0, 1.0].
    post: returns one of "EVIDENCE", "KILLED", "QUARANTINED" + a reason string.
          When conflict_strength == 0.0, the verdict is byte-identical to
          ``core.iev_gate.decide_intent_update``.
    fail: never raises; degenerate input collapses to QUARANTINED with
          a documented reason.
    inv:  required_evidence_paths(conflict_strength) is monotone
          non-decreasing in conflict_strength.

STN-analog mapping:
    conflict_strength <-> STN firing rate evoked by hyperdirect cortical input.
    Higher firing rate -> higher decision threshold -> harder for a candidate
    motor (here: integration) plan to release.

Threshold formula (deterministic):
    required_paths(c) = ceil(1 + c * 2)
        c = 0.0  -> required_paths = 1 (legacy single-path revalidation)
        c = 0.5  -> required_paths = 2
        c = 1.0  -> required_paths = 3

Backwards compatibility:
    This is a SEPARATE function from ``core.iev_gate.decide_intent_update``.
    Existing callers do not reach this module. Only the falsifiability
    test harness (``tools/eai/run_falsifiability_test.py``) and any
    explicit graded-mode caller use it.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass

from core.eai.intelligence_cycle import EvidenceArtifact

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class GradedGateDecision:
    """Verdict + reason + threshold trace.

    ``required_paths`` is the threshold the gate enforced. Recorded for
    audit so the falsifiability test report can verify the STN-analog
    threshold scaling without re-deriving it.
    """

    status: str  # "EVIDENCE" | "KILLED" | "QUARANTINED"
    reason: str
    required_paths: int
    available_paths: int


def required_revalidation_paths(conflict_strength: float) -> int:
    """Monotone non-decreasing threshold mapping."""
    if conflict_strength < 0.0:
        conflict_strength = 0.0
    if conflict_strength > 1.0:
        conflict_strength = 1.0
    return math.ceil(1.0 + conflict_strength * 2.0)


def _emergency_exit_enabled() -> bool:
    return os.getenv("EAI_EMERGENCY_EXIT", "").strip().lower() in {"1", "true", "yes", "on"}


def decide_with_graded_threshold(
    artifact: EvidenceArtifact,
    *,
    retention_hash: str | None,
    revalidation_passed: bool,
    conflict_strength: float,
) -> GradedGateDecision:
    """Graded IEV-gate decision.

    Behaviour:
        - If emergency exit env var set -> QUARANTINED.
        - If artifact.can_be_promoted() False -> KILLED (boundary or
          repro hash broken; same as legacy gate).
        - If retention_hash not SHA-256 hex -> QUARANTINED.
        - If revalidation_passed is False -> QUARANTINED.
        - Else: compute required_paths from conflict_strength.
          If len(artifact.revalidation_evidence_paths) >= required_paths
          -> EVIDENCE. Otherwise -> QUARANTINED with reason
          ``graded_threshold_unmet``.
    """
    required = required_revalidation_paths(conflict_strength)
    available = len(artifact.revalidation_evidence_paths)

    if _emergency_exit_enabled():
        return GradedGateDecision(
            status="QUARANTINED",
            reason="emergency_exit",
            required_paths=required,
            available_paths=available,
        )
    if not artifact.can_be_promoted():
        return GradedGateDecision(
            status="KILLED",
            reason="can_be_promoted_false",
            required_paths=required,
            available_paths=available,
        )
    if not _SHA256_HEX.fullmatch(retention_hash or ""):
        return GradedGateDecision(
            status="QUARANTINED",
            reason="retention_hash_invalid",
            required_paths=required,
            available_paths=available,
        )
    if not revalidation_passed:
        return GradedGateDecision(
            status="QUARANTINED",
            reason="revalidation_not_passed",
            required_paths=required,
            available_paths=available,
        )
    if available < required:
        return GradedGateDecision(
            status="QUARANTINED",
            reason="graded_threshold_unmet",
            required_paths=required,
            available_paths=available,
        )
    return GradedGateDecision(
        status="EVIDENCE",
        reason="promotion_allowed",
        required_paths=required,
        available_paths=available,
    )
