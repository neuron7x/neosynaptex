from __future__ import annotations


def reject_obvious_overclaim(claim_text: str) -> bool:
    lowered = claim_text.lower()
    triggers = ["always true", "proves consciousness", "universal law", "100% guaranteed"]
    return any(trigger in lowered for trigger in triggers)
