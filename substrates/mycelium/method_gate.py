"""Method Gate 0 for `SUBSTRATE_006_MYCELIAL_ELECTROPHYSIOLOGY`.

This module enforces the fail-closed γ-definition audit recorded in
`docs/methods/mycelium_gamma_definition_audit.json` and the partner
prose document `docs/methods/MYCELIUM_GAMMA_DEFINITION_AUDIT.md`.

It is a pure-Python definition gate. It does **not**:

* analyze any fungal data;
* compute γ on any biological signal;
* implement DFA, spectral, avalanche, K(C), or null pipelines;
* read any biological dataset.

It only:

* loads the deterministic audit JSON;
* validates the schema and the cross-field invariants (NONE ↔ BLOCKED,
  DFA → `h_tension_if_dfa` recorded, ACCEPTED → non-empty primary
  formula);
* exposes two boolean predicates that downstream consumers (CI gates,
  pipeline runners, evidence-promotion scripts) MUST consult before
  running anything against fungal data.

Promotion semantics tied to `docs/CLAIM_BOUNDARY.md §5.1` and §6:

* `can_run_biological_pipeline` — `True` only when the audit JSON
  reports an accepted primary γ-definition AND the schema validator
  agrees. Always `False` for any `BLOCKED_BY_METHOD_DEFINITION` /
  `GAMMA_DEFINITION_REJECTED` status.
* `can_promote_to_evidence_admissible` — `True` only when the primary
  γ-definition is accepted, the primary metric formula is non-empty,
  and the DFA tension flag is explicit if DFA is the primary or
  among the rejected candidates. Secondary metrics never promote.

There are no mutable globals, no side effects, no IO besides reading
the audit JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Public canonical literals
# ---------------------------------------------------------------------------

STATUS_ACCEPTED: Final[str] = "GAMMA_DEFINITION_ACCEPTED"
STATUS_REJECTED: Final[str] = "GAMMA_DEFINITION_REJECTED"
STATUS_BLOCKED: Final[str] = "BLOCKED_BY_METHOD_DEFINITION"

VALID_STATUSES: Final[frozenset[str]] = frozenset(
    {STATUS_ACCEPTED, STATUS_REJECTED, STATUS_BLOCKED}
)

DEFINITION_NONE: Final[str] = "NONE"
DEFINITION_DFA: Final[str] = "DFA_2H_PLUS_1"
DEFINITION_SPECTRAL: Final[str] = "SPECTRAL_APERIODIC"
DEFINITION_AVALANCHE: Final[str] = "EVENT_AVALANCHE"
DEFINITION_KC: Final[str] = "SUBSTRATE_KC"

VALID_DEFINITIONS: Final[frozenset[str]] = frozenset(
    {
        DEFINITION_NONE,
        DEFINITION_DFA,
        DEFINITION_SPECTRAL,
        DEFINITION_AVALANCHE,
        DEFINITION_KC,
    }
)

REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "accepted_candidate_reason",
    "decision_reason",
    "forbidden_promotions",
    "gamma_target_interval",
    "h_tension_if_dfa",
    "method_risks",
    "non_claims",
    "primary_gamma_definition",
    "primary_metric_formula",
    "primary_metric_name",
    "rejected_candidates",
    "secondary_metrics",
    "status",
    "substrate_id",
)

REQUIRED_NON_CLAIMS: Final[tuple[str, ...]] = ("This audit does not analyze fungal data.",)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MethodGateResult:
    """Immutable record of the audit verdict.

    The dataclass is frozen so a downstream consumer cannot mutate a
    verdict to grant itself promotion.
    """

    substrate_id: str
    status: str
    primary_gamma_definition: str
    primary_metric_name: str
    primary_metric_formula: str
    gamma_target_interval: tuple[float, float] | None
    h_tension_if_dfa: bool | None
    accepted_candidate_reason: str
    rejected_candidates: tuple[dict[str, str], ...]
    secondary_metrics: tuple[str, ...]
    forbidden_promotions: tuple[str, ...]
    method_risks: tuple[str, ...]
    non_claims: tuple[str, ...]
    decision_reason: str


@dataclass(frozen=True, slots=True)
class MethodGateValidation:
    """Outcome of `validate_method_audit` — never raises, always tellable."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


# ---------------------------------------------------------------------------
# Helpers (private)
# ---------------------------------------------------------------------------


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"INVALID_AUDIT_JSON: missing required key: {key}")
    return data[key]


def _require_str(data: dict[str, Any], key: str) -> str:
    value = _require(data, key)
    if not isinstance(value, str):
        raise ValueError(
            f"INVALID_AUDIT_JSON: key {key!r} must be string, got {type(value).__name__}"
        )
    return value


