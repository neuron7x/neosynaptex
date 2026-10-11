"""Tests for STACK.lock enforcement (Task 11)."""

from __future__ import annotations

import pytest

from tools.audit.stack_lock_check import _matches, _parse_stack_lock, check


def test_matches_pep440ish() -> None:
    assert _matches("2.4.3", ">=2.2.6,<3.0")
    assert not _matches("1.9.0", ">=2.2.6,<3.0")
    assert not _matches("3.0.0", ">=2.2.6,<3.0")
    assert _matches("1.17.1", ">=1.15.3,<2.0")
    assert _matches("4.3.1", ">=4.3.1,<5.0")


def test_parse_stack_lock_round_trip() -> None:
    text = (
        "schema_version: 1\n"
        'canonical_stack_version: "1.0.0"\n'
        "\n"
        "required:\n"
        '  numpy: ">=2.2.6,<3.0"\n'
        '  scipy: ">=1.15.3,<2.0"\n'
        "frozen_at_commit:\n"
        '  numpy: "2.4.3"\n'
    )
    d = _parse_stack_lock(text)
    assert d["schema_version"] == 1
    assert d["canonical_stack_version"] == "1.0.0"
    assert d["required"]["numpy"] == ">=2.2.6,<3.0"
    assert d["frozen_at_commit"]["numpy"] == "2.4.3"


def test_stack_lock_matches_installed_versions() -> None:
    errors = check()
    if errors:
        pytest.fail("STACK.lock mismatch: " + "; ".join(errors))
