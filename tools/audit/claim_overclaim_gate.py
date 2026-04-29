"""Phase 2.1 P10 mechanical enforcement — fail if a PR claims more than the code enforces.

This gate scans:

* the PR title (``GH_PR_TITLE``),
* the PR body (``GH_PR_BODY``),
* every source file under ``core/``, ``contracts/``, ``evidence/``,
  ``tools/``, ``analysis/``, ``formal/`` that ships in this repo,

for **forbidden overclaim phrases** that the codebase does not actually
implement at this stage.

A forbidden phrase is admitted ONLY if it appears in an explicit
disavowal context: the line containing the phrase must also contain at
least one disavowal word (``not``, ``disavow``, ``forbidden``,
``rejected``, ``downgraded``, ``does not prove``, ``not yet``,
``not implemented``).

Body-license rule (PR title/body only)
--------------------------------------

A forbidden phrase in the PR title is also admitted when the PR body
explicitly disavows the *same* phrase on a single line (a
*body-licensed* phrase). This handles the case where the PR author's
account cannot edit the title (e.g. fork/READ permission) but the body
makes the disavowal unambiguous, e.g. body says
"this PR is **not** a 'cryptographic evidence chain'". Production
source files (``core/``, ``contracts/``, …) are NEVER body-licensed —
they must self-disavow on the same line.

Forbidden phrases (current list):

* ``cryptographic evidence chain`` — implies signed, attested, fully-bound
  evidence. The Phase 2.1 PR is a *runtime repo-file hash binding gate*,
  not a chain.
* ``hypothesis validated`` — the γ ≈ 1 hypothesis is not validated.
* ``hypothesis ready`` — same.
* ``research proof`` — overclaim; nothing in this repo constitutes a proof.
* ``full evidence verification`` — no entry verifies pipeline_hash or
  result_hash; manifest binding is partial.
* ``validated substrate evidence`` (without quotes around it as a status
  symbol) — the ladder state is FROZEN until the promotion gate exists.

Exit codes
----------

* 0 — every forbidden phrase, where it appears at all, appears in an
  explicit disavowal context.
* 2 — at least one positive use of a forbidden phrase exists somewhere.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Final

__all__ = [
    "DISAVOWAL_TOKENS",
    "FORBIDDEN_PHRASES",
    "find_overclaims",
    "main",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Phrases the codebase must not claim positively at this stage.
FORBIDDEN_PHRASES: Final[tuple[str, ...]] = (
    "cryptographic evidence chain",
    "hypothesis validated",
    "hypothesis ready",
    "research proof",
    "full evidence verification",
    "validated substrate evidence",
)

#: Disavowal tokens that, if co-occurring on the same line as a forbidden
#: phrase, mark the use as an explicit "NOT this" — admitted.
DISAVOWAL_TOKENS: Final[tuple[str, ...]] = (
    "not",
    "disavow",
    "forbidden",
    "rejected",
    "downgraded",
    "frozen",
    "does not",
    "not yet",
    "not implemented",
    "is not",
)

#: Source roots scanned by the gate. Tests are intentionally excluded —
#: tests describe forbidden phrases when proving rejection.
_SOURCE_ROOTS: Final[tuple[str, ...]] = (
    "core",
    "contracts",
    "evidence",
    "tools",
    "analysis",
    "formal",
    ".github/workflows",
)

#: File extensions worth scanning.
_SCAN_EXTS: Final[frozenset[str]] = frozenset({".py", ".md", ".yml", ".yaml", ".json"})

#: Files exempt from the scan because they are the canonical source of
#: the forbidden-phrase list itself. Listing the phrases is required for
#: the gate to function; doing so is not an overclaim.
_EXEMPT_PATHS: Final[frozenset[str]] = frozenset(
    {
        "tools/audit/claim_overclaim_gate.py",
        ".github/workflows/claim_overclaim_gate.yml",
    }
)


def _is_disavowal_context(line: str) -> bool:
    lower = line.lower()
    return any(tok in lower for tok in DISAVOWAL_TOKENS)


def _scan_text(
    label: str,
    text: str,
    licensed_phrases: frozenset[str] = frozenset(),
) -> list[str]:
    """Return list of overclaim violations in ``text``.

    Each entry of the returned list is a human-readable string of the
    form ``"<label>:<line_no>: <forbidden phrase> in: <line>"``.

    ``licensed_phrases`` are forbidden phrases that have been disavowed
    elsewhere in the PR (e.g. body disavowal licensing the title); any
    occurrence of them in this ``text`` is admitted regardless of local
    disavowal context.
    """
    out: list[str] = []
    for n, line in enumerate(text.splitlines(), start=1):
        for phrase in FORBIDDEN_PHRASES:
            if phrase in line.lower():
                if _is_disavowal_context(line):
                    continue
                if phrase in licensed_phrases:
                    continue
                out.append(
                    f"{label}:{n}: forbidden phrase {phrase!r} "
                    f"without disavowal token; line: {line.strip()[:160]}"
                )
    return out


def _body_licensed_phrases(pr_body: str) -> frozenset[str]:
    """Return phrases the PR body explicitly disavows.

    A forbidden phrase is *body-licensed* when it appears in ``pr_body``
    on a line that also carries an explicit disavowal token. This
    licenses the same phrase to appear in the (often less editable) PR
    title — e.g. when the author's account has READ-only permission and
    cannot edit the title, but the body unambiguously states "this PR
    is **not** a cryptographic evidence chain".

    A PR that mentions a forbidden phrase only positively in the body
    licenses nothing — both title and body remain hard-fail.
    """
    if not pr_body:
        return frozenset()
    licensed: set[str] = set()
    for line in pr_body.splitlines():
        if not _is_disavowal_context(line):
            continue
        lower = line.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in lower:
                licensed.add(phrase)
    return frozenset(licensed)


def find_overclaims(repo_root: Path = _REPO_ROOT) -> list[str]:
    """Walk source roots + PR title/body env, return list of violations.

    The PR body is scanned first; any forbidden phrase the body
    explicitly disavows is treated as *body-licensed* and admitted in
    the PR title. Production source files are scanned line-by-line and
    are NOT body-licensed — production code must self-disavow on the
    same line.
    """
    violations: list[str] = []

    pr_body = os.environ.get("GH_PR_BODY", "")
    licensed = _body_licensed_phrases(pr_body)

    pr_title = os.environ.get("GH_PR_TITLE", "")
    if pr_title:
        violations.extend(_scan_text("PR_TITLE", pr_title, licensed_phrases=licensed))

    if pr_body:
        violations.extend(_scan_text("PR_BODY", pr_body))

    for root_name in _SOURCE_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in _SCAN_EXTS:
                continue
            rel = path.relative_to(repo_root)
            if str(rel).replace("\\", "/") in _EXEMPT_PATHS:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            violations.extend(_scan_text(str(rel), text))

    return violations


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT), type=Path)
    args = parser.parse_args(argv)
    violations = find_overclaims(args.repo_root.resolve())
    if violations:
        print(
            f"OVERCLAIM: {len(violations)} forbidden-phrase use(s) without disavowal:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 2
    print(
        f"OK: scanned {len(_SOURCE_ROOTS)} source roots + PR_TITLE/BODY env; "
        f"{len(FORBIDDEN_PHRASES)} forbidden phrase(s) tracked; "
        "every match is in an explicit disavowal context."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
