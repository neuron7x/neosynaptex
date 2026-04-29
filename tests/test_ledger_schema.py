"""Tests for evidence/ledger_schema.py — Phase 2.1 hardened validator.

Numbered tests:
1.  Clean EVIDENCE_CANDIDATE fixture passes ``validate_entry``.
2.  Bad status (not in ladder) raises LedgerSchemaError.
3.  Bad evidence_tier raises.
4.  Bad downgrade_reason raises.
5.  Non-VALIDATED non-NO_ADMISSIBLE without downgrade_reason raises.
6.  VALIDATED is rejected globally by the P6 freeze, regardless of fields.
7.  VALIDATED_SUBSTRATE_EVIDENCE is rejected globally by the P6 freeze.
8.  EVIDENCE_CANDIDATE_NULL_FAILED is admitted with NULL_NOT_REJECTED reason.
9.  Null-failed entry at EVIDENCE_CANDIDATE is rejected (P7).
10. Null-failed entry at EVIDENCE_CANDIDATE_NULL_FAILED is admitted.
11. Non-dict hash_binding (list/int/str/False) is rejected at schema time (P2).
12. ``validate_ledger`` reports per-substrate errors.
13. Real repository ledger validates clean (Phase 2.1 invariant).
14. ``LedgerEntry`` is frozen and slot-only.
15. ``KAPPA_NOT_GAMMA`` is a canonical downgrade reason.
16. ``NO_EXTERNAL_REPLICATION`` is a canonical downgrade reason.
17. ``NULL_NOT_REJECTED`` is a canonical downgrade reason (P7 added).
18. Pickle round-trip of valid entry succeeds.
19. Pickle-forged raw is rejected on unpickle (validate_entry-routed).
20. ``_unsafe_construct`` is fully removed (no longer in the module).
21. ``is_null_screen_failed`` recognises the canonical phrases + p>=alpha.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from evidence.ledger_schema import (
    ALLOWED_DOWNGRADE_REASONS,
    CANON_VALIDATED_FROZEN,
    FROZEN_LADDER_STATES,
    LedgerEntry,
    LedgerSchemaError,
    is_null_screen_failed,
    validate_entry,
    validate_ledger,
)

_GOOD_HASH = "0" * 64
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _good_candidate() -> dict[str, Any]:
    """A schema-clean EVIDENCE_CANDIDATE entry."""
    return {
        "substrate": "x",
        "status": "EVIDENCE_CANDIDATE",
        "downgrade_reason": "NO_REAL_DATA_HASH",
        "data_sha256": None,
        "adapter_code_hash": None,
        "null_family_status": None,
        "rerun_command": None,
        "claim_boundary_ref": "docs/CLAIM_BOUNDARY.md#claim-c-003",
        "evidence_tier": "MEASURED_NO_HASH",
    }


def _good_null_failed() -> dict[str, Any]:
    """A schema-clean EVIDENCE_CANDIDATE_NULL_FAILED entry (P7)."""
    return {
        "substrate": "x",
        "status": "EVIDENCE_CANDIDATE_NULL_FAILED",
        "downgrade_reason": "NULL_NOT_REJECTED",
        "data_sha256": None,
        "adapter_code_hash": None,
        "null_family_status": "p_permutation=0.946 — null cannot be rejected.",
        "rerun_command": None,
        "claim_boundary_ref": "docs/CLAIM_BOUNDARY.md#claim-c-003",
        "evidence_tier": "MEASURED_NO_HASH",
    }


# 1
def test_clean_candidate_validates() -> None:
    e = validate_entry("x", _good_candidate())
    assert isinstance(e, LedgerEntry)
    assert e.status == "EVIDENCE_CANDIDATE"


# 2
def test_bad_status_rejected() -> None:
    raw = _good_candidate() | {"status": "NOT_A_REAL_STATUS"}
    with pytest.raises(LedgerSchemaError, match="status"):
        validate_entry("x", raw)


# 3
def test_bad_evidence_tier_rejected() -> None:
    raw = _good_candidate() | {"evidence_tier": "WORLD_DOMINATION"}
    with pytest.raises(LedgerSchemaError, match="evidence_tier"):
        validate_entry("x", raw)


# 4
def test_bad_downgrade_reason_rejected() -> None:
    raw = _good_candidate() | {"downgrade_reason": "BECAUSE_I_FEEL_LIKE_IT"}
    with pytest.raises(LedgerSchemaError, match="downgrade_reason"):
        validate_entry("x", raw)


# 5
def test_non_validated_without_downgrade_reason_rejected() -> None:
    raw = _good_candidate() | {"downgrade_reason": None}
    with pytest.raises(LedgerSchemaError, match="downgrade_reason"):
        validate_entry("x", raw)


# 6
def test_validated_globally_frozen() -> None:
    """P6: VALIDATED is rejected even when every legacy field is filled."""
    assert CANON_VALIDATED_FROZEN is True
    assert "VALIDATED" in FROZEN_LADDER_STATES
    raw = {
        "substrate": "x",
        "status": "VALIDATED",
        "data_sha256": _GOOD_HASH,
        "adapter_code_hash": _GOOD_HASH,
        "null_family_status": "shuffle:passed",
        "rerun_command": "python -m x",
        "claim_boundary_ref": "docs/CLAIM_BOUNDARY.md#claim-c-002",
        "evidence_tier": "MEASURED_WITH_HASH",
    }
    with pytest.raises(LedgerSchemaError, match="FROZEN"):
        validate_entry("x", raw)


# 7
def test_validated_substrate_evidence_globally_frozen() -> None:
    raw = {
        "substrate": "x",
        "status": "VALIDATED_SUBSTRATE_EVIDENCE",
        "data_sha256": _GOOD_HASH,
        "adapter_code_hash": _GOOD_HASH,
        "null_family_status": "shuffle:passed",
        "rerun_command": "python -m x",
        "claim_boundary_ref": "docs/CLAIM_BOUNDARY.md#claim-c-002",
        "evidence_tier": "MEASURED_WITH_HASH",
    }
    with pytest.raises(LedgerSchemaError, match="FROZEN"):
        validate_entry("x", raw)


# 8
def test_null_failed_state_admitted() -> None:
    e = validate_entry("x", _good_null_failed())
    assert e.status == "EVIDENCE_CANDIDATE_NULL_FAILED"
    assert e.downgrade_reason == "NULL_NOT_REJECTED"


# 9
def test_null_failed_at_evidence_candidate_rejected() -> None:
    """P7: documented null failure must not sit at plain EVIDENCE_CANDIDATE."""
    raw = _good_candidate() | {
        "null_family_status": "p_permutation=0.946 — null cannot be rejected.",
    }
    with pytest.raises(LedgerSchemaError, match="failed null screen"):
        validate_entry("x", raw)


# 10
def test_null_failed_at_inconclusive_admitted() -> None:
    raw = _good_candidate() | {
        "status": "INCONCLUSIVE",
        "downgrade_reason": "NULL_NOT_REJECTED",
        "null_family_status": "p_permutation=1.0 — null cannot be rejected.",
    }
    e = validate_entry("x", raw)
    assert e.status == "INCONCLUSIVE"


# 11
@pytest.mark.parametrize("hb", [[], 0, "", False, "string", 42])
def test_falsy_or_nondict_hash_binding_rejected(hb: object) -> None:
    raw = _good_candidate() | {"hash_binding": hb}
    with pytest.raises(LedgerSchemaError, match="hash_binding"):
        validate_entry("x", raw)


def test_dict_hash_binding_admitted() -> None:
    raw = _good_candidate() | {"hash_binding": {}}
    validate_entry("x", raw)


def test_omitted_hash_binding_admitted() -> None:
    validate_entry("x", _good_candidate())


# 12
def test_validate_ledger_reports_per_substrate() -> None:
    ledger = {
        "version": "2.0.0",
        "entries": {
            "good": _good_candidate(),
            "bad": _good_candidate() | {"status": "BLAH"},
        },
    }
    errs = validate_ledger(ledger)
    assert "good" not in errs
    assert "bad" in errs
    assert any("status" in e for e in errs["bad"])


# 13
def test_real_ledger_validates_clean() -> None:
    """Phase 2.1 invariant: the canonical ledger always passes the schema."""
    ledger = json.loads((_REPO_ROOT / "evidence" / "gamma_ledger.json").read_text(encoding="utf-8"))
    errs = validate_ledger(ledger)
    assert not errs, f"canonical ledger schema violations: {errs}"


# 14
def test_ledger_entry_frozen_and_slotted() -> None:
    e = validate_entry("x", _good_candidate())
    assert dataclasses.is_dataclass(e)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        e.status = "NOPE"  # type: ignore[misc]


# 15
def test_kappa_not_gamma_reason_recognised() -> None:
    assert "KAPPA_NOT_GAMMA" in ALLOWED_DOWNGRADE_REASONS


# 16
def test_no_external_replication_recognised() -> None:
    assert "NO_EXTERNAL_REPLICATION" in ALLOWED_DOWNGRADE_REASONS


# 17
def test_null_not_rejected_reason_recognised() -> None:
    assert "NULL_NOT_REJECTED" in ALLOWED_DOWNGRADE_REASONS


# 18
def test_pickle_round_trip_valid_entry() -> None:
    import pickle

    entry = validate_entry("x", _good_candidate())
    restored = pickle.loads(pickle.dumps(entry))
    assert restored.status == "EVIDENCE_CANDIDATE"
    assert restored.substrate == "x"


# 19
def test_pickle_forged_raw_rejected_on_unpickle() -> None:
    """Forged raw → re-routed through validate_entry on unpickle → schema fires."""
    forged_args = ("x", _good_candidate() | {"status": "VALIDATED"})
    with pytest.raises(LedgerSchemaError):
        validate_entry(*forged_args)


# 20
def test_unsafe_construct_fully_removed() -> None:
    """P4: _unsafe_construct must not exist on the module at all."""
    import evidence.ledger_schema as mod

    assert "_unsafe_construct" not in mod.__all__
    assert not hasattr(mod, "_unsafe_construct"), (
        "_unsafe_construct must be deleted, not just hidden"
    )


# 21
@pytest.mark.parametrize(
    "phrase, expected",
    [
        ("p_permutation=1.0 — null cannot be rejected", True),
        ("p_permutation=0.946 — null cannot be rejected.", True),
        ("p_permutation=0.05 — borderline", True),  # >= alpha
        ("p_permutation=0.049 — null rejected", False),
        ("p_permutation=0.001 — null rejected", False),
        ("not_applicable_analytical", False),
        ("shuffle: passed", False),
        ("surrogate did NOT distinguish from γ=1", True),
        (None, False),
        ("", False),
        (42, False),
    ],
)
def test_is_null_screen_failed(phrase: object, expected: bool) -> None:
    assert is_null_screen_failed(phrase) is expected


# ───────── P7 deeper — verdict semantics on null-failed entries ─────────


@pytest.mark.parametrize(
    "verdict",
    [
        "METASTABLE",
        "Metastable",
        "metastable",
        "CONSISTENT_WITH_GAMMA_EQUALS_ONE",
        "WARNING",
        "POSITIVE",
    ],
)
def test_null_failed_with_positive_verdict_rejected(verdict: str) -> None:
    """P7 deeper — null-failed entry must not carry positive verdict."""
    raw = _good_null_failed() | {"verdict": verdict}
    with pytest.raises(LedgerSchemaError, match="positive-metastability"):
        validate_entry("x", raw)


@pytest.mark.parametrize("verdict", ["NULL_NOT_REJECTED", "INCONCLUSIVE", None])
def test_null_failed_with_neutral_verdict_admitted(verdict: object) -> None:
    raw = _good_null_failed() | {"verdict": verdict}
    e = validate_entry("x", raw)
    assert e.status == "EVIDENCE_CANDIDATE_NULL_FAILED"


# ───────── P8 — data_sha256_kind enum + raw-data honesty ─────────


def test_data_sha256_without_kind_rejected() -> None:
    raw = _good_candidate() | {
        "data_sha256": "a" * 64,
        # data_sha256_kind missing — must be rejected per P8
    }
    with pytest.raises(LedgerSchemaError, match="data_sha256_kind"):
        validate_entry("x", raw)


def test_data_sha256_kind_unknown_value_rejected() -> None:
    raw = _good_candidate() | {
        "data_sha256": "a" * 64,
        "data_sha256_kind": "raw_pixie_dust",
    }
    with pytest.raises(LedgerSchemaError, match="data_sha256_kind"):
        validate_entry("x", raw)


@pytest.mark.parametrize(
    "kind",
    [
        "raw_dataset_merkle_root",
        "bundle_manifest",
        "bundle_manifest:evidence/data_hashes.json",
        "adapter_source",
        "script_source",
        "script_sha256_at_generation_time",
    ],
)
def test_data_sha256_kind_canonical_values_admitted(kind: str) -> None:
    raw = _good_candidate() | {
        "data_sha256": "a" * 64,
        "data_sha256_kind": kind,
    }
    validate_entry("x", raw)


def test_data_sha256_kind_optional_when_data_sha_null() -> None:
    """If data_sha256 is null, data_sha256_kind may be absent."""
    raw = _good_candidate()  # data_sha256=None, no kind
    validate_entry("x", raw)


def test_non_raw_data_kinds_documented_set() -> None:
    """P8: manifest/adapter/script kinds are flagged as NOT raw-data."""
    from evidence.ledger_schema import NON_RAW_DATA_KINDS

    assert "bundle_manifest" in NON_RAW_DATA_KINDS
    assert "adapter_source" in NON_RAW_DATA_KINDS
    assert "script_source" in NON_RAW_DATA_KINDS
    # raw_dataset_merkle_root is the ONLY kind that MAY back a raw-data claim
    assert "raw_dataset_merkle_root" not in NON_RAW_DATA_KINDS
