"""Claim Surface Reconciliation Gate — fail-closed audit of repository claim coherence.

Phase 1 of the NeoSynaptex research-engineering protocol. This tool does
**not** modify the ledger, the README, or any claim-bearing surface; it
only **detects contradictions** between them. Phase 2 (Ledger Evidence
Hardening) acts on the contradictions; this gate exposes them.

Contradiction families detected
-------------------------------

1. **Ledger inconsistency** — an entry carries
   ``status="VALIDATED"`` while lacking one or more of:
   ``data_source.sha256`` (non-null, non-pointer-string),
   ``adapter_code_hash`` (non-null, non-pointer-string),
   ``null_family_status``, ``rerun_command``, ``claim_boundary_ref``.

2. **BN-Syn overclaim** — the ``bnsyn`` ledger entry must NOT be
   ``VALIDATED``: per
   ``docs/claim_boundaries/BN_SYN_LOCAL_STRUCTURAL_EVIDENCE.md`` the
   BN-Syn substrate is ``LOCAL_STRUCTURAL_EVIDENCE_ONLY``.

3. **Mycelium overclaim** — the ``contracts/mycelium_pre_admission.py``
   contract must remain ``BLOCKED_BY_METHOD_DEFINITION``; any other
   public mycelial verdict in the canon is a contradiction.

4. **README forbidden-phrase scan** — ``README.md`` must not contain
   wording that exceeds the §2 forbidden list of
   ``docs/CLAIM_BOUNDARY.md`` (e.g. "γ ≈ 1.0 is a law", "universal",
   "publishable evidential core", etc.).

5. **C-004 overclaim** — Claim row C-004 in
   ``docs/CLAIM_BOUNDARY.md`` must remain ``Layer: Conjectural``.

6. **README badge inflation** — README badges or headlines describing
   substrates as "validated" must reconcile with the empty evidential
   core stated in §5.1 of the claim boundary.

Exit policy
-----------

* Exit ``0`` and write ``RECONCILED`` only when zero contradictions are
  detected.
* Exit ``2`` and write a machine-readable report listing every
  contradiction otherwise. The report does NOT auto-promote, downgrade,
  or modify any claim — it only names the conflicts.

Output
------

* Stdout: a JSON document with the full contradiction list.
* If ``--report PATH`` is given: write a markdown report describing the
  contradictions in human-readable form for review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "Violation",
    "collect_violations",
    "build_report",
    "main",
]


_REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent.parent

# Forbidden README phrases. Sourced from docs/CLAIM_BOUNDARY.md §2.
# Stored as (regex, code, message) triples; case-insensitive.
_README_FORBIDDEN_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (r"\bγ\s*≈\s*1\.0\s+is\s+a\s+law\b", "FORBIDDEN_LAW", "γ ≈ 1.0 framed as a law"),
    (
        r"\buniversal\s+(?:law|exponent|invariant)\b",
        "FORBIDDEN_UNIVERSAL",
        "universal-law / universal-exponent framing",
    ),
    (
        r"\bsubstrate.?independent\s+law\b",
        "FORBIDDEN_SUBSTRATE_INDEPENDENT",
        "substrate-independent law framing",
    ),
    (
        r"\bconfirmed\s+cross.?substrate\s+invariant\b",
        "FORBIDDEN_CONFIRMED_INVARIANT",
        "confirmed cross-substrate invariant framing",
    ),
    (
        r"\bpublishable\s+evidential\s+core\b",
        "FORBIDDEN_PUBLISHABLE_CORE",
        "publishable evidential core (forbidden before Phase IX gate closes)",
    ),
    (
        r"\bγ\s*=\s*1\s+everywhere\b",
        "FORBIDDEN_GAMMA_EVERYWHERE",
        "γ = 1 everywhere framing",
    ),
    (
        r"\bproves\s+universality\b",
        "FORBIDDEN_PROVES_UNIVERSALITY",
        "proves-universality framing",
    ),
    (
        r"\bglobal\s+theorem\b",
        "FORBIDDEN_GLOBAL_THEOREM",
        "global-theorem framing",
    ),
)

# Conservative pointer-string heuristic: a hash field is "non-real" if it is
# null, an empty string, or a free-text "see ..." pointer rather than a
# concrete sha256-style 64-hex value.
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _is_real_hash(value: object) -> bool:
    """Return True iff ``value`` looks like a real sha256 string."""
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


@dataclass(frozen=True, slots=True)
class Violation:
    """A single contradiction in the canon surface."""

    code: str
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM"
    surface: str  # path or pseudo-path describing the source
    locator: str  # e.g. "entries.bnsyn.status" or "README.md:line=82"
    message: str
    proposed_action: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


def _check_ledger_entry(
    substrate_id: str,
    entry: dict[str, Any],
) -> list[Violation]:
    """Check a single ledger entry against the VALIDATED-requires-evidence rules.

    Phase 2 schema (v2.0.0): canonical fields are flat ``data_sha256``,
    ``adapter_code_hash``, ``null_family_status``, ``rerun_command``,
    ``claim_boundary_ref``. Legacy ``data_source.sha256`` is a fallback.
    """
    out: list[Violation] = []
    status = entry.get("status")
    if status not in {"VALIDATED", "VALIDATED_SUBSTRATE_EVIDENCE"}:
        return out

    ledger_path = "evidence/gamma_ledger.json"
    base_locator = f"entries.{substrate_id}"

    sha = entry.get("data_sha256")
    if not _is_real_hash(sha):
        legacy = entry.get("data_source") or {}
        if isinstance(legacy, dict):
            sha = legacy.get("sha256")
    if not _is_real_hash(sha):
        out.append(
            Violation(
                code="VALIDATED_WITHOUT_DATA_SHA256",
                severity="CRITICAL",
                surface=ledger_path,
                locator=f"{base_locator}.data_sha256",
                message=(
                    f"substrate {substrate_id!r} carries status=VALIDATED but its "
                    "data_sha256 is missing, null, or a free-text pointer; "
                    "VALIDATED requires a concrete data hash per CLAIM_BOUNDARY.md §5.1."
                ),
                proposed_action=(
                    "Either populate data_sha256 with a real 64-hex sha256 "
                    "or downgrade the substrate to "
                    "LOCAL_STRUCTURAL_EVIDENCE_ONLY / EVIDENCE_CANDIDATE."
                ),
                evidence={"observed": sha},
            )
        )

    adapter = entry.get("adapter_code_hash")
    if not _is_real_hash(adapter):
        out.append(
            Violation(
                code="VALIDATED_WITHOUT_ADAPTER_CODE_HASH",
                severity="CRITICAL",
                surface=ledger_path,
                locator=f"{base_locator}.adapter_code_hash",
                message=(
                    f"substrate {substrate_id!r} carries status=VALIDATED but its "
                    "adapter_code_hash is missing or non-canonical; VALIDATED requires "
                    "a deterministic pipeline hash."
                ),
                proposed_action=(
                    "Either populate adapter_code_hash with a real 64-hex sha256 of the "
                    "frozen adapter source, or downgrade the substrate."
                ),
                evidence={"observed": adapter},
            )
        )

    for required_field, code in (
        ("null_family_status", "VALIDATED_WITHOUT_NULL_FAMILY_STATUS"),
        ("rerun_command", "VALIDATED_WITHOUT_RERUN_COMMAND"),
        ("claim_boundary_ref", "VALIDATED_WITHOUT_CLAIM_BOUNDARY_REF"),
    ):
        if required_field not in entry or entry.get(required_field) in (None, ""):
            out.append(
                Violation(
                    code=code,
                    severity="HIGH",
                    surface=ledger_path,
                    locator=f"{base_locator}.{required_field}",
                    message=(
                        f"substrate {substrate_id!r} carries status=VALIDATED but lacks "
                        f"a {required_field!r} field; required by Phase 2 schema."
                    ),
                    proposed_action=(
                        f"Add {required_field!r} to the ledger entry "
                        f"or downgrade {substrate_id} until the field is supplied."
                    ),
                )
            )

    return out


def _check_downgrade_completeness(
    substrate_id: str,
    entry: dict[str, Any],
) -> list[Violation]:
    """Non-VALIDATED entries (other than NO_ADMISSIBLE_CLAIM) need a downgrade_reason."""
    out: list[Violation] = []
    status = entry.get("status")
    if status in {"VALIDATED", "VALIDATED_SUBSTRATE_EVIDENCE", "NO_ADMISSIBLE_CLAIM"}:
        return out
    if not entry.get("downgrade_reason"):
        out.append(
            Violation(
                code="DOWNGRADE_WITHOUT_REASON",
                severity="HIGH",
                surface="evidence/gamma_ledger.json",
                locator=f"entries.{substrate_id}.downgrade_reason",
                message=(
                    f"substrate {substrate_id!r} has status={status!r} (below VALIDATED) "
                    "but no downgrade_reason field; non-VALIDATED entries must explain "
                    "why they sit below VALIDATED."
                ),
                proposed_action=(
                    "Populate downgrade_reason with a code from "
                    "evidence/ledger_schema.ALLOWED_DOWNGRADE_REASONS."
                ),
            )
        )
    return out


def _check_bnsyn_ledger(entries: dict[str, Any]) -> list[Violation]:
    """BN-Syn ledger entry must not exceed LOCAL_STRUCTURAL_EVIDENCE_ONLY."""
    out: list[Violation] = []
    bnsyn_keys = [k for k in entries if "bn" in k.lower() and "syn" in k.lower()]
    for key in bnsyn_keys:
        entry = entries[key]
        if entry.get("status") in {"VALIDATED", "VALIDATED_SUBSTRATE_EVIDENCE"}:
            out.append(
                Violation(
                    code="BNSYN_OVERCLAIM",
                    severity="CRITICAL",
                    surface="evidence/gamma_ledger.json",
                    locator=f"entries.{key}.status",
                    message=(
                        f"BN-Syn entry {key!r} has status={entry.get('status')!r}, but "
                        "docs/claim_boundaries/BN_SYN_LOCAL_STRUCTURAL_EVIDENCE.md "
                        "constrains BN-Syn to LOCAL_STRUCTURAL_EVIDENCE_ONLY until a "
                        "γ-side pass is supplied externally (κ ≠ γ)."
                    ),
                    proposed_action=(
                        f"Downgrade {key} to LOCAL_STRUCTURAL_EVIDENCE_ONLY in Phase 2 "
                        "and add an explicit downgrade_reason."
                    ),
                    evidence={"observed_status": entry.get("status")},
                )
            )
    return out


def _check_readme_forbidden(readme_text: str) -> list[Violation]:
    """Scan README for forbidden phrases per CLAIM_BOUNDARY §2."""
    out: list[Violation] = []
    for pattern, code, msg in _README_FORBIDDEN_PATTERNS:
        for m in re.finditer(pattern, readme_text, flags=re.IGNORECASE):
            line_no = readme_text[: m.start()].count("\n") + 1
            out.append(
                Violation(
                    code=code,
                    severity="HIGH",
                    surface="README.md",
                    locator=f"README.md:line={line_no}",
                    message=f"forbidden phrase per CLAIM_BOUNDARY.md §2: {msg}",
                    proposed_action=(
                        "Reword to a §3 allowed framing (regime marker / "
                        "cross-substrate convergence / falsification)."
                    ),
                    evidence={"matched_text": m.group(0)},
                )
            )
    return out


def _check_readme_validated_count(readme_text: str) -> list[Violation]:
    """Cross-check README 'validated substrates' count against §5.1 empty core.

    docs/CLAIM_BOUNDARY.md §5.1 explicitly states the evidential core is
    empty: no substrate has closed all six gates yet. README phrases of
    the form ``N validated substrates`` are therefore inconsistent until
    each named substrate has closed §5.1 (data hash + replication +
    surrogate non-reproduction + external rerun).
    """
    out: list[Violation] = []
    pattern = re.compile(r"(?P<n>\d+)\s+validated\s+substrate", flags=re.IGNORECASE)
    for m in pattern.finditer(readme_text):
        line_no = readme_text[: m.start()].count("\n") + 1
        out.append(
            Violation(
                code="README_VALIDATED_COUNT_INCONSISTENT_WITH_EMPTY_CORE",
                severity="HIGH",
                surface="README.md",
                locator=f"README.md:line={line_no}",
                message=(
                    "README asserts validated-substrate count, but "
                    "docs/CLAIM_BOUNDARY.md §5.1 declares the evidential core empty "
                    "(no substrate has closed all six §5.1 gates)."
                ),
                proposed_action=(
                    "Either reword to 'measured' / 'empirical' wording or close "
                    "the §5.1 gates per substrate."
                ),
                evidence={"matched_text": m.group(0)},
            )
        )
    return out


def _check_c004_layer(claim_boundary_text: str) -> list[Violation]:
    """C-004 row in CLAIM_BOUNDARY must remain ``Conjectural``."""
    out: list[Violation] = []
    # Locate the C-004 block. Use a non-greedy match up to the next claim row.
    m = re.search(
        r"###\s+Claim\s+C-004[^\n]*\n(?P<body>.*?)(?=\n###\s+Claim|\n##\s+\d|$)",
        claim_boundary_text,
        flags=re.DOTALL,
    )
    if m is None:
        out.append(
            Violation(
                code="C004_MISSING",
                severity="CRITICAL",
                surface="docs/CLAIM_BOUNDARY.md",
                locator="C-004 row",
                message="C-004 claim row is missing from CLAIM_BOUNDARY.md",
                proposed_action=(
                    "Restore C-004 row as 'Conjectural' per canon-closure protocol v1.0."
                ),
            )
        )
        return out
    body = m.group("body")
    layer_match = re.search(r"\*\*Layer:\*\*\s*(\w+)", body)
    layer = layer_match.group(1) if layer_match else None
    if layer != "Conjectural":
        out.append(
            Violation(
                code="C004_LAYER_OVERCLAIM",
                severity="CRITICAL",
                surface="docs/CLAIM_BOUNDARY.md",
                locator="C-004.Layer",
                message=(f"C-004 must be Layer=Conjectural; observed {layer!r}."),
                proposed_action="Restore C-004 layer to Conjectural.",
                evidence={"observed_layer": layer},
            )
        )
    return out


def _check_mycelium_contract(repo_root: Path) -> list[Violation]:
    """Mycelium pre-admission contract must remain BLOCKED_BY_METHOD_DEFINITION."""
    out: list[Violation] = []
    contract_path = repo_root / "contracts" / "mycelium_pre_admission.py"
    if not contract_path.is_file():
        out.append(
            Violation(
                code="MYCELIUM_CONTRACT_MISSING",
                severity="CRITICAL",
                surface=str(contract_path.relative_to(repo_root)),
                locator="file",
                message="mycelium_pre_admission contract is missing.",
                proposed_action="Restore contract per #154.",
            )
        )
        return out
    text = contract_path.read_text(encoding="utf-8")
    if "BLOCKED_BY_METHOD_DEFINITION" not in text:
        out.append(
            Violation(
                code="MYCELIUM_CONTRACT_OVERCLAIM",
                severity="CRITICAL",
                surface="contracts/mycelium_pre_admission.py",
                locator="module",
                message=(
                    "mycelium_pre_admission contract no longer contains the "
                    "BLOCKED_BY_METHOD_DEFINITION reason; Gate 0 invariant violated."
                ),
                proposed_action="Restore the canonical Gate 0 verdict tuple.",
            )
        )
    if "VALIDATED_SUBSTRATE_EVIDENCE" in text and "non_claims" not in text:
        out.append(
            Violation(
                code="MYCELIUM_CONTRACT_PROMOTES_VALIDATED",
                severity="CRITICAL",
                surface="contracts/mycelium_pre_admission.py",
                locator="module",
                message=(
                    "mycelium_pre_admission contract references "
                    "VALIDATED_SUBSTRATE_EVIDENCE outside a non-claims context."
                ),
                proposed_action="Audit contract for accidental promotion path.",
            )
        )
    return out


def collect_violations(repo_root: Path) -> list[Violation]:
    """Run every reconciliation check and return the union of violations."""
    violations: list[Violation] = []

    ledger_path = repo_root / "evidence" / "gamma_ledger.json"
    if not ledger_path.is_file():
        violations.append(
            Violation(
                code="LEDGER_MISSING",
                severity="CRITICAL",
                surface="evidence/gamma_ledger.json",
                locator="file",
                message="evidence/gamma_ledger.json is missing.",
                proposed_action="Restore the ledger.",
            )
        )
    else:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        entries = ledger.get("entries") or {}
        for substrate_id, entry in entries.items():
            if isinstance(entry, dict):
                violations.extend(_check_ledger_entry(substrate_id, entry))
                violations.extend(_check_downgrade_completeness(substrate_id, entry))
        violations.extend(_check_bnsyn_ledger(entries))

    readme_path = repo_root / "README.md"
    if readme_path.is_file():
        readme_text = readme_path.read_text(encoding="utf-8")
        violations.extend(_check_readme_forbidden(readme_text))
        violations.extend(_check_readme_validated_count(readme_text))

    cb_path = repo_root / "docs" / "CLAIM_BOUNDARY.md"
    if cb_path.is_file():
        violations.extend(_check_c004_layer(cb_path.read_text(encoding="utf-8")))

    violations.extend(_check_mycelium_contract(repo_root))

    return violations


def build_report(violations: list[Violation]) -> str:
    """Render violations as a markdown report."""
    if not violations:
        return "# Claim Surface Reconciliation\n\nRECONCILED. No contradictions detected.\n"
    lines: list[str] = [
        "# Claim Surface Reconciliation Report",
        "",
        f"Found **{len(violations)}** contradiction(s).",
        "",
        "| # | Severity | Code | Surface | Locator | Message |",
        "|---|----------|------|---------|---------|---------|",
    ]
    for i, v in enumerate(violations, 1):
        msg = v.message.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {i} | {v.severity} | `{v.code}` | `{v.surface}` | `{v.locator}` | {msg} |")
    lines.extend(["", "## Proposed actions", ""])
    for i, v in enumerate(violations, 1):
        if v.proposed_action:
            lines.append(f"{i}. **{v.code}** — {v.proposed_action}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit NeoSynaptex claim surfaces for contradictions. Exits 0 only if RECONCILED."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT_DEFAULT,
        help="Path to the repository root (default: detected from this file).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional markdown report output path.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional machine-readable JSON output path.",
    )
    args = parser.parse_args(argv)

    violations = collect_violations(args.repo_root)
    payload = {
        "schema_version": "1.0.0",
        "verdict": "RECONCILED" if not violations else "NOT_RECONCILED",
        "violation_count": len(violations),
        "violations": [asdict(v) for v in violations],
    }
    raw = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(raw, encoding="utf-8")
    else:
        sys.stdout.write(raw)

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(build_report(violations), encoding="utf-8")

    return 0 if not violations else 2


if __name__ == "__main__":
    raise SystemExit(main())
