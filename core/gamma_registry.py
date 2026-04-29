"""Gamma Registry -- single programmatic API for all gamma values.

All gamma values MUST come from gamma_ledger.json via this registry.
INV-1: gamma derived only, never assigned.

Phase 2.1 hardening
-------------------

Closes audit-B4 ("runtime never validates") and Stanford/MIT review
P3+P5: every load runs **two** fail-closed gates before populating the
cache:

1. ``evidence.ledger_schema.validate_ledger`` — schema check
   (status, downgrade reason, frozen-ladder freeze, null-failed
   verdict semantics, hash_binding type discipline).
2. ``tools.audit.ledger_evidence_binding.collect_violations`` —
   runtime hash-binding check (recompute every declared SHA-256 from
   the named repo-internal source).

Both must pass. Any violation raises :class:`GammaRegistryError` and
the cache is **never** populated. There is **no env-var escape hatch**
(P5): tests that need a synthetic ledger pass an explicit
``ledger_path`` to a test-only loader.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evidence.ledger_schema import validate_ledger
from tools.audit.ledger_evidence_binding import collect_violations

__all__ = [
    "GammaRegistry",
    "GammaRegistryError",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LEDGER_PATH = _REPO_ROOT / "evidence" / "gamma_ledger.json"


class GammaRegistryError(Exception):
    pass


class GammaRegistry:
    """Read-only gateway to gamma_ledger.json with runtime verification."""

    _cache: dict[str, Any] | None = None
    _ledger_hash: str | None = None

    @classmethod
    def _load(cls, force: bool = False) -> dict[str, Any]:
        if cls._cache is not None and not force:
            return cls._cache
        if not _LEDGER_PATH.exists():
            raise GammaRegistryError(f"Ledger not found: {_LEDGER_PATH}")
        raw = _LEDGER_PATH.read_bytes()
        ledger_hash = hashlib.sha256(raw).hexdigest()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GammaRegistryError(f"ledger JSON parse error: {exc}") from exc

        # Gate 1: schema validation (P3, was already there, kept).
        schema_errs = validate_ledger(parsed)
        if schema_errs:
            raise GammaRegistryError(
                f"ledger fails schema validation; runtime refuses to load. violations={schema_errs}"
            )

        # Gate 2 (Phase 2.1 P3): runtime hash-binding recomputation.
        # Required so a caller cannot land a ledger whose stored hashes
        # drifted from disk between schema-time and runtime.
        binding_errs = collect_violations(parsed, repo_root=_REPO_ROOT)
        if binding_errs:
            raise GammaRegistryError(
                "ledger fails binding validation; runtime refuses to load. "
                f"violations={binding_errs}"
            )

        # Only mutate cache after both gates pass.
        cls._ledger_hash = ledger_hash
        cls._cache = parsed
        return cls._cache

    @classmethod
    def ledger_hash(cls) -> str:
        cls._load()
        return cls._ledger_hash  # type: ignore[return-value]

    @classmethod
    def get(cls, entry_id: str, field: str = "gamma") -> Any:
        ledger = cls._load()
        entries = ledger.get("entries", {})
        if entry_id not in entries:
            raise GammaRegistryError(f"Unknown entry: {entry_id}")
        entry = entries[entry_id]
        if field not in entry:
            raise GammaRegistryError(f"Field '{field}' not in entry '{entry_id}'")
        return entry[field]

    @classmethod
    def get_entry(cls, entry_id: str) -> dict[str, Any]:
        ledger = cls._load()
        entries = ledger.get("entries", {})
        if entry_id not in entries:
            raise GammaRegistryError(f"Unknown entry: {entry_id}")
        return dict(entries[entry_id])

    @classmethod
    def is_locked(cls, entry_id: str) -> bool:
        return bool(cls.get(entry_id, "locked"))

    @classmethod
    def all_entries(cls) -> dict[str, dict[str, Any]]:
        ledger = cls._load()
        return dict(ledger.get("entries", {}))

    @classmethod
    def verify_hash(cls, entry_id: str, expected_hash: str) -> bool:
        entry = cls.get_entry(entry_id)
        ds = entry.get("data_source", {})
        actual = ds.get("sha256")
        if actual is None:
            return False
        return bool(actual == expected_hash)

    @classmethod
    def locked_entries(cls) -> dict[str, dict[str, Any]]:
        return {k: v for k, v in cls.all_entries().items() if v.get("locked", False)}

    @classmethod
    def requires_rederivation(cls) -> dict[str, dict[str, Any]]:
        return {
            k: v for k, v in cls.all_entries().items() if v.get("status") == "REQUIRES_REDERIVATION"
        }

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cache = None
        cls._ledger_hash = None
