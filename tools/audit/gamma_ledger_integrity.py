"""Gamma-ledger integrity gate — γ-claims must not silently rot.

Signal contract
---------------

``evidence/gamma_ledger.json`` is the authoritative store of γ
measurements. Every entry is a **measured** claim under
``docs/SYSTEM_PROTOCOL.md`` discipline, not a hypothesis or an
analogy. This tool verifies the ledger's **structural invariants**:

* File parses as JSON.
* Top-level has ``version``, ``invariant``, ``entries``.
* Each entry carries the required keys (``substrate``, ``gamma``,
  ``ci_low``, ``ci_high``, ``status``, ``tier``, ``locked``,
  ``derivation_method``, ``method_tier``).
* ``ci_low <= gamma <= ci_high`` and all three are positive
  (γ is a positive-valued metastability signature; a negative CI
  lower bound is a numerical or sign-convention bug).
* ``method_tier`` matches ``^T[1-5]$``.
* ``status`` is in the canonical taxonomy.
* ``locked`` is a boolean.
* ``data_source`` is a mapping with ``file`` and ``sha256`` keys.

Scope
-----

Structural only. Does NOT:

* Re-compute γ values.
* Verify that the reported CI was actually computed with the
  declared method.
* Cross-check ``gamma`` against an external dataset.
* Enforce that γ is near 1.0 — the canon explicitly permits γ ≠ 1
  as legitimate evidence for a substrate in the
  ``falsified``/``WARNING``/``METASTABLE`` space.

Semantic correctness of the measurement stays the reviewer's job
per ``docs/ADVERSARIAL_CONTROLS.md``.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

__all__ = [
    "ALLOWED_STATUSES",
    "METHOD_TIER_REGEX",
    "REQUIRED_ENTRY_KEYS",
    "IntegrityError",
    "load_ledger",
    "main",
    "run_check",
]

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_LEDGER_PATH = _REPO_ROOT / "evidence" / "gamma_ledger.json"

REQUIRED_ENTRY_KEYS: frozenset[str] = frozenset(
    {
        "substrate",
        "description",
        "gamma",
        "ci_low",
        "ci_high",
        "status",
        "tier",
        "locked",
        "derivation_method",
        "method_tier",
        "data_source",
    }
)

ALLOWED_STATUSES: frozenset[str] = frozenset(
    {
        "VALIDATED",
        "PENDING",
        "INVALIDATED",
        "FALSIFIED",
        "DRAFT",
        # Phase 2 hardening (ledger v2.0.0): canonical claim ladder per
        # docs/architecture/recursive_claim_refinement.md §2 plus extended
        # sub-VALIDATED states authorised by the Phase 2 protocol.
        "EVIDENCE_CANDIDATE",
        "LOCAL_STRUCTURAL_EVIDENCE_ONLY",
        "ARTIFACT_SUSPECTED",
        "NO_ADMISSIBLE_CLAIM",
        "SUPPORTED_BY_NULLS",
        "VALIDATED_SUBSTRATE_EVIDENCE",
        "BLOCKED_BY_METHOD_DEFINITION",
        "INCONCLUSIVE",
    }
)

METHOD_TIER_REGEX = re.compile(r"^T[1-5]$")


class IntegrityError(ValueError):
    """Raised when the ledger cannot be parsed into the expected shape."""


def load_ledger(path: pathlib.Path = _LEDGER_PATH) -> dict:
    if not path.is_file():
        raise IntegrityError(f"gamma_ledger not found at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IntegrityError(f"gamma_ledger.json: JSON parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise IntegrityError("gamma_ledger.json: top-level must be an object")
    for key in ("version", "invariant", "entries"):
        if key not in data:
            raise IntegrityError(f"gamma_ledger.json: missing top-level key {key!r}")
    if not isinstance(data["entries"], dict):
        raise IntegrityError("gamma_ledger.json: 'entries' must be an object")
    return data


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_entry(entry_id: str, entry: dict) -> list[str]:
    errors: list[str] = []

    missing = REQUIRED_ENTRY_KEYS - entry.keys()
    if missing:
        errors.append(f"{entry_id}: missing keys {sorted(missing)}")

    # Phase 2 hardening: substrates that do not emit γ (e.g. BN-Syn after
    # κ ≠ γ downgrade to LOCAL_STRUCTURAL_EVIDENCE_ONLY) carry null gamma /
    # ci_low / ci_high. This is the canonically correct representation —
    # null is preferred over a fabricated κ-as-γ value. Skip the numeric
    # check for these entries.
    status_for_numeric = entry.get("status")
    skip_numeric_check = status_for_numeric in {
        "LOCAL_STRUCTURAL_EVIDENCE_ONLY",
        "BLOCKED_BY_METHOD_DEFINITION",
        "NO_ADMISSIBLE_CLAIM",
        "FALSIFIED",
    }
    if not skip_numeric_check:
        for numeric_key in ("gamma", "ci_low", "ci_high"):
            if numeric_key in entry and not _is_number(entry[numeric_key]):
                errors.append(f"{entry_id}: {numeric_key}={entry[numeric_key]!r} must be numeric")

    if all(_is_number(entry.get(k)) for k in ("gamma", "ci_low", "ci_high")):
        gamma = float(entry["gamma"])
        ci_low = float(entry["ci_low"])
        ci_high = float(entry["ci_high"])
        if not (ci_low <= gamma <= ci_high):
            errors.append(
                f"{entry_id}: CI envelope violation — "
                f"ci_low={ci_low} <= gamma={gamma} <= ci_high={ci_high} required"
            )
        for label, value in (("gamma", gamma), ("ci_low", ci_low), ("ci_high", ci_high)):
            if value <= 0:
                errors.append(
                    f"{entry_id}: {label}={value} must be > 0 "
                    "(γ is a positive metastability signature)"
                )

    status = entry.get("status")
    if isinstance(status, str) and status not in ALLOWED_STATUSES:
        errors.append(f"{entry_id}: status {status!r} not in {sorted(ALLOWED_STATUSES)}")

    tier = entry.get("method_tier")
    if isinstance(tier, str) and not METHOD_TIER_REGEX.match(tier):
        errors.append(f"{entry_id}: method_tier {tier!r} must match {METHOD_TIER_REGEX.pattern}")

    if "locked" in entry and not isinstance(entry["locked"], bool):
        errors.append(f"{entry_id}: locked={entry['locked']!r} must be boolean")

    substrate = entry.get("substrate")
    if isinstance(substrate, str) and not substrate.strip():
        errors.append(f"{entry_id}: substrate must be a non-empty string")

    ds = entry.get("data_source")
    if ds is not None:
        if not isinstance(ds, dict):
            errors.append(f"{entry_id}: data_source must be an object")
        else:
            for expected in ("file", "sha256"):
                if expected not in ds:
                    errors.append(f"{entry_id}: data_source missing key {expected!r}")

    # Optional numeric fields: if present AND not null, must be numeric.
    for optional_key in ("r2", "n_pairs", "p_permutation"):
        if optional_key in entry:
            val = entry[optional_key]
            if val is not None and not _is_number(val):
                errors.append(f"{entry_id}: {optional_key}={val!r} must be numeric or null")

    return errors


def run_check(path: pathlib.Path = _LEDGER_PATH) -> tuple[int, str]:
    try:
        data = load_ledger(path)
    except IntegrityError as exc:
        return 2, f"DRIFT: {exc}"

    errors: list[str] = []
    entries = data["entries"]
    for entry_id, entry in entries.items():
        if not isinstance(entry, dict):
            errors.append(f"{entry_id}: entry must be an object")
            continue
        errors.extend(_validate_entry(entry_id, entry))

    if errors:
        return 2, "DRIFT: " + "; ".join(errors)

    n = len(entries)
    return 0, (
        f"OK: {n} γ-ledger entries; all CI envelopes, tiers, statuses, and required keys valid."
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    _ = argv
    code, message = run_check()
    stream = sys.stdout if code == 0 else sys.stderr
    print(message, file=stream)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
