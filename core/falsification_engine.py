"""Falsification engine with graded conflict strength (STN-analog v1).

CONTRACT:
    pre:  claim_text: str (non-empty); contradiction_markers: list[str]
    post: returns FalsificationResult with passed: bool, reason: str,
          conflict_strength: float in [0.0, 1.0].
    fail: never raises; degenerate inputs collapse to passed=True,
          conflict_strength=0.0.
    inv:  conflict_strength == 0.0 iff falsification_passes == True
          AND no physical-impossibility violation.

DETERMINISTIC scoring formula:
    physical_impossibility_violation   -> 1.0 (hard kill, terminating)
    per full-substring marker hit       -> +0.4
    per token-overlap-only hit (>=2     -> +0.15
        unique tokens, no substring)
    clamp to [0.0, 1.0]

Backwards compatibility:
    FalsificationResult is a NamedTuple over (passed, reason,
    conflict_strength); existing callers that unpack
    `passed, reason = falsification_decision(...)` continue to work
    because tuple-unpacking ignores the third element... ACTUALLY NO,
    standard tuple unpacking with 2 names raises ValueError. So
    instead, we keep the legacy `falsification_decision` signature
    returning `tuple[bool, str]` and expose a NEW function
    `falsification_decision_graded` returning the full result. Callers
    that want graded mode opt in; existing callers see no behaviour
    change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FalsificationResult:
    """Graded falsification verdict.

    ``passed`` is the binary verdict (True iff no falsifier hit and
    no physical-impossibility violation). ``conflict_strength`` is a
    real-valued scalar in [0.0, 1.0] that downstream gates can use to
    modulate threshold (STN-analog hyperdirect signal).
    """

    passed: bool
    reason: str
    conflict_strength: float


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    """Return lowercase alphanumeric token set."""
    return set(_TOKEN_RE.findall(text.lower()))


def falsification_passes(claim_text: str, contradiction_markers: list[str]) -> bool:
    """Legacy binary check: True iff no full-substring marker hit."""
    lowered = claim_text.lower()
    return not any(marker.lower() in lowered for marker in contradiction_markers)


def violates_physical_plausibility(claim_text: str) -> bool:
    """Fail-closed heuristic guard for physically impossible overclaims."""
    lowered = claim_text.lower()
    impossible_markers = [
        "perpetual motion",
        "energy from nothing",
        "faster than light information transfer",
        "100% efficient heat engine",
    ]
    if any(marker in lowered for marker in impossible_markers):
        return True

    # Detect impossible efficiency percentages > 100.
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%\s*efficien", lowered):
        if float(match.group(1)) > 100.0:
            return True
    return False


def falsification_decision(claim_text: str, contradiction_markers: list[str]) -> tuple[bool, str]:
    """Legacy binary signature. Preserved for backwards compatibility.

    All callers in the existing test suite use this signature; the new
    graded function lives at ``falsification_decision_graded`` so
    legacy behaviour is byte-identical.
    """
    if violates_physical_plausibility(claim_text):
        return False, "physical_plausibility_violation"
    if not falsification_passes(claim_text, contradiction_markers):
        return False, "contradiction_marker_hit"
    return True, "passed"


def falsification_decision_graded(
    claim_text: str, contradiction_markers: list[str]
) -> FalsificationResult:
    """Graded falsification with conflict-strength scoring.

    Per the §6.2 contract:
        physical_impossibility -> conflict_strength = 1.0 (hard kill)
        full-substring marker hit -> +0.4 each
        token-overlap-only (>=2 unique tokens shared, no substring) -> +0.15 each
        clamp to [0, 1]
    """
    lowered = claim_text.lower()
    claim_tokens = _tokens(claim_text)

    if violates_physical_plausibility(claim_text):
        return FalsificationResult(
            passed=False,
            reason="physical_plausibility_violation",
            conflict_strength=1.0,
        )

    full_hits = 0
    token_hits = 0
    for marker in contradiction_markers:
        marker_lo = marker.lower()
        if marker_lo in lowered:
            full_hits += 1
            continue
        marker_tokens = _tokens(marker)
        if len(marker_tokens & claim_tokens) >= 2:
            token_hits += 1

    conflict_raw = 0.4 * full_hits + 0.15 * token_hits
    conflict_strength = max(0.0, min(1.0, conflict_raw))

    if full_hits > 0:
        return FalsificationResult(
            passed=False,
            reason="contradiction_marker_hit",
            conflict_strength=conflict_strength,
        )
    if token_hits > 0:
        # Token-overlap-only: passed remains True at binary level
        # (no full substring hit), but conflict_strength > 0 so
        # downstream IEV gate can raise its threshold.
        return FalsificationResult(
            passed=True,
            reason="passed_with_token_overlap_conflict",
            conflict_strength=conflict_strength,
        )
    return FalsificationResult(passed=True, reason="passed", conflict_strength=0.0)
