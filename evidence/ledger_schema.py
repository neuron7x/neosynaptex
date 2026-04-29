"""Gamma ledger schema (v2.0.0) — typed, fail-closed validator.

Phase 2 of the NeoSynaptex research-engineering protocol. This module
defines the **machine-checkable schema** for ``evidence/gamma_ledger.json``
entries and a fail-closed validator that the reconciliation tool and
tests use to enforce the schema. Phase 1 (`#158`) detected
contradictions; Phase 2 makes the schema itself enforceable so future
contradictions are blocked at write-time, not detected after the fact.

Canonical claim ladder (per
``docs/architecture/recursive_claim_refinement.md`` §2 plus the four
extended states authorised in the Phase 2 protocol):

    NO_ADMISSIBLE_CLAIM
    ARTIFACT_SUSPECTED
    LOCAL_STRUCTURAL_EVIDENCE_ONLY
    EVIDENCE_CANDIDATE
    SUPPORTED_BY_NULLS
    VALIDATED_SUBSTRATE_EVIDENCE
    FALSIFIED
    BLOCKED_BY_METHOD_DEFINITION
    INCONCLUSIVE

Reason codes (e.g. ``KAPPA_NOT_GAMMA``, ``NO_REAL_DATA_HASH``,
``NO_EXTERNAL_REPLICATION``) populate ``downgrade_reason`` and are NOT
ladder states.

The schema is intentionally minimal: no Pydantic, no third-party
dependency. Validation happens through a frozen dataclass plus a
post-init runtime check that rejects any combination the canon forbids.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

__all__ = [
    "CANONICAL_LADDER",
    "ALLOWED_DOWNGRADE_REASONS",
    "ALLOWED_EVIDENCE_TIERS",
    "LedgerEntry",
    "LedgerSchemaError",
    "validate_entry",
    "validate_ledger",
]


CANONICAL_LADDER: Final[frozenset[str]] = frozenset(
    {
        "NO_ADMISSIBLE_CLAIM",
        "ARTIFACT_SUSPECTED",
        "LOCAL_STRUCTURAL_EVIDENCE_ONLY",
        "EVIDENCE_CANDIDATE",
        "SUPPORTED_BY_NULLS",
        "VALIDATED_SUBSTRATE_EVIDENCE",
        "FALSIFIED",
        "BLOCKED_BY_METHOD_DEFINITION",
        "INCONCLUSIVE",
        # Legacy umbrella status used by the v1.0.0 ledger; Phase 2
        # downgrades retire it everywhere except where explicit hardened
        # evidence supports it (none today; declared empty by §5.1).
        "VALIDATED",
    }
)


#: Reason codes that travel with non-VALIDATED entries.
#: Keep this set tight — every new code is an explicit canon extension.
ALLOWED_DOWNGRADE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "KAPPA_NOT_GAMMA",
        "NO_REAL_DATA_HASH",
        "NO_REAL_ADAPTER_HASH",
        "NO_EXTERNAL_REPLICATION",
        "NO_EXTERNAL_RERUN",
        "NO_NULL_FAMILY_VERDICT",
        "SCRIPT_DRIFT",
        "MEASUREMENT_NOT_CANONICAL",
        "EVIDENCE_BUNDLE_INCOMPLETE",
        "PHASE_2_HARDENING",
    }
)

#: Evidence tiers describe what kind of evidence backs an entry.
ALLOWED_EVIDENCE_TIERS: Final[frozenset[str]] = frozenset(
    {
        "ANALYTICAL",  # closed-form proof, e.g. Lemma 1
        "NUMERICAL_INTERNAL",  # deterministic numerical script
        "MEASURED_NO_HASH",  # measurement exists but no real data hash
        "MEASURED_WITH_HASH",  # measurement + real sha256 + adapter hash
        "LOCAL_STRUCTURAL",  # BN-Syn-class local proxy
        "FALSIFIED",
        "GATE_BLOCKED",  # Gate 0 BLOCKED_BY_METHOD_DEFINITION
    }
)

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class LedgerSchemaError(ValueError):
    """Raised when a ledger entry violates the schema."""


def _is_real_hash(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One frozen, post-init-validated ledger row.

    The dataclass is **frozen** and **slot-only** so callers cannot mutate
    the row after construction or attach extra fields. ``__post_init__``
    enforces the schema invariants and raises
    :class:`LedgerSchemaError` on any violation.
    """

    substrate: str
    status: str
    data_sha256: str | None
    adapter_code_hash: str | None
    null_family_status: str | None
    rerun_command: str | None
    claim_boundary_ref: str | None
    evidence_tier: str | None
    downgrade_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        errors = list(_collect_entry_errors(self))
        if errors:
            raise LedgerSchemaError(f"LedgerEntry({self.substrate!r}) schema violations: {errors}")


