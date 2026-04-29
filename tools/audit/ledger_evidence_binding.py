"""Runtime repo-file hash binding gate.

Phase 2.1 hardening — closes audit-B1 (format-only check) and audit-B2
(stale hashes already in the ledger). Stanford/MIT review hardening
adds P1 (path-traversal safety) and P2 (strict ``hash_binding`` typing).

Scope discipline (P0)
---------------------

This is **not** a "cryptographic evidence chain" — it is a runtime
repo-file hash binding gate. It can prove: *the SHA-256 stored in the
ledger equals the SHA-256 of a file at a repo-relative path that
resolves inside the repository working tree*. It does **not** prove:
provenance of the data, signed attestation, pipeline integrity, result
reproducibility, or anything about external datasets that are not
themselves in the repo. Those gates live elsewhere (Phase 3+).

Contract
--------

Every entry in ``evidence/gamma_ledger.json`` whose ``data_sha256`` or
``adapter_code_hash`` is non-null MUST also declare a binding under

    "hash_binding": {
        "data_sha256_source":      "<repo-relative path>",
        "adapter_code_hash_source": "<repo-relative path>"
    }

This tool walks every binding, computes the SHA-256 of the named file
(restricted to repo-internal paths only), and compares it to the stored
value using constant-time comparison (``hmac.compare_digest``).

Honest-null contract
--------------------

* ``stored == None  AND  source == None``: ADMITTED (no claim made).
* ``stored != None  AND  source == None``: REJECTED — unbound hash.
* ``stored == None  AND  source != None``: REJECTED — binding without value.
* both non-null: hashes must match.

Path safety (P1)
----------------

Source paths must:

* be strings, non-empty, contain no NUL or other ASCII control chars,
* be **relative** (no leading ``/``, no Windows drive letter),
* contain no ``..`` segment (post-``PurePosixPath`` parse),
* resolve (with symlinks followed) to a path that
  ``Path.relative_to(repo_root.resolve(strict=True))`` accepts,
* point to a regular file (not a directory, socket, or device).

Any violation is reported as a binding violation; the file is **not**
hashed.

``hash_binding`` typing (P2)
----------------------------

* Missing or ``None`` → treated as ``{}`` (no bindings).
* Plain ``dict`` → bindings.
* Anything else (``list``, ``str``, ``int``, ``False``, …) → REJECTED.
  No falsy-non-dict coercion.

Exit codes
----------

* 0 — every declared hash matches its on-disk source and every
  source path is repo-internal.
* 2 — at least one entry is unbound, missing, drifting, or has an
  unsafe source path.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

__all__ = [
    "BindingError",
    "collect_violations",
    "compute_file_hash",
    "is_safe_repo_path",
    "main",
    "resolve_repo_relative_source",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LEDGER = _REPO_ROOT / "evidence" / "gamma_ledger.json"

#: Windows drive letter / UNC prefixes; rejected even on POSIX hosts.
_DRIVE_RE = re.compile(r"^([a-zA-Z]:|\\\\)")

#: ASCII control characters (incl. NUL) — never permitted in paths.
_CONTROL_CHARS = set(chr(i) for i in range(0x20)) | {chr(0x7F)}


class BindingError(ValueError):
    """Raised when a ledger entry's stored hash does not match disk."""


