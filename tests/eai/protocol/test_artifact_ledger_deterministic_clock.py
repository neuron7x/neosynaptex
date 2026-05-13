"""Ledger contract: injectable clock yields deterministic transcripts.

Three invariants are pinned:
1. Same inputs + fixed clock => byte-identical ledger entries.
2. The retention-hash regex still fails closed regardless of the clock.
3. The default-construction path (no clock injection) keeps the
   real UTC wall-clock as the timestamp source.
"""

from __future__ import annotations

import re
from itertools import count

import pytest

from core.artifact_ledger import ArtifactLedger, LedgerEntry

_HEX = "a" * 64


def _fixed_clock() -> str:
    return "1970-01-01T00:00:00+00:00"


def test_same_inputs_with_fixed_clock_produce_identical_entries() -> None:
    a = ArtifactLedger(clock=_fixed_clock)
    b = ArtifactLedger(clock=_fixed_clock)
    e_a = a.append("EVD-1", "CLM-1", "EVIDENCE", _HEX)
    e_b = b.append("EVD-1", "CLM-1", "EVIDENCE", _HEX)
    assert e_a == e_b
    assert isinstance(e_a, LedgerEntry)
    assert e_a.timestamp_utc == "1970-01-01T00:00:00+00:00"


def test_sequence_with_monotonic_clock_replays_byte_for_byte() -> None:
    counter = count()

    def monotonic_clock() -> str:
        return f"1970-01-01T00:00:{next(counter):02d}+00:00"

    ledger = ArtifactLedger(clock=monotonic_clock)
    entries = [ledger.append(f"EVD-{i}", f"CLM-{i}", "EVIDENCE", _HEX) for i in range(5)]
    timestamps = [e.timestamp_utc for e in entries]
    assert timestamps == [f"1970-01-01T00:00:0{i}+00:00" for i in range(5)]
    # Order in the internal list mirrors append order.
    assert [e.artifact_id for e in ledger.entries] == [f"EVD-{i}" for i in range(5)]


def test_invalid_hash_still_fails_closed_under_fixed_clock() -> None:
    ledger = ArtifactLedger(clock=_fixed_clock)
    with pytest.raises(ValueError, match="retention_hash must be lowercase SHA-256 hex"):
        ledger.append("EVD-X", "CLM-X", "EVIDENCE", "not-a-hex-digest")
    # Failed appends must NOT leak into the ledger.
    assert ledger.entries == []


def test_default_clock_remains_available_and_returns_real_utc_iso() -> None:
    ledger = ArtifactLedger()
    entry = ledger.append("EVD-D", "CLM-D", "EVIDENCE", _HEX)
    # The default clock yields a real timestamp; assert *shape*, not value.
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00",
        entry.timestamp_utc,
    ), entry.timestamp_utc
