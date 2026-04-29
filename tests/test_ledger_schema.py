"""Tests for evidence/ledger_schema.py — Phase 2 ledger schema validator.

Numbered tests:
1.  Clean fixture passes ``validate_entry``.
2.  Bad status (not in ladder) raises LedgerSchemaError.
3.  Bad evidence_tier raises.
4.  Bad downgrade_reason raises.
5.  VALIDATED without data_sha256 raises.
6.  VALIDATED without adapter_code_hash raises.
7.  VALIDATED without null_family_status raises.
8.  VALIDATED without rerun_command raises.
9.  VALIDATED without claim_boundary_ref raises.
10. VALIDATED with downgrade_reason raises.
11. Non-VALIDATED non-NO_ADMISSIBLE without downgrade_reason raises.
12. ``validate_ledger`` reports per-substrate errors.
13. Real repository ledger validates clean (Phase 2 invariant).
14. ``LedgerEntry`` is frozen and slot-only.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from evidence.ledger_schema import (
    ALLOWED_DOWNGRADE_REASONS,
    LedgerEntry,
    LedgerSchemaError,
    validate_entry,
    validate_ledger,
)

_GOOD_HASH = "0" * 64
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _good_validated() -> dict[str, Any]:
    return {
        "substrate": "x",
        "status": "VALIDATED",
        "data_sha256": _GOOD_HASH,
        "adapter_code_hash": _GOOD_HASH,
        "null_family_status": "shuffle:passed",
        "rerun_command": "python -m x",
        "claim_boundary_ref": "docs/CLAIM_BOUNDARY.md#claim-c-002",
        "evidence_tier": "MEASURED_WITH_HASH",
    }


# 1
def test_clean_fixture_validates() -> None:
    e = validate_entry("x", _good_validated())
    assert isinstance(e, LedgerEntry)
    assert e.status == "VALIDATED"


# 2
def test_bad_status_rejected() -> None:
    raw = _good_validated() | {"status": "NOT_A_REAL_STATUS"}
    with pytest.raises(LedgerSchemaError, match="status"):
        validate_entry("x", raw)


# 3
def test_bad_evidence_tier_rejected() -> None:
    raw = _good_validated() | {"evidence_tier": "WORLD_DOMINATION"}
    with pytest.raises(LedgerSchemaError, match="evidence_tier"):
        validate_entry("x", raw)


# 4
def test_bad_downgrade_reason_rejected() -> None:
    raw = _good_validated() | {
        "status": "EVIDENCE_CANDIDATE",
        "downgrade_reason": "BECAUSE_I_FEEL_LIKE_IT",
    }
    with pytest.raises(LedgerSchemaError, match="downgrade_reason"):
        validate_entry("x", raw)


# 5
def test_validated_without_data_sha256_rejected() -> None:
    raw = _good_validated() | {"data_sha256": None}
    with pytest.raises(LedgerSchemaError, match="data_sha256"):
        validate_entry("x", raw)


# 6
def test_validated_without_adapter_code_hash_rejected() -> None:
    raw = _good_validated() | {"adapter_code_hash": "see something"}
    with pytest.raises(LedgerSchemaError, match="adapter_code_hash"):
        validate_entry("x", raw)


# 7
def test_validated_without_null_family_status_rejected() -> None:
    raw = _good_validated() | {"null_family_status": None}
    with pytest.raises(LedgerSchemaError, match="null_family_status"):
        validate_entry("x", raw)


# 8
def test_validated_without_rerun_command_rejected() -> None:
    raw = _good_validated() | {"rerun_command": ""}
    with pytest.raises(LedgerSchemaError, match="rerun_command"):
        validate_entry("x", raw)


# 9
def test_validated_without_claim_boundary_ref_rejected() -> None:
    raw = _good_validated() | {"claim_boundary_ref": None}
    with pytest.raises(LedgerSchemaError, match="claim_boundary_ref"):
        validate_entry("x", raw)


# 10
def test_validated_with_downgrade_reason_rejected() -> None:
    raw = _good_validated() | {"downgrade_reason": "KAPPA_NOT_GAMMA"}
    with pytest.raises(LedgerSchemaError, match="downgrade_reason"):
        validate_entry("x", raw)


# 11
def test_non_validated_without_downgrade_reason_rejected() -> None:
    raw = {
        "substrate": "x",
        "status": "EVIDENCE_CANDIDATE",
        "data_sha256": None,
        "adapter_code_hash": None,
        "null_family_status": None,
        "rerun_command": None,
        "claim_boundary_ref": "docs/CLAIM_BOUNDARY.md#claim-c-003",
        "evidence_tier": "MEASURED_NO_HASH",
    }
    with pytest.raises(LedgerSchemaError, match="downgrade_reason"):
        validate_entry("x", raw)


# 12
def test_validate_ledger_reports_per_substrate() -> None:
    ledger = {
        "version": "2.0.0",
        "entries": {
            "good": _good_validated(),
            "bad": _good_validated() | {"status": "BLAH"},
        },
    }
    errs = validate_ledger(ledger)
    assert "good" not in errs
    assert "bad" in errs
    assert any("status" in e for e in errs["bad"])


# 13
def test_real_ledger_validates_clean() -> None:
    """Phase 2 invariant: the canonical ledger always passes the schema."""
    ledger = json.loads((_REPO_ROOT / "evidence" / "gamma_ledger.json").read_text(encoding="utf-8"))
    errs = validate_ledger(ledger)
    assert not errs, f"canonical ledger schema violations: {errs}"


# 14
def test_ledger_entry_frozen_and_slotted() -> None:
    e = validate_entry("x", _good_validated())
    assert dataclasses.is_dataclass(e)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        e.status = "NOPE"  # type: ignore[misc]


def test_kappa_not_gamma_reason_recognised() -> None:
    """`KAPPA_NOT_GAMMA` must be a canonical downgrade reason."""
    assert "KAPPA_NOT_GAMMA" in ALLOWED_DOWNGRADE_REASONS


def test_no_external_replication_recognised() -> None:
    assert "NO_EXTERNAL_REPLICATION" in ALLOWED_DOWNGRADE_REASONS
