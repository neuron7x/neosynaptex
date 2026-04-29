"""Canonicalised JSON → SHA-256 result_hash.

Phase 3 binds every published result to an explicit content hash so
that:

* re-runs at the same seed and M produce a byte-identical
  ``result_hash`` (plan §7 test 6);
* CI on ``main`` can pin the canonical screen output and fail closed
  on drift;
* ledger-update proposals carry a structural binding to the source
  result, closing audit-B-style "stale hash" failure modes.

Canonicalisation rules (single-source-of-truth for Phase 3):

* The hash payload is the result dict with non-deterministic fields
  removed — the hash itself, wall-clock timestamps, and runtime
  measurements. Two runs differ in those fields by design; the hash
  must not.
* ``json.dumps(payload, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False, allow_nan=False)`` — sorted keys, no spaces,
  UTF-8, NaN/Inf rejected.
* The encoded UTF-8 bytes are fed to ``hashlib.sha256``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = [
    "NON_DETERMINISTIC_FIELDS",
    "canonical_json_bytes",
    "compute_result_hash",
]


#: Top-level fields stripped before hashing. The listed fields vary
#: across re-runs by design — wall-clock time, measured CPU runtime,
#: and the hash itself (a result cannot hash itself).
NON_DETERMINISTIC_FIELDS: frozenset[str] = frozenset(
    {
        "result_hash",
        "generated_at_utc",
        "runtime_seconds",
    }
)


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Return the canonicalised JSON byte string for ``payload``.

    Strips ``NON_DETERMINISTIC_FIELDS`` so payloads can be hashed
    before *or* after stamping the hash onto the result dict.
    """
    stripped = {k: v for k, v in payload.items() if k not in NON_DETERMINISTIC_FIELDS}
    text = json.dumps(
        stripped,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def compute_result_hash(payload: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of the canonicalised ``payload``."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
