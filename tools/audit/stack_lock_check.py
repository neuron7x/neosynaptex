"""Enforce STACK.lock — Task 11 of the γ-program remediation protocol.

Exit 0 if every pinned package matches its ``required:`` specifier in
``STACK.lock``. Exit 2 otherwise.

The check is intentionally tolerant: we match against PEP 440
specifiers (``>=a,<b``), not exact-equality. The ``frozen_at_commit``
block is informational — it records the exact versions that produced
the committed artefacts so replication is byte-comparable when a
replicator pins to those values.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_STACK_PATH = _REPO / "STACK.lock"

_SPEC_RE = re.compile(r"\s*([<>=!~]=?)\s*([0-9][0-9a-zA-Z.+-]*)")


def _parse_spec(s: str) -> list[tuple[str, tuple[int, ...]]]:
    """Return a list of (op, version_tuple) pairs from a PEP-440-ish string."""

    parts: list[tuple[str, tuple[int, ...]]] = []
    for chunk in s.split(","):
        m = _SPEC_RE.match(chunk.strip())
        if not m:
            raise ValueError(f"unparseable spec: {s!r}")
        op, ver = m.group(1), m.group(2)
        parts.append((op, _ver_tuple(ver)))
    return parts


def _ver_tuple(v: str) -> tuple[int, ...]:
    out = []
    for part in re.split(r"[.\-+]", v):
        try:
            out.append(int(part))
        except ValueError:
            break
    return tuple(out)


def _matches(installed: str, spec: str) -> bool:
    iv = _ver_tuple(installed)
    for op, sv in _parse_spec(spec):
        if op == ">=" and not (iv >= sv):
            return False
        if op == "<" and not (iv < sv):
            return False
        if op == "==" and iv != sv:
            return False
        if op == "!=" and iv == sv:
            return False
        if op == ">" and not (iv > sv):
            return False
        if op == "<=" and not (iv <= sv):
            return False
    return True


def _parse_stack_lock(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"required": {}, "frozen_at_commit": {}}
    section: str | None = None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("schema_version:"):
            out["schema_version"] = int(s.split(":", 1)[1].strip())
            continue
        if s.startswith("canonical_stack_version:"):
            out["canonical_stack_version"] = s.split(":", 1)[1].strip().strip('"')
            continue
        if s in ("required:", "frozen_at_commit:"):
            section = s[:-1]
            continue
        if section and line.startswith("  ") and ":" in s:
            name, _, val = s.partition(":")
            out[section][name.strip()] = val.strip().strip('"')
    return out


def check(stack_path: Path = _STACK_PATH) -> list[str]:
    """Return list of violations; empty list means OK."""

    data = _parse_stack_lock(stack_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for pkg, spec in data["required"].items():
        try:
            mod = importlib.import_module(pkg)
        except ModuleNotFoundError:
            errors.append(f"{pkg}: required by STACK.lock but not installed")
            continue
        installed = getattr(mod, "__version__", None)
        if installed is None:
            errors.append(f"{pkg}: no __version__ attribute")
            continue
        if not _matches(installed, spec):
            errors.append(f"{pkg}: installed {installed!r} does not match STACK.lock spec {spec!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    errors = check()
    if errors:
        print("STACK.lock violations:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 2
    print("STACK.lock OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
