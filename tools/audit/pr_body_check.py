"""Validate that a pull-request body contains a well-formed ``claim_status`` block.

Thin companion to ``tools/audit/claim_status_applied.py``: that tool
measures whether the taxonomy is **applied in the git log**; this tool
enforces that any **incoming PR** carries an explicit label. Together
they close the adoption loop — detection + enforcement — for the
SYSTEM_PROTOCOL v1.1 kill-signal ``taxonomy_disuse``.

Contract
--------

* **Input.** A single text blob: either a file path via ``argv[1]`` or
  stdin when no argument is given.
* **Success.** Exit 0 when the blob contains at least one line matching
  ``^claim_status: <label>$`` (case-insensitive, whitespace-tolerant,
  optional backticks / quotes) where ``<label>`` is one of
  ``CANONICAL_LABELS`` from ``tools.audit.claim_status_applied``.
* **Dependabot exception.** Exit 0 for narrowly-scoped dependency-only
  PRs opened by ``dependabot[bot]`` when the title, head ref, and body
  all match Dependabot's machine-generated dependency-update shape.
  These PRs are treated as ``claim_status: measured`` because the claim
  is only a dependency metadata update, not a scientific or product
  claim. Human-authored PRs never receive this exception. An explicit
  non-canonical ``claim_status`` line is always rejected before this
  exception is considered.
* **Failure.** Exit 2 in either of two cases:

  1. No ``claim_status:`` line is present — the PR has not applied the
     taxonomy at all.
  2. A ``claim_status:`` line is present but its value is outside the
     canonical taxonomy — the PR tried to apply the taxonomy but named
     an unknown label.

* **Scope.** This tool checks **presence and syntactic validity**, not
  semantic correctness. Whether the chosen label is the right one for
  the change is not machine-checkable; that is the reviewer's job.
  Semantic correctness is explicitly NOT in the contract of this tool.

Labels are imported at runtime from
``tools.audit.claim_status_applied.CANONICAL_LABELS`` so the taxonomy
has one single source of truth.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass

from tools.audit.claim_status_applied import CANONICAL_LABELS

__all__ = ["ValidationContext", "main", "validate"]

_LABEL_ALT = "|".join(re.escape(label) for label in CANONICAL_LABELS)
DEPENDABOT_ACTOR = "dependabot[bot]"

# Strict line-anchored pattern for the PR-body check. Matches any of:
#
#   claim_status: measured
#   Claim_Status: derived
#   claim status: hypothesized
#   claim_status: `unverified analogy`
#   `claim_status: derived`
#   claim_status: "falsified"
#
# but not a prose mention like "we measured the gamma exponent".
_PR_BODY_PATTERN = re.compile(
    rf"(?mi)^\s*`?\s*claim[_\s]*status\s*:\s*[`'\"]?({_LABEL_ALT})[`'\"]?\s*`?\s*$"
)

# Weaker pattern — "there is a claim_status line of SOME kind" — used only
# to distinguish "no block at all" from "block with an unknown label",
# so the error message can point the reviewer at the right failure mode.
_PR_BODY_ANY_LABEL_LINE = re.compile(
    r"(?mi)^\s*`?\s*claim[_\s]*status\s*:\s*[`'\"]?([^`'\"\s][^`'\"]*?)[`'\"]?\s*`?\s*$"
)

_DEPENDABOT_TITLE_PATTERN = re.compile(
    r"(?i)^(?:deps|build|ci)(?:\([^)]*\))?:\s+bump\s+.+\s+(?:from\s+.+\s+to\s+.+|with\s+\d+\s+updates?)"
)
_DEPENDABOT_BODY_PATTERN = re.compile(
    r"(?is)(?:\bBumps\b.+\bfrom\b.+\bto\b.+\bDependabot\b|"
    r"\bBumps the .+ group\b.+\bUpdates\b.+\bfrom\b.+\bto\b.+\bDependabot\b)"
)
_DEPENDABOT_HEAD_PATTERN = re.compile(r"(?i)^dependabot/")


@dataclass(frozen=True)
class ValidationContext:
    """Optional GitHub event context for narrow machine-generated exceptions."""

    actor: str = ""
    title: str = ""
    head_ref: str = ""


def _is_dependabot_dependency_pr(text: str, context: ValidationContext | None) -> bool:
    """Return True only for machine-generated dependency-only Dependabot PRs.

    The exception is intentionally conjunctive. It requires the GitHub actor,
    branch namespace, PR title, and body shape to agree. This avoids turning the
    governance gate into a broad "bot == pass" bypass, which would be a charming
    way to reintroduce the exact security theater this repository is allergic to.
    """

    if context is None:
        return False
    if context.actor != DEPENDABOT_ACTOR:
        return False
    if not _DEPENDABOT_HEAD_PATTERN.search(context.head_ref):
        return False
    if not _DEPENDABOT_TITLE_PATTERN.search(context.title):
        return False
    return bool(_DEPENDABOT_BODY_PATTERN.search(text))


def _unknown_claim_status_reason(text: str) -> str | None:
    any_lines = [m.group(1).strip() for m in _PR_BODY_ANY_LABEL_LINE.finditer(text)]
    if not any_lines:
        return None
    unknown = sorted({v.lower() for v in any_lines})
    return (
        "claim_status block is present but its label(s) are outside the "
        "canonical taxonomy: "
        + ", ".join(repr(u) for u in unknown)
        + ". Valid labels: "
        + ", ".join(CANONICAL_LABELS)
        + ". See docs/SYSTEM_PROTOCOL.md §Barrier rule (item 4)."
    )


def validate(text: str, context: ValidationContext | None = None) -> tuple[bool, str]:
    """Return ``(ok, reason)`` for a PR body text blob.

    ``reason`` is always a single line suitable for a CI log and, on
    failure, includes a pointer at ``docs/SYSTEM_PROTOCOL.md §Barrier rule``.
    """

    canonical_hits = [m.group(1).lower() for m in _PR_BODY_PATTERN.finditer(text)]
    if canonical_hits:
        return True, (
            "claim_status present with canonical label(s): "
            + ", ".join(sorted(set(canonical_hits)))
        )

    unknown_reason = _unknown_claim_status_reason(text)
    if unknown_reason is not None:
        return False, unknown_reason

    if _is_dependabot_dependency_pr(text, context):
        return True, (
            "dependency-only Dependabot PR accepted as claim_status: measured "
            "under the narrow machine-generated dependency-update exception"
        )

    return False, (
        "PR body is missing a claim_status block. "
        "Add a line of the form `claim_status: <label>` where <label> is "
        "one of: "
        + ", ".join(CANONICAL_LABELS)
        + ". See docs/SYSTEM_PROTOCOL.md §Barrier rule (item 4) and "
        "`.github/PULL_REQUEST_TEMPLATE.md`."
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="-", help="PR body file path, or '-' for stdin.")
    parser.add_argument("--actor", default="", help="GitHub actor from github.actor.")
    parser.add_argument("--title", default="", help="Pull request title from the GitHub event.")
    parser.add_argument("--head-ref", default="", help="Pull request head ref from the GitHub event.")
    return parser.parse_args(argv)


def _read_input(path: str) -> str:
    if path != "-":
        return pathlib.Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def _emit_safely(event_type: str, **kwargs: object) -> None:
    """Best-effort telemetry emit; never raises, never blocks the check.

    Observability is a side channel. If ``tools.telemetry`` is missing
    (minimal CI image) or the sink is broken, the audit verdict still
    stands. This matches ``telemetry_spine_spec.md §8``.
    """

    try:
        from tools.telemetry.emit import emit_event

        emit_event(event_type, "audit.pr_body_check", **kwargs)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — silent-drop per spec §8
        return


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    context = ValidationContext(actor=args.actor, title=args.title, head_ref=args.head_ref)

    try:
        from tools.telemetry.emit import span
    except ImportError:
        span = None  # type: ignore[assignment]

    if span is None:
        text = _read_input(args.path)
        ok, reason = validate(text, context)
        stream = sys.stdout if ok else sys.stderr
        print(reason, file=stream)
        return 0 if ok else 2

    with span("audit.pr_body_check.run", "audit.pr_body_check"):
        text = _read_input(args.path)
        ok, reason = validate(text, context)
        stream = sys.stdout if ok else sys.stderr
        print(reason, file=stream)
        _emit_safely(
            "audit.pr_body_check.verdict",
            payload={"reason_head": reason[:200]},
            outcome="ok" if ok else "fail",
        )
    return 0 if ok else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
