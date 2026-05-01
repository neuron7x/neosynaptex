"""M-bridge claim status lint — block claim drift after PR #171.

Signal contract
---------------

`contracts/M_BRIDGE_CLAIM_STATUS.yaml` is the authoritative registry for
the M-invariant bridge claim family. After the `INVALID_HWI` verdict on
PR #171, several claims must NOT appear positively in repository
documentation:

  - "M is universal"
  - "Turing Gap closed"
  - "MFN and BN-Syn share M invariant"
  - "M=1.0 proves convergence"
  - "INVALID_HWI supports the bridge"
  - "MFN BN-Syn bridge confirmed"

This tool walks the docs tree and rejects any positive assertion of
those strings. A verbatim quote inside an explicit disavowal context
(``forbidden``, ``rejected``, ``disavowed``, ``must not``, ``do not
claim``, ``anti-pattern`` on the same line, or under a heading whose
text contains any of those markers) is allowed.

Scope
-----

Structural / lexical only. Does NOT:

* Parse natural language for paraphrased forbidden claims.
* Verify that the registry YAML is logically self-consistent.
* Check git history for rolled-back claims.

Semantic correctness of every claim assertion remains the reviewer's
job per `docs/ADVERSARIAL_CONTROLS.md`.

Exit codes
----------
0 — registry healthy and no positive forbidden claim found.
2 — at least one violation; details printed to stderr.
3 — registry file missing, malformed, or missing required keys.
"""

from __future__ import annotations

import pathlib
import re
import sys
from dataclasses import dataclass

import yaml

REGISTRY_PATH = pathlib.Path("contracts/M_BRIDGE_CLAIM_STATUS.yaml")
DOCS_ROOT = pathlib.Path("docs")

REQUIRED_REGISTRY_KEYS: tuple[str, ...] = (
    "claim_family",
    "current_status",
    "last_experiment",
    "allowed_claims",
    "forbidden_claims",
    "next_candidate_paths",
    "forbidden_post_hoc_actions",
)

DISAVOWAL_MARKERS: tuple[str, ...] = (
    "forbidden",
    "rejected",
    "disavowed",
    "must not",
    "do not claim",
    "anti-pattern",
    "anti pattern",
)

REQUIRED_PR_REFERENCE = "171"


@dataclass(frozen=True)
class Violation:
    path: pathlib.Path
    line_number: int
    line: str
    forbidden_claim: str


@dataclass(frozen=True)
class RegistryError:
    message: str


def _load_registry() -> dict[str, object] | RegistryError:
    if not REGISTRY_PATH.exists():
        return RegistryError(f"registry file missing: {REGISTRY_PATH}")
    try:
        data = yaml.safe_load(REGISTRY_PATH.read_text())
    except yaml.YAMLError as exc:
        return RegistryError(f"registry YAML parse error: {exc}")
    if not isinstance(data, dict):
        return RegistryError("registry top-level is not a mapping")
    return data


def _check_registry_shape(data: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_REGISTRY_KEYS:
        if key not in data:
            errors.append(f"registry missing required key: {key}")
    if data.get("claim_family") != "m_invariant_bridge":
        errors.append("registry claim_family must equal 'm_invariant_bridge'")
    if data.get("current_status") != "OPEN_NARROWED":
        errors.append(
            f"registry current_status must remain OPEN_NARROWED until a "
            f"pre-registered passing contract exists; got {data.get('current_status')!r}"
        )
    last = data.get("last_experiment")
    if not isinstance(last, dict) or str(last.get("pr")) != REQUIRED_PR_REFERENCE:
        errors.append(f"registry last_experiment.pr must reference PR #{REQUIRED_PR_REFERENCE}")
    if isinstance(last, dict) and last.get("verdict") != "INVALID_HWI":
        errors.append("registry last_experiment.verdict must be INVALID_HWI")
    forbidden = data.get("forbidden_claims")
    if not isinstance(forbidden, list) or not forbidden:
        errors.append("registry forbidden_claims must be a non-empty list")
    return errors


def _line_in_disavowal_context(lines: list[str], idx: int, heading_stack: list[str]) -> bool:
    """A claim quote is allowed if its line OR an enclosing heading
    contains a disavowal marker (case-insensitive)."""
    haystacks: list[str] = [lines[idx].lower(), *(h.lower() for h in heading_stack)]
    return any(marker in h for marker in DISAVOWAL_MARKERS for h in haystacks)


def _walk_md(path: pathlib.Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def _scan_file(path: pathlib.Path, forbidden: list[str]) -> list[Violation]:
    lines = _walk_md(path)
    heading_stack: list[str] = []
    found: list[Violation] = []
    for idx, raw in enumerate(lines):
        m = _HEADING_RE.match(raw)
        if m:
            level = len(m.group(1))
            text = m.group(2)
            heading_stack = heading_stack[: level - 1] + [text]
            continue
        for claim in forbidden:
            if claim.lower() in raw.lower():
                if _line_in_disavowal_context(lines, idx, heading_stack):
                    continue
                found.append(
                    Violation(
                        path=path,
                        line_number=idx + 1,
                        line=raw.rstrip(),
                        forbidden_claim=claim,
                    )
                )
    return found


def scan_docs(forbidden_claims: list[str]) -> list[Violation]:
    violations: list[Violation] = []
    if not DOCS_ROOT.exists():
        return violations
    for md in sorted(DOCS_ROOT.rglob("*.md")):
        violations.extend(_scan_file(md, forbidden_claims))
    return violations


def main(argv: list[str] | None = None) -> int:
    _ = argv
    reg = _load_registry()
    if isinstance(reg, RegistryError):
        print(f"registry error: {reg.message}", file=sys.stderr)
        return 3

    shape_errors = _check_registry_shape(reg)
    if shape_errors:
        for err in shape_errors:
            print(f"registry error: {err}", file=sys.stderr)
        return 3

    forbidden = list(reg.get("forbidden_claims") or [])
    violations = scan_docs([str(c) for c in forbidden])
    if violations:
        print(
            f"M-bridge claim lint: {len(violations)} positive forbidden claim(s) found:",
            file=sys.stderr,
        )
        for v in violations:
            print(
                f"  {v.path}:{v.line_number}: {v.forbidden_claim!r}\n    {v.line}",
                file=sys.stderr,
            )
        return 2

    last_pr = (reg.get("last_experiment") or {}).get("pr")  # type: ignore[union-attr]
    status = reg.get("current_status")
    print(
        f"M-bridge claim lint: OK ({len(forbidden)} forbidden claims checked, "
        f"registry status={status!r}, last PR=#{last_pr})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
