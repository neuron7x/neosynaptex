"""Evidence hardening — audit, grade, and seal gamma_ledger.json entries.

The weakest link in NFI is not the theory or code — it's the evidence.
This module:

1. Grades each ledger entry on 6 quality axes (0–1 each)
2. Computes an overall Evidence Strength Score (ESS)
3. Flags entries that weaken the universality claim
4. Generates SHA-256 provenance seals for data + code
5. Produces an honest audit report

Quality axes:
    Q1: Statistical significance (p-value present and < 0.05)
    Q2: Effect size (R² > 0.5)
    Q3: Sample adequacy (n_pairs >= 10)
    Q4: Confidence interval (CI present and contains 1.0)
    Q5: Data provenance (SHA-256 hash present)
    Q6: Code provenance (adapter hash present)

ESS = mean(Q1..Q6). Grading:
    A: ESS >= 0.8 (publication-ready)
    B: ESS >= 0.6 (solid, minor gaps)
    C: ESS >= 0.4 (usable, needs work)
    D: ESS >= 0.2 (weak, flag for reviewer)
    F: ESS < 0.2 (unreliable, exclude from claims)
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "AuditReport",
    "EntryGrade",
    "audit_ledger",
    "compute_code_hash",
    "compute_data_hash",
]

_P_THRESHOLD: Final[float] = 0.05
_R2_THRESHOLD: Final[float] = 0.5
_N_THRESHOLD: Final[int] = 10


@dataclass(frozen=True)
class EntryGrade:
    """Quality grade for a single ledger entry."""

    entry_id: str
    gamma: float
    status: str
    q_significance: float  # Q1: p-value quality
    q_effect_size: float  # Q2: R² quality
    q_sample_size: float  # Q3: n_pairs quality
    q_confidence_interval: float  # Q4: CI quality
    q_data_provenance: float  # Q5: data hash
    q_code_provenance: float  # Q6: code hash
    ess: float  # Evidence Strength Score
    grade: str  # A/B/C/D/F
    issues: tuple[str, ...]  # list of specific issues
    is_reliable: bool  # ESS >= 0.4


@dataclass(frozen=True)
class AuditReport:
    """Full audit of the gamma ledger."""

    total_entries: int
    validated_entries: int
    grades: tuple[EntryGrade, ...]
    mean_ess: float
    min_ess: float
    n_reliable: int
    n_unreliable: int
    weakest_entry: str
    strongest_entry: str
    claim_strength: str  # "STRONG" / "MODERATE" / "WEAK" / "INSUFFICIENT"
    recommendations: tuple[str, ...]


def _score_pvalue(p: object) -> float:
    """Score p-value: 1.0 if p < 0.05, 0.5 if p < 0.10, 0.0 if missing/high."""
    if p is None:
        return 0.0
    try:
        pf = float(p)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(pf):
        return 0.0
    if pf < _P_THRESHOLD:
        return 1.0
    if pf < 0.10:
        return 0.5
    return 0.2  # present but not significant


def _score_r2(r2: object) -> float:
    """Score R²: 1.0 if > 0.7, 0.7 if > 0.5, 0.3 if > 0.2, 0 if missing."""
    if r2 is None:
        return 0.0
    try:
        rf = float(r2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(rf):
        return 0.0
    if rf > 0.7:
        return 1.0
    if rf > _R2_THRESHOLD:
        return 0.7
    if rf > 0.2:
        return 0.3
    return 0.1


def _score_n(n: object) -> float:
    """Score sample size: 1.0 if >= 20, 0.7 if >= 10, 0.3 if present, 0 if missing."""
    if n is None:
        return 0.0
    try:
        ni = int(str(n))
    except (TypeError, ValueError):
        return 0.0
    if ni >= 20:
        return 1.0
    if ni >= _N_THRESHOLD:
        return 0.7
    if ni > 0:
        return 0.3
    return 0.0


def _score_ci(ci_lo: object, ci_hi: object) -> float:
    """Score CI: 1.0 if present and contains 1.0, 0.5 if present but not, 0 if missing."""
    if ci_lo is None or ci_hi is None:
        return 0.0
    try:
        lo = float(ci_lo)  # type: ignore[arg-type]
        hi = float(ci_hi)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(lo) or math.isnan(hi):
        return 0.0
    if lo <= 1.0 <= hi:
        return 1.0
    return 0.5  # CI present but doesn't contain unity


def _score_hash(h: object) -> float:
    """Score provenance hash: 1.0 if present, 0 if missing."""
    if h is None or h == "":
        return 0.0
    return 1.0


def _grade_from_ess(ess: float) -> str:
    """Letter grade from ESS."""
    if ess >= 0.8:
        return "A"
    if ess >= 0.6:
        return "B"
    if ess >= 0.4:
        return "C"
    if ess >= 0.2:
        return "D"
    return "F"


def audit_ledger(
    ledger_path: str | Path | None = None,
) -> AuditReport:
    """Audit the gamma ledger for evidence quality.

    Args:
        ledger_path: path to gamma_ledger.json. Default: evidence/gamma_ledger.json.

    Returns:
        AuditReport with per-entry grades and overall assessment.
    """
    if ledger_path is None:
        ledger_path = Path(__file__).parent.parent / "evidence" / "gamma_ledger.json"
    else:
        ledger_path = Path(ledger_path)

    with open(ledger_path, encoding="utf-8") as f:
        raw = json.load(f)

    entries = raw.get("entries", raw)
    if not isinstance(entries, dict):
        raise ValueError("ledger must have 'entries' dict")

    grades: list[EntryGrade] = []
    validated_grades: list[EntryGrade] = []

    for eid, data in entries.items():
        if not isinstance(data, dict):
            continue
        gamma = data.get("gamma")
        if gamma is None:
            continue

        status = data.get("status", "UNKNOWN")

        # Score each axis
        q1 = _score_pvalue(data.get("p_permutation"))
        q2 = _score_r2(data.get("r2"))
        q3 = _score_n(data.get("n_pairs"))
        q4 = _score_ci(data.get("ci_low"), data.get("ci_high"))
        ds = data.get("data_source", {})
        q5 = _score_hash(ds.get("sha256") if isinstance(ds, dict) else None)
        q6 = _score_hash(data.get("adapter_code_hash"))

        ess = (q1 + q2 + q3 + q4 + q5 + q6) / 6.0
        grade = _grade_from_ess(ess)

        # Identify specific issues
        issues: list[str] = []
        if q1 == 0:
            issues.append("missing p-value")
        elif q1 < 1.0:
            issues.append(f"p={data.get('p_permutation')} (≥ 0.05)")
        if q2 == 0:
            issues.append("missing R²")
        elif q2 < 0.7:
            issues.append(f"R²={data.get('r2')} (weak fit)")
        if q3 == 0:
            issues.append("missing n_pairs")
        elif q3 < 0.7:
            issues.append(f"n={data.get('n_pairs')} (small sample)")
        if q4 == 0:
            issues.append("missing CI")
        elif q4 < 1.0:
            issues.append("CI does not contain 1.0")
        if q5 == 0:
            issues.append("missing data SHA-256")
        if q6 == 0:
            issues.append("missing adapter code hash")

        entry_grade = EntryGrade(
            entry_id=eid,
            gamma=float(gamma),
            status=status,
            q_significance=q1,
            q_effect_size=q2,
            q_sample_size=q3,
            q_confidence_interval=q4,
            q_data_provenance=q5,
            q_code_provenance=q6,
            ess=ess,
            grade=grade,
            issues=tuple(issues),
            is_reliable=ess >= 0.4,
        )
        grades.append(entry_grade)
        # Phase 2 hardening (ledger v2.0.0): pool VALIDATED + the
        # post-VALIDATED measurement tiers (EVIDENCE_CANDIDATE,
        # SUPPORTED_BY_NULLS, VALIDATED_SUBSTRATE_EVIDENCE) as the
        # "γ-emitting candidate" set. Sub-γ statuses are excluded.
        if status in {
            "VALIDATED",
            "VALIDATED_SUBSTRATE_EVIDENCE",
            "EVIDENCE_CANDIDATE",
            "SUPPORTED_BY_NULLS",
        }:
            validated_grades.append(entry_grade)

    # Aggregate
    weakest_id = ""
    strongest_id = ""
    if validated_grades:
        ess_values = [g.ess for g in validated_grades]
        mean_ess = sum(ess_values) / len(ess_values)
        min_ess = min(ess_values)
        weakest_id = min(validated_grades, key=lambda g: g.ess).entry_id
        strongest_id = max(validated_grades, key=lambda g: g.ess).entry_id
        n_reliable = sum(1 for g in validated_grades if g.is_reliable)
        n_unreliable = len(validated_grades) - n_reliable
    else:
        mean_ess = 0.0
        min_ess = 0.0
        n_reliable = 0
        n_unreliable = 0

    # Claim strength
    if n_reliable >= 6 and mean_ess >= 0.6:
        claim = "STRONG"
    elif n_reliable >= 4 and mean_ess >= 0.4:
        claim = "MODERATE"
    elif n_reliable >= 2:
        claim = "WEAK"
    else:
        claim = "INSUFFICIENT"

    # Generate recommendations
    recs: list[str] = []
    for g in validated_grades:
        if g.q_significance == 0:
            recs.append(f"{g.entry_id}: run permutation test → add p-value")
        if g.q_data_provenance == 0:
            recs.append(f"{g.entry_id}: compute SHA-256 of source data")
        if g.q_code_provenance == 0:
            recs.append(f"{g.entry_id}: hash adapter code → add adapter_code_hash")
        if g.q_effect_size < 0.3:
            recs.append(f"{g.entry_id}: R²={g.gamma:.3f} — review methodology")

    # Deduplicate recommendations
    seen: set[str] = set()
    unique_recs: list[str] = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique_recs.append(r)

    return AuditReport(
        total_entries=len(grades),
        validated_entries=len(validated_grades),
        grades=tuple(grades),
        mean_ess=mean_ess,
        min_ess=min_ess,
        n_reliable=n_reliable,
        n_unreliable=n_unreliable,
        weakest_entry=weakest_id,
        strongest_entry=strongest_id,
        claim_strength=claim,
        recommendations=tuple(unique_recs),
    )


def compute_data_hash(path: str | Path) -> str:
    """SHA-256 hash of a data file for provenance sealing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"data file not found: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compute_code_hash(path: str | Path) -> str:
    """SHA-256 hash of an adapter source file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"code file not found: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()