def _require_str_tuple(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = _require(data, key)
    if not isinstance(value, list):
        raise ValueError(
            f"INVALID_AUDIT_JSON: key {key!r} must be list, got {type(value).__name__}"
        )
    out: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(
                f"INVALID_AUDIT_JSON: key {key!r}[{i}] must be string, got {type(item).__name__}"
            )
        out.append(item)
    return tuple(out)


def _coerce_interval(raw: Any) -> tuple[float, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("INVALID_AUDIT_JSON: gamma_target_interval must be null or [low, high]")
    low_raw, high_raw = raw
    if not isinstance(low_raw, (int, float)) or not isinstance(high_raw, (int, float)):
        raise ValueError("INVALID_AUDIT_JSON: gamma_target_interval values must be numeric")
    low = float(low_raw)
    high = float(high_raw)
    if low > high:
        raise ValueError("INVALID_AUDIT_JSON: gamma_target_interval low > high")
    return (low, high)


def _coerce_h_tension(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    raise ValueError("INVALID_AUDIT_JSON: h_tension_if_dfa must be bool or null")


def _coerce_rejected(raw: Any) -> tuple[dict[str, str], ...]:
    if not isinstance(raw, list):
        raise ValueError("INVALID_AUDIT_JSON: rejected_candidates must be a list")
    out: list[dict[str, str]] = []
    seen_candidates: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"INVALID_AUDIT_JSON: rejected_candidates[{i}] must be object")
        if "candidate" not in item or "reason" not in item:
            raise ValueError(
                f"INVALID_AUDIT_JSON: rejected_candidates[{i}] missing 'candidate' or 'reason'"
            )
        candidate_value = item["candidate"]
        reason_value = item["reason"]
        if not isinstance(candidate_value, str) or not isinstance(reason_value, str):
            raise ValueError(f"INVALID_AUDIT_JSON: rejected_candidates[{i}] fields must be strings")
        if candidate_value in seen_candidates:
            raise ValueError(
                f"INVALID_AUDIT_JSON: rejected_candidates duplicate entry {candidate_value!r}"
            )
        seen_candidates.add(candidate_value)
        out.append({"candidate": candidate_value, "reason": reason_value})
    return tuple(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_method_audit(path: Path) -> MethodGateResult:
    """Load and structurally validate the audit JSON at *path*.

    Raises:
        FileNotFoundError: when *path* does not exist.
        ValueError: prefixed with ``INVALID_AUDIT_JSON:`` on schema, type,
            duplicate-candidate, multiple-primary, or empty-decision-reason
            violations.
    """

    if not path.exists():
        raise FileNotFoundError(str(path))

    raw_text = path.read_text(encoding="utf-8")
    try:
        data: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"INVALID_AUDIT_JSON: malformed JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("INVALID_AUDIT_JSON: top-level must be object")

    for key in REQUIRED_KEYS:
        if key not in data:
            raise ValueError(f"INVALID_AUDIT_JSON: missing required key: {key}")

    substrate_id = _require_str(data, "substrate_id")
    status = _require_str(data, "status")
    if status not in VALID_STATUSES:
        raise ValueError(f"INVALID_AUDIT_JSON: status {status!r} not in {sorted(VALID_STATUSES)}")

    primary = _require_str(data, "primary_gamma_definition")
    if primary not in VALID_DEFINITIONS:
        raise ValueError(
            f"INVALID_AUDIT_JSON: primary_gamma_definition {primary!r} not in "
            f"{sorted(VALID_DEFINITIONS)}"
        )

    primary_name = _require_str(data, "primary_metric_name")
    primary_formula = _require_str(data, "primary_metric_formula")
    decision_reason = _require_str(data, "decision_reason")
    if not decision_reason.strip():
        raise ValueError("INVALID_AUDIT_JSON: decision_reason must be non-empty")

    accepted_reason = _require_str(data, "accepted_candidate_reason")

    interval = _coerce_interval(data["gamma_target_interval"])
    h_tension = _coerce_h_tension(data["h_tension_if_dfa"])

    rejected = _coerce_rejected(data["rejected_candidates"])
    rejected_candidate_names = {entry["candidate"] for entry in rejected}
    if primary != DEFINITION_NONE and primary in rejected_candidate_names:
        raise ValueError(
            "INVALID_AUDIT_JSON: primary_gamma_definition cannot also appear in rejected_candidates"
        )

    secondary = _require_str_tuple(data, "secondary_metrics")
    forbidden = _require_str_tuple(data, "forbidden_promotions")
    risks = _require_str_tuple(data, "method_risks")
    non_claims = _require_str_tuple(data, "non_claims")

    return MethodGateResult(
        substrate_id=substrate_id,
        status=status,
        primary_gamma_definition=primary,
        primary_metric_name=primary_name,
        primary_metric_formula=primary_formula,
        gamma_target_interval=interval,
        h_tension_if_dfa=h_tension,
        accepted_candidate_reason=accepted_reason,
        rejected_candidates=rejected,
        secondary_metrics=secondary,
        forbidden_promotions=forbidden,
        method_risks=risks,
        non_claims=non_claims,
        decision_reason=decision_reason,
    )


def validate_method_audit(result: MethodGateResult) -> MethodGateValidation:
    """Cross-field validation that does not raise.

    Enforces:

    * NONE ↔ BLOCKED coupling.
    * `GAMMA_DEFINITION_ACCEPTED` requires non-empty `primary_metric_formula`
      AND non-empty `primary_metric_name`.
    * If DFA is primary OR among rejected candidates, `h_tension_if_dfa`
      must be explicitly recorded (not `None`).
    * Required non-claims must be present (`This audit does not analyze
      fungal data.`).
    * Warns when any secondary-metric description hints at promotion
      (the words "primary" or "promote" appearing inside a secondary
      metric is a smell — recorded as a warning, not an error, so the
      audit author can revise).
    """

    errors: list[str] = []
    warnings: list[str] = []

    # NONE ↔ BLOCKED coupling
    if result.primary_gamma_definition == DEFINITION_NONE and result.status != STATUS_BLOCKED:
        errors.append(
            f"primary_gamma_definition=NONE requires status=BLOCKED_BY_METHOD_DEFINITION; "
            f"got status={result.status!r}"
        )
    if result.status == STATUS_BLOCKED and result.primary_gamma_definition != DEFINITION_NONE:
        errors.append(
            f"status=BLOCKED_BY_METHOD_DEFINITION requires primary_gamma_definition=NONE; "
            f"got primary_gamma_definition={result.primary_gamma_definition!r}"
        )

    # ACCEPTED requires populated primary metric
    if result.status == STATUS_ACCEPTED:
        if not result.primary_metric_formula.strip():
            errors.append(
                "status=GAMMA_DEFINITION_ACCEPTED requires non-empty primary_metric_formula"
            )
        if not result.primary_metric_name.strip():
            errors.append("status=GAMMA_DEFINITION_ACCEPTED requires non-empty primary_metric_name")
        if result.primary_gamma_definition == DEFINITION_NONE:
            errors.append(
                "status=GAMMA_DEFINITION_ACCEPTED is incompatible with "
                "primary_gamma_definition=NONE"
            )

    # DFA tension recorded if DFA appears anywhere
    rejected_names = {entry["candidate"] for entry in result.rejected_candidates}
    dfa_referenced = (
        result.primary_gamma_definition == DEFINITION_DFA or DEFINITION_DFA in rejected_names
    )
    if dfa_referenced and result.h_tension_if_dfa is None:
        errors.append(
            "DFA candidate referenced (primary or rejected) requires h_tension_if_dfa "
            "to be explicit (true|false), got None"
        )

    # Required non-claims present
    for required_phrase in REQUIRED_NON_CLAIMS:
        if not any(required_phrase == nc for nc in result.non_claims):
            errors.append(f"missing required non-claim: {required_phrase!r}")

    # Secondary-metric promotion smell (warning only)
    for i, metric in enumerate(result.secondary_metrics):
        lowered = metric.lower()
        if "promote" in lowered:
            warnings.append(
                f"secondary_metrics[{i}] mentions 'promote' — secondary metrics never promote"
            )
        # Hint at "primary" usage that is NOT a back-reference to the canon name
        # of the primary aperiodic estimate. Recognise the canonical IRASA
        # cross-check phrasing as a non-smell.
        if "primary" in lowered and "cross-check" not in lowered and "mandatory" not in lowered:
            warnings.append(
                f"secondary_metrics[{i}] uses the word 'primary' outside a cross-check "
                f"context — verify it does not imply promotion"
            )

    return MethodGateValidation(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def can_run_biological_pipeline(result: MethodGateResult) -> bool:
    """Return whether a biological-data pipeline may run for this substrate.

    `False` when:
      * status is BLOCKED or REJECTED;
      * primary_gamma_definition is NONE;
      * the cross-field validator reports any error.

    Otherwise `True`.
    """

    if result.status != STATUS_ACCEPTED:
        return False
    if result.primary_gamma_definition == DEFINITION_NONE:
        return False
    return validate_method_audit(result).valid


def can_promote_to_evidence_admissible(result: MethodGateResult) -> bool:
    """Return whether the substrate may enter the evidential lane.

    Stricter than `can_run_biological_pipeline`: in addition to the
    pipeline gate, requires `primary_metric_formula` non-empty and the
    DFA tension flag explicit when DFA is referenced. Secondary metrics
    never grant promotion; this function is the structural choke point.
    """

    if result.status != STATUS_ACCEPTED:
        return False
    if result.primary_gamma_definition == DEFINITION_NONE:
        return False
    if not result.primary_metric_formula.strip():
        return False
    if not result.primary_metric_name.strip():
        return False
    rejected_names = {entry["candidate"] for entry in result.rejected_candidates}
    dfa_referenced = (
        result.primary_gamma_definition == DEFINITION_DFA or DEFINITION_DFA in rejected_names
    )
    if dfa_referenced and result.h_tension_if_dfa is None:
        return False
    return validate_method_audit(result).valid
