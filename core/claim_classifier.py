from __future__ import annotations

from core.eai.intelligence_cycle import ClaimType

KEYWORD_TO_TYPE: list[tuple[str, ClaimType]] = [
    ("predict", ClaimType.PREDICTIVE),
    ("causal", ClaimType.CAUSAL),
    ("security", ClaimType.SECURITY),
    ("protocol", ClaimType.SOFTWARE),
    ("compliance", ClaimType.COMPLIANCE),
]


def classify_claim_type(claim_text: str) -> ClaimType:
    lowered = claim_text.lower()
    for keyword, claim_type in KEYWORD_TO_TYPE:
        if keyword in lowered:
            return claim_type
    return ClaimType.FACTUAL
