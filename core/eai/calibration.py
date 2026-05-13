from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Metrics:
    total: int
    false_promotion_rate: float
    quarantine_accuracy: float
    overclaim_trap_detection: float
    false_bucket_total: int
    ambiguous_bucket_total: int
    adversarial_bucket_total: int
    unknown_bucket_total: int


FORBIDDEN = ["consciousness", "many agents agree", "authority"]


def gated_decision(text: str) -> str:
    t = text.lower()
    if any(k in t for k in FORBIDDEN):
        return "KILLED"
    if "needs tests" in t or "likely" in t:
        return "QUARANTINED"
    return "EVIDENCE"


def run_calibration(path: Path) -> Metrics:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    promoted_false = 0
    false_total = 0
    amb_ok = 0
    amb_total = 0
    traps_ok = 0
    traps_total = 0
    unknown_total = 0

    for r in rows:
        pred = gated_decision(r["claim_text"])
        bucket = r["bucket"]
        if bucket == "false":
            false_total += 1
            promoted_false += int(pred == "EVIDENCE")
        elif bucket == "ambiguous":
            amb_total += 1
            amb_ok += int(pred == "QUARANTINED")
        elif bucket == "adversarial_overclaim":
            traps_total += 1
            traps_ok += int(pred != "EVIDENCE")
        else:
            unknown_total += 1

    return Metrics(
        total=len(rows),
        false_promotion_rate=promoted_false / max(1, false_total),
        quarantine_accuracy=amb_ok / max(1, amb_total),
        overclaim_trap_detection=traps_ok / max(1, traps_total),
        false_bucket_total=false_total,
        ambiguous_bucket_total=amb_total,
        adversarial_bucket_total=traps_total,
        unknown_bucket_total=unknown_total,
    )


def contradiction_decision(source: str, candidate: str) -> str:
    s = source.lower()
    c = candidate.lower()
    if (
        ("limited to local test" in s and "universal" in c)
        or ("not externally validated" in s and "validated" in c)
        or ("correlation only" in s and "causal" in c)
        or ("demo-ready" in s and "enterprise-ready" in c)
    ):
        return "KILLED"
    if "ambiguous" in s and "confirmed" in c:
        return "QUARANTINED"
    return "EVIDENCE"


def run_contradiction_calibration(path: Path) -> Metrics:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    false_promo = 0
    for r in rows:
        pred = contradiction_decision(r["source"], r["candidate"])
        if r["expected_status"] in {"KILLED", "QUARANTINED"} and pred == "EVIDENCE":
            false_promo += 1
    total = len(rows)
    return Metrics(
        total=total,
        false_promotion_rate=false_promo / max(total, 1),
        quarantine_accuracy=0.0,
        overclaim_trap_detection=0.0,
        false_bucket_total=total,
        ambiguous_bucket_total=0,
        adversarial_bucket_total=0,
        unknown_bucket_total=0,
    )