def compute_file_hash(path: Path) -> str:
    """Return the SHA-256 hex of ``path`` (streaming, 1 MiB chunks)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _path_violation(source: str) -> str | None:
    """Return a human-readable violation if ``source`` is unsafe.

    Pure string-level checks; resolution is the caller's job.
    """
    if not isinstance(source, str):
        return f"source path is not a str: {type(source).__name__}"
    if source == "":
        return "source path is empty"
    if any(c in source for c in _CONTROL_CHARS):
        return "source path contains ASCII control characters"
    if _DRIVE_RE.match(source):
        return f"source path looks absolute (drive/UNC): {source!r}"
    if source.startswith("/") or source.startswith("\\"):
        return f"source path is absolute: {source!r}"
    parts = PurePosixPath(source).parts
    if any(p == ".." for p in parts):
        return f"source path contains '..' traversal: {source!r}"
    # P1 (Stanford/MIT review): explicit reject of "." / "./" / pure-dot
    # paths. They resolve to the repo root (a directory), which the
    # is_file() check would also catch — but the spec asks for explicit
    # name-level rejection so the violation message stays precise.
    if all(p in {".", "./"} or p == "" for p in parts) or source.strip() in {".", "./"}:
        return f"source path is the bare repo-root '.': {source!r}"
    return None


def resolve_repo_relative_source(source: object, repo_root: Path) -> Path:
    """Resolve ``source`` to a regular file inside ``repo_root`` or RAISE.

    Phase 2.1 P1 (Stanford/MIT review) raise-style API. Use this when
    you want an exception on violation; ``is_safe_repo_path`` keeps the
    tuple-style API for the binding-walk that aggregates messages.

    Returns the symlink-resolved absolute path (always inside
    ``repo_root.resolve()``). Raises :class:`BindingError` on any of:

    * non-string source,
    * empty source,
    * ASCII control characters,
    * Windows drive / UNC prefix,
    * leading ``/`` or ``\\``,
    * any ``..`` segment,
    * the bare ``"."`` (repo root, never a regular file),
    * resolved path outside ``repo_root.resolve()``,
    * non-existent path,
    * non-regular path (directory, socket, device).
    """
    if not isinstance(source, str):
        raise BindingError(f"source must be a non-empty string; got {type(source).__name__}")
    ok, err = is_safe_repo_path(source, repo_root=repo_root)
    if not ok:
        raise BindingError(err or f"source path {source!r} rejected")
    return (repo_root / source).resolve(strict=False)


def is_safe_repo_path(source: str, *, repo_root: Path) -> tuple[bool, str | None]:
    """Validate that ``source`` resolves to a regular file inside ``repo_root``.

    Returns ``(ok, violation_message)``. ``ok`` is ``True`` only when:

    * ``_path_violation(source)`` returns ``None``, AND
    * ``(repo_root / source)`` exists, is a regular file, and the
      symlink-resolved absolute path is contained in ``repo_root.resolve(strict=True)``.
    """
    msg = _path_violation(source)
    if msg is not None:
        return False, msg
    candidate = repo_root / source
    try:
        resolved = candidate.resolve(strict=False)
        repo_resolved = repo_root.resolve(strict=False)
    except OSError as exc:  # pragma: no cover — IO sanity guard
        return False, f"could not resolve {source!r}: {exc}"
    # Containment check via resolve()-then-relative_to. This catches both
    # symlinks pointing outside the repo and any residual ``..`` that
    # survived the string-level scan.
    try:
        resolved.relative_to(repo_resolved)
    except ValueError:
        return False, (
            f"source path {source!r} resolves to {resolved} which is outside "
            f"the repository root {repo_resolved}"
        )
    if not resolved.exists():
        return False, f"source file does not exist on disk: {source!r}"
    if not resolved.is_file():
        return False, (
            f"source path {source!r} resolves to a non-regular path "
            f"({'directory' if resolved.is_dir() else 'special file'})"
        )
    return True, None


_HASH_FIELDS: tuple[tuple[str, str], ...] = (
    ("data_sha256", "data_sha256_source"),
    ("adapter_code_hash", "adapter_code_hash_source"),
)


def _coerce_hash_binding(raw_binding: object) -> tuple[dict[str, object] | None, str | None]:
    """Strict P2 coercion. Returns ``(binding_dict, violation_message)``.

    * ``None`` or missing → ``({}, None)``
    * ``dict``           → ``(dict, None)``
    * anything else      → ``(None, "<message>")``
    """
    if raw_binding is None:
        return {}, None
    if isinstance(raw_binding, dict):
        return raw_binding, None
    return None, (
        f"hash_binding must be a dict or omitted; "
        f"got {raw_binding!r} (type {type(raw_binding).__name__})"
    )


def collect_violations(ledger: dict[str, Any], *, repo_root: Path = _REPO_ROOT) -> list[str]:
    """Return human-readable binding violations across the ledger.

    Empty list ↔ every declared hash matches its declared source AND
    every source path is repo-internal.
    """
    out: list[str] = []
    for sid, entry in ledger.get("entries", {}).items():
        if not isinstance(entry, dict):
            out.append(f"{sid}: entry is not a dict")
            continue
        binding, type_err = _coerce_hash_binding(entry.get("hash_binding"))
        if type_err is not None:
            out.append(f"{sid}: {type_err}")
            continue
        assert binding is not None  # narrowed by _coerce_hash_binding
        for hash_field, source_field in _HASH_FIELDS:
            stored = entry.get(hash_field)
            source = binding.get(source_field)
            if stored is None and source is None:
                continue  # honest null
            if stored is None and source is not None:
                out.append(
                    f"{sid}: {hash_field}=null but hash_binding.{source_field}={source!r} "
                    "(declared source without a hash)"
                )
                continue
            if stored is not None and source is None:
                out.append(
                    f"{sid}: {hash_field}={stored[:16]}... declared without "
                    f"hash_binding.{source_field} — UNBOUND HASH"
                )
                continue
            try:
                resolved = resolve_repo_relative_source(source, repo_root)
            except BindingError as exc:
                out.append(f"{sid}: {hash_field} → {source!r} unsafe — {exc}")
                continue
            actual = compute_file_hash(resolved)
            if not hmac.compare_digest(str(stored), actual):
                out.append(
                    f"{sid}: {hash_field} DRIFT — "
                    f"stored {str(stored)[:16]}... vs actual {actual[:16]}... "
                    f"(source={source})"
                )
    return out


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default=str(_LEDGER), type=Path)
    args = parser.parse_args(argv)
    if not args.ledger.is_file():
        print(f"ERROR: ledger not found: {args.ledger}", file=sys.stderr)
        return 2
    try:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: ledger JSON parse error: {exc}", file=sys.stderr)
        return 2
    violations = collect_violations(ledger)
    if violations:
        print(
            f"BINDING DRIFT: {len(violations)} violation(s):",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 2
    bound = sum(
        1
        for e in ledger.get("entries", {}).values()
        if e.get("data_sha256") or e.get("adapter_code_hash")
    )
    print(
        f"OK: every declared hash recomputed against disk and bound to a "
        f"repo-internal source path; {bound} entr(ies) carry at least one binding."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
