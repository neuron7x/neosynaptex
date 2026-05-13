from __future__ import annotations

import re


def falsification_passes(claim_text: str, contradiction_markers: list[str]) -> bool:
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
    if violates_physical_plausibility(claim_text):
        return False, "physical_plausibility_violation"
    if not falsification_passes(claim_text, contradiction_markers):
        return False, "contradiction_marker_hit"
    return True, "passed"