def _collect_entry_errors(e: LedgerEntry) -> list[str]:
    """Return a list of human-readable schema violations for ``e``."""
    errs: list[str] = []
    if e.status not in CANONICAL_LADDER:
        errs.append(f"status={e.status!r} not in canonical ladder")
    if e.evidence_tier is not None and e.evidence_tier not in ALLOWED_EVIDENCE_TIERS:
        errs.append(f"evidence_tier={e.evidence_tier!r} not in ALLOWED_EVIDENCE_TIERS")
    if e.downgrade_reason is not None and e.downgrade_reason not in ALLOWED_DOWNGRADE_REASONS:
        errs.append(f"downgrade_reason={e.downgrade_reason!r} not in ALLOWED_DOWNGRADE_REASONS")
    if e.status in {"VALIDATED", "VALIDATED_SUBSTRATE_EVIDENCE"}:
        if not _is_real_hash(e.data_sha256):
            errs.append("VALIDATED requires a real data_sha256 (64-hex)")
        if not _is_real_hash(e.adapter_code_hash):
            errs.append("VALIDATED requires a real adapter_code_hash (64-hex)")
        if not e.null_family_status:
            errs.append("VALIDATED requires null_family_status")
        if not e.rerun_command:
            errs.append("VALIDATED requires rerun_command")
        if not e.claim_boundary_ref:
            errs.append("VALIDATED requires claim_boundary_ref")
        if e.downgrade_reason is not None:
            errs.append("VALIDATED entries must not carry a downgrade_reason")
    else:
        if e.downgrade_reason is None and e.status not in {"NO_ADMISSIBLE_CLAIM"}:
            errs.append(f"non-VALIDATED status={e.status!r} requires an explicit downgrade_reason")
    return errs


def validate_entry(substrate_id: str, raw: dict[str, Any]) -> LedgerEntry:
    """Construct a :class:`LedgerEntry` from a raw ledger dict.

    Raises :class:`LedgerSchemaError` if the entry violates the schema.
    """
    return LedgerEntry(
        substrate=str(raw.get("substrate", substrate_id)),
        status=str(raw.get("status", "")),
        data_sha256=raw.get("data_sha256"),
        adapter_code_hash=raw.get("adapter_code_hash"),
        null_family_status=raw.get("null_family_status"),
        rerun_command=raw.get("rerun_command"),
        claim_boundary_ref=raw.get("claim_boundary_ref"),
        evidence_tier=raw.get("evidence_tier"),
        downgrade_reason=raw.get("downgrade_reason"),
        raw=dict(raw),
    )


def validate_ledger(ledger: dict[str, Any]) -> dict[str, list[str]]:
    """Validate every entry in a parsed ledger dict.

    Returns a dict mapping ``substrate_id`` to a list of schema-violation
    strings. An empty dict means the ledger is schema-clean.
    """
    out: dict[str, list[str]] = {}
    if str(ledger.get("version", "")).split(".")[0] not in {"1", "2"}:
        out["__root__"] = [f"unknown ledger version {ledger.get('version')!r}"]
        return out
    entries = ledger.get("entries") or {}
    for sid, raw in entries.items():
        if not isinstance(raw, dict):
            out[sid] = [f"entry is not a dict: {type(raw).__name__}"]
            continue
        try:
            validate_entry(sid, raw)
        except LedgerSchemaError as exc:
            out[sid] = list(_collect_entry_errors(_unsafe_construct(sid, raw)))
            if not out[sid]:
                out[sid] = [str(exc)]
    return out


def _unsafe_construct(sid: str, raw: dict[str, Any]) -> LedgerEntry:
    """Construct a LedgerEntry bypassing __post_init__ for error reporting."""
    obj = object.__new__(LedgerEntry)
    object.__setattr__(obj, "substrate", str(raw.get("substrate", sid)))
    object.__setattr__(obj, "status", str(raw.get("status", "")))
    object.__setattr__(obj, "data_sha256", raw.get("data_sha256"))
    object.__setattr__(obj, "adapter_code_hash", raw.get("adapter_code_hash"))
    object.__setattr__(obj, "null_family_status", raw.get("null_family_status"))
    object.__setattr__(obj, "rerun_command", raw.get("rerun_command"))
    object.__setattr__(obj, "claim_boundary_ref", raw.get("claim_boundary_ref"))
    object.__setattr__(obj, "evidence_tier", raw.get("evidence_tier"))
    object.__setattr__(obj, "downgrade_reason", raw.get("downgrade_reason"))
    object.__setattr__(obj, "raw", dict(raw))
    return obj
