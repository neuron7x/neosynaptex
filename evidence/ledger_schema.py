"""Gamma ledger schema (v2.1.0) — typed, fail-closed validator.

Phase 2.1 hardening (closes audit-B1/B2/B3/B4 + Stanford/MIT review
P4/P6/P7) of the NeoSynaptex research-engineering protocol. This
module defines the **machine-checkable schema** for
``evidence/gamma_ledger.json`` entries and a fail-closed validator that
the reconciliation tool, the binding gate, and the runtime registry use
to enforce the schema.

Canonical claim ladder (per
``docs/architecture/recursive_claim_refinement.md`` §2 plus the
extended states authorised in the Phase 2 / 2.1 protocol):

    NO_ADMISSIBLE_CLAIM
    ARTIFACT_SUSPECTED
    LOCAL_STRUCTURAL_EVIDENCE_ONLY
    EVIDENCE_CANDIDATE
    EVIDENCE_CANDIDATE_NULL_FAILED   (Phase 2.1 — null cannot be rejected)
    SUPPORTED_BY_NULLS
    VALIDATED_SUBSTRATE_EVIDENCE     (FROZEN — see CANON_VALIDATED_FROZEN)
    FALSIFIED
    BLOCKED_BY_METHOD_DEFINITION
    INCONCLUSIVE
    VALIDATED                        (FROZEN — see CANON_VALIDATED_FROZEN)

P6 freeze
---------

``VALIDATED`` and ``VALIDATED_SUBSTRATE_EVIDENCE`` are **rejected
globally** until the canon defines machine-checkable promotion gates
(raw-data Merkle root, pipeline_hash, result_hash, null p < α,
external rerun, preregistration). Field-presence is no longer a
sufficient promotion criterion. The freeze flag
``CANON_VALIDATED_FROZEN`` is module-level and intentionally not
overridable from configuration: lifting it requires a deliberate code
change reviewed under the same protocol that retired field-only
promotion.

Reason codes (e.g. ``KAPPA_NOT_GAMMA``, ``NO_REAL_DATA_HASH``,
``NULL_NOT_REJECTED``) populate ``downgrade_reason`` and are NOT
ladder states.

The schema is intentionally minimal: no Pydantic, no third-party
dependency. Validation happens through pure functions that operate on
raw dicts; the frozen ``LedgerEntry`` dataclass exists only as a
typed read-only handle for callers who already passed validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

__all__ = [
    "ALLOWED_DATA_SHA256_KINDS",
    "ALLOWED_DOWNGRADE_REASONS",
    "ALLOWED_EVIDENCE_TIERS",
    "CANONICAL_LADDER",
    "CANON_VALIDATED_FROZEN",
    "FROZEN_LADDER_STATES",
    "LedgerEntry",
    "LedgerSchemaError",
    "NON_RAW_DATA_KINDS",
    "is_null_screen_failed",
    "validate_entry",
    "validate_ledger",
]


CANONICAL_LADDER: Final[frozenset[str]] = frozenset(
    {
        "NO_ADMISSIBLE_CLAIM",
        "ARTIFACT_SUSPECTED",
        "LOCAL_STRUCTURAL_EVIDENCE_ONLY",
        "EVIDENCE_CANDIDATE",
        # Phase 2.1: explicit verdict-state for substrates whose null
        # screen failed to reject the null hypothesis. Distinct from
        # plain EVIDENCE_CANDIDATE because the cohort cannot yet support
        # any positive metastability claim (P7).
        "EVIDENCE_CANDIDATE_NULL_FAILED",
        "SUPPORTED_BY_NULLS",
        "VALIDATED_SUBSTRATE_EVIDENCE",
        "FALSIFIED",
        "BLOCKED_BY_METHOD_DEFINITION",
        "INCONCLUSIVE",
        # Legacy umbrella status. Frozen by P6 — see CANON_VALIDATED_FROZEN.
        "VALIDATED",
    }
)


#: Ladder states that are admitted to the canon but rejected for new
#: entries until the Phase 2.1 P6 promotion gates exist
#: (raw-data Merkle root, pipeline_hash, result_hash, null p < α,
#: external rerun, preregistration).
FROZEN_LADDER_STATES: Final[frozenset[str]] = frozenset(
    {
        "VALIDATED",
        "VALIDATED_SUBSTRATE_EVIDENCE",
    }
)


#: Master switch for the P6 freeze. Lifting requires a deliberate code
#: change, NOT a config flag — environment overrides have been removed.
CANON_VALIDATED_FROZEN: Final[bool] = True


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
        "NULL_NOT_REJECTED",  # Phase 2.1 P7 — surrogate cannot be distinguished
        "SCRIPT_DRIFT",
        "MEASUREMENT_NOT_CANONICAL",
        "EVIDENCE_BUNDLE_INCOMPLETE",
        "PHASE_2_HARDENING",
        "PHASE_2_1_HARDENING",
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

#: Phrases inside ``null_family_status`` that mark a failed null screen
#: (P7). Matching is case-insensitive substring; one hit is enough.
_NULL_FAILED_PHRASES: Final[tuple[str, ...]] = (
    "null cannot be rejected",
    "surrogate did not distinguish",
    "surrogate did NOT distinguish",
)

#: Regex: extract ``p_permutation=<float>`` from null_family_status.
_P_PERMUTATION_RE: Final[re.Pattern[str]] = re.compile(r"p_permutation\s*=\s*([0-9.]+)")

#: Significance threshold for null rejection (P7).
_ALPHA: Final[float] = 0.05


#: P8 honest-downgrade enum for the ``data_sha256_kind`` field. The
#: kind makes explicit *what* the stored hash binds to, so a "bundle
#: manifest" (a file describing dataset SHA-256s) cannot silently be
#: confused with raw data hashing. Until raw-file Merkle is computed
#: in-tree, ``raw_dataset_merkle_root`` is the only kind allowed to
#: claim direct raw-data binding.
ALLOWED_DATA_SHA256_KINDS: Final[frozenset[str]] = frozenset(
    {
        "raw_dataset_merkle_root",  # Phase 3+: per-file SHA → Merkle root
        "bundle_manifest",  # SHA-256 of evidence/data_hashes.json
        "bundle_manifest:evidence/data_hashes.json",  # legacy explicit form
        "adapter_source",  # SHA-256 of substrate adapter source
        "script_source",  # SHA-256 of an analysis/verification script
        "script_sha256_at_generation_time",  # legacy form for lemma_1
    }
)


#: Kinds that are NOT direct raw-data bindings. A schema claim of
#: VALIDATED with raw-data evidence may not be backed by these kinds.
NON_RAW_DATA_KINDS: Final[frozenset[str]] = frozenset(
    {
        "bundle_manifest",
        "bundle_manifest:evidence/data_hashes.json",
        "adapter_source",
        "script_source",
        "script_sha256_at_generation_time",
    }
)


class LedgerSchemaError(ValueError):
    """Raised when a ledger entry violates the schema."""


def _is_real_hash(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


def is_null_screen_failed(null_family_status: object) -> bool:
    """Return True if the entry's null_family_status documents a failed
    null screen (P7).

    Triggers on:
      * ``p_permutation = X`` substring with X >= 0.05
      * any of the canonical "null cannot be rejected" phrases.
    Returns False when the status is null/empty/analytical.
    """
    if not isinstance(null_family_status, str) or not null_family_status:
        return False
    s = null_family_status.lower()
    if any(phrase.lower() in s for phrase in _NULL_FAILED_PHRASES):
        return True
    m = _P_PERMUTATION_RE.search(null_family_status)
    if m is not None:
        try:
            p = float(m.group(1))
        except ValueError:
            return False
        return p >= _ALPHA
    return False


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One frozen, validated ledger row.

    Construction is the **only** sanctioned admission path; the
    ``__post_init__`` runs the canonical schema check. The dataclass is
    frozen + slot-only so casual mutation is blocked. ``__reduce__`` is
    overridden to route every unpickle through ``validate_entry`` so
    pickle round-trip cannot bypass the schema.
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
        errors = list(_collect_entry_errors(self.substrate, dict(self.raw)))
        if errors:
            raise LedgerSchemaError(f"LedgerEntry({self.substrate!r}) schema violations: {errors}")

    def __reduce__(self) -> tuple[Any, ...]:
        # Phase 2.1 anti-pickle: route unpickle through validate_entry
        # so __post_init__ schema check fires on the deserialised side.
        return (validate_entry, (self.substrate, dict(self.raw)))


def _collect_entry_errors(substrate_id: str, raw: dict[str, Any]) -> list[str]:
    """Return a list of human-readable schema violations for a raw entry.

    Pure function: operates on the raw dict (P4 — no forged
    ``LedgerEntry`` objects required for error reporting).
    """
    errs: list[str] = []
    status = str(raw.get("status", "") or "")
    if status not in CANONICAL_LADDER:
        errs.append(f"status={status!r} not in canonical ladder")

    evidence_tier = raw.get("evidence_tier")
    if evidence_tier is not None and evidence_tier not in ALLOWED_EVIDENCE_TIERS:
        errs.append(f"evidence_tier={evidence_tier!r} not in ALLOWED_EVIDENCE_TIERS")

    downgrade_reason = raw.get("downgrade_reason")
    if downgrade_reason is not None and downgrade_reason not in ALLOWED_DOWNGRADE_REASONS:
        errs.append(f"downgrade_reason={downgrade_reason!r} not in ALLOWED_DOWNGRADE_REASONS")

    # P6 — VALIDATED freeze: reject globally regardless of fields.
    if status in FROZEN_LADDER_STATES:
        if CANON_VALIDATED_FROZEN:
            errs.append(
                f"status={status!r} is FROZEN by Phase 2.1 P6 — promotion to "
                "VALIDATED requires raw-data Merkle root, pipeline_hash, "
                "result_hash, null p<α, external rerun, and preregistration "
                "fields that are not yet machine-checkable. Lifting the "
                "freeze requires editing CANON_VALIDATED_FROZEN."
            )
        else:  # pragma: no cover — preserved for the day the freeze lifts
            if not _is_real_hash(raw.get("data_sha256")):
                errs.append("VALIDATED requires a real data_sha256 (64-hex)")
            if not _is_real_hash(raw.get("adapter_code_hash")):
                errs.append("VALIDATED requires a real adapter_code_hash (64-hex)")
            if not raw.get("null_family_status"):
                errs.append("VALIDATED requires null_family_status")
            if not raw.get("rerun_command"):
                errs.append("VALIDATED requires rerun_command")
            if not raw.get("claim_boundary_ref"):
                errs.append("VALIDATED requires claim_boundary_ref")
            if downgrade_reason is not None:
                errs.append("VALIDATED entries must not carry a downgrade_reason")
    else:
        if downgrade_reason is None and status not in {"NO_ADMISSIBLE_CLAIM"}:
            errs.append(f"non-VALIDATED status={status!r} requires an explicit downgrade_reason")

    # P7 — entries whose null screen has failed must not sit at
    # EVIDENCE_CANDIDATE (which implies positive metastability is plausible).
    # Allowed states for null-failed entries:
    #   EVIDENCE_CANDIDATE_NULL_FAILED, INCONCLUSIVE, ARTIFACT_SUSPECTED,
    #   LOCAL_STRUCTURAL_EVIDENCE_ONLY, NO_ADMISSIBLE_CLAIM, FALSIFIED,
    #   BLOCKED_BY_METHOD_DEFINITION.
    null_status = raw.get("null_family_status")
    if is_null_screen_failed(null_status):
        permitted = {
            "EVIDENCE_CANDIDATE_NULL_FAILED",
            "INCONCLUSIVE",
            "ARTIFACT_SUSPECTED",
            "LOCAL_STRUCTURAL_EVIDENCE_ONLY",
            "NO_ADMISSIBLE_CLAIM",
            "FALSIFIED",
            "BLOCKED_BY_METHOD_DEFINITION",
        }
        if status not in permitted:
            errs.append(
                f"null_family_status documents a failed null screen "
                f"(p_permutation>={_ALPHA} or 'null cannot be rejected'); "
                f"status={status!r} is not permitted. Allowed: "
                f"{sorted(permitted)}"
            )
        # P7 deeper (Phase 2.1 v2): a null-failed entry must not carry a
        # positive metastability VERDICT. Permitted verdicts mirror the
        # ladder downgrade: NULL_NOT_REJECTED, INCONCLUSIVE, or null.
        # METASTABLE / METASTABLE_* / CONSISTENT_* / WARNING are forbidden
        # because they semantically project a positive γ ≈ 1 claim that
        # the failed null screen cannot support.
        verdict = raw.get("verdict")
        if verdict is not None:
            verdict_str = str(verdict).upper()
            forbidden_when_null_failed = {
                "METASTABLE",
                "METASTABLE_SUPPORT",
                "METASTABLE_CANDIDATE",
                "CONSISTENT_WITH_GAMMA_EQUALS_ONE",
                "WARNING",
                "POSITIVE",
            }
            if verdict_str in forbidden_when_null_failed:
                errs.append(
                    f"null_family_status documents a failed null screen but "
                    f"verdict={verdict!r} is a positive-metastability label. "
                    f"Allowed verdicts for null-failed entries: NULL_NOT_REJECTED, "
                    f"INCONCLUSIVE, or null. Forbidden: "
                    f"{sorted(forbidden_when_null_failed)}"
                )

    # P2 — hash_binding type discipline (echoed here so non-binding
    # consumers still surface the violation when reading via
    # ``validate_ledger``). The full path-traversal + recompute lives in
    # ``tools.audit.ledger_evidence_binding``.
    hb = raw.get("hash_binding")
    if hb is not None and not isinstance(hb, dict):
        errs.append(f"hash_binding={hb!r} (type {type(hb).__name__}) — must be dict or omitted")

    # P8 — data_sha256_kind enum check + raw-data honesty.
    # When data_sha256 is non-null, the entry MUST declare what kind of
    # binding the hash represents (P8 Option B / honest downgrade).
    # Manifest / adapter / script kinds are NEVER raw-data bindings; the
    # canon must not silently let a manifest hash satisfy a raw-data
    # gate. The VALIDATED ladder freeze (P6) covers the latter today;
    # this check makes the kind machine-checkable for future un-freezes.
    kind = raw.get("data_sha256_kind")
    data_sha = raw.get("data_sha256")
    if kind is not None and kind not in ALLOWED_DATA_SHA256_KINDS:
        errs.append(
            f"data_sha256_kind={kind!r} not in ALLOWED_DATA_SHA256_KINDS "
            f"({sorted(ALLOWED_DATA_SHA256_KINDS)})"
        )
    if data_sha is not None and kind is None:
        errs.append(
            "data_sha256 is non-null but data_sha256_kind is missing — "
            "explicit kind is required so 'bundle_manifest' cannot silently "
            "stand in for raw-data binding"
        )

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
        errs = _collect_entry_errors(sid, raw)
        if errs:
            out[sid] = errs
    return out
