from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum


class RouteMode(str, Enum):
    CHEAP_TRIAGE = "cheap_triage"
    VERIFY = "verify"
    ESCALATE = "escalate"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class FinalStatus(str, Enum):
    CLOSED = "CLOSED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    ESCALATE = "ESCALATE"
    VERIFY = "VERIFY"
    CHEAP_TRIAGE = "CHEAP_TRIAGE"


ALLOWED_EPISTEMIC_STATUSES = {
    "derived",
    "measured",
    "inferred",
    "unverified analogy",
    "falsified",
    "retracted",
    "unknown",
}
_SAFE_CLAIM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SIGNAL_FIELDS = (
    "prediction_error",
    "uncertainty",
    "novelty",
    "evidence_risk",
    "reversibility",
    "load",
)


def _unit(name: str, v: float) -> float:
    if not isinstance(v, int | float):
        raise ValueError(f"{name} must be numeric")
    value = float(v)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be within [0,1]")
    return value


def _safe_claim_id(claim_id: str) -> str:
    if not isinstance(claim_id, str) or not claim_id:
        raise ValueError("claim_id must be non-empty")
    if claim_id in {".", ".."} or "/" in claim_id or "\\" in claim_id:
        raise ValueError("claim_id must be a safe path segment")
    if not _SAFE_CLAIM_ID.fullmatch(claim_id):
        raise ValueError("claim_id contains unsupported characters")
    return claim_id


@dataclass(frozen=True)
class ClaimSignal:
    claim_id: str
    prediction_error: float
    uncertainty: float
    novelty: float
    evidence_risk: float
    reversibility: float
    load: float
    epistemic_status: str = "derived"

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _safe_claim_id(self.claim_id))
        if self.epistemic_status not in ALLOWED_EPISTEMIC_STATUSES:
            raise ValueError(f"unsupported epistemic_status: {self.epistemic_status}")
        for key in _SIGNAL_FIELDS:
            object.__setattr__(self, key, _unit(key, getattr(self, key)))
