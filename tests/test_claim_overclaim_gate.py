"""Tests for tools.audit.claim_overclaim_gate (Phase 2.1 P10 mechanical).

Numbered tests:
1.  Real repository (no PR env) passes the gate — every match is
    inside an explicit disavowal context.
2.  PR_TITLE containing "cryptographic evidence chain" without
    disavowal → REJECTED.
3.  PR_TITLE with the phrase in a disavowal context (``not``) →
    ADMITTED.
4.  PR_BODY with a forbidden phrase without disavowal → REJECTED.
5.  All FORBIDDEN_PHRASES are tracked.
6.  All DISAVOWAL_TOKENS are non-empty strings.
7.  ``find_overclaims`` exempts ``tools/audit/claim_overclaim_gate.py``
    so the canonical phrase list is not self-flagged.
8.  Adding a forbidden phrase to a tmp source file under one of the
    scanned roots is detected.
9.  Body-license: PR title carries a forbidden phrase, PR body
    explicitly disavows the same phrase → title is ADMITTED.
10. Body-license is phrase-scoped: an unrelated body disavowal does
    NOT license a different forbidden phrase in the title.
11. Body that mentions a forbidden phrase positively (no disavowal
    token on the line) does NOT license the title.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.audit.claim_overclaim_gate import (
    DISAVOWAL_TOKENS,
    FORBIDDEN_PHRASES,
    find_overclaims,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_PR_TITLE", raising=False)
    monkeypatch.delenv("GH_PR_BODY", raising=False)


# 1
def test_real_repository_passes() -> None:
    violations = find_overclaims(_REPO_ROOT)
    assert violations == [], f"production code overclaim: {violations}"


# 2
def test_pr_title_overclaim_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "GH_PR_TITLE",
        "feat(evidence): Phase 2.1 — runtime hash binding + cryptographic evidence chain",
    )
    v = find_overclaims(_REPO_ROOT)
    assert any("PR_TITLE" in s and "cryptographic evidence chain" in s for s in v)


# 3
def test_pr_title_with_disavowal_admitted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "GH_PR_TITLE",
        'docs: explain why this is NOT a "cryptographic evidence chain"',
    )
    v = find_overclaims(_REPO_ROOT)
    assert all("PR_TITLE" not in s for s in v), v


# 4
def test_pr_body_overclaim_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "GH_PR_BODY",
        "## Summary\n\nWe ship a full evidence verification system in this PR.\n",
    )
    v = find_overclaims(_REPO_ROOT)
    assert any("PR_BODY" in s and "full evidence verification" in s for s in v)


# 5
@pytest.mark.parametrize("phrase", FORBIDDEN_PHRASES)
def test_forbidden_phrase_set_membership(phrase: str) -> None:
    assert isinstance(phrase, str) and phrase
    # Must be lowercase to match _scan_text's lower() on the line
    assert phrase == phrase.lower(), f"FORBIDDEN_PHRASES entries must be lowercase; got {phrase!r}"


# 6
@pytest.mark.parametrize("token", DISAVOWAL_TOKENS)
def test_disavowal_tokens_nonempty(token: str) -> None:
    assert isinstance(token, str) and token


# 7
def test_gate_self_exempt() -> None:
    """The gate's own source file is exempt — it must not self-flag."""
    violations = find_overclaims(_REPO_ROOT)
    assert all("tools/audit/claim_overclaim_gate.py" not in v for v in violations), violations


# 8
def test_temp_source_file_overclaim_detected(tmp_path: Path) -> None:
    """A new file under a scanned root with a forbidden phrase is flagged."""
    fake_repo = tmp_path / "repo"
    (fake_repo / "tools" / "audit").mkdir(parents=True)
    bad = fake_repo / "tools" / "audit" / "fake.py"
    bad.write_text(
        '"""This module ships a cryptographic evidence chain."""\n',
        encoding="utf-8",
    )
    v = find_overclaims(fake_repo)
    assert any("fake.py" in s and "cryptographic evidence chain" in s for s in v)


def test_temp_source_file_disavowal_admitted(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    (fake_repo / "tools" / "audit").mkdir(parents=True)
    ok = fake_repo / "tools" / "audit" / "fake.py"
    ok.write_text(
        '"""This module is NOT a cryptographic evidence chain."""\n',
        encoding="utf-8",
    )
    v = find_overclaims(fake_repo)
    assert v == []


# 9 — body-license: title carries the phrase, body disavows it on a
# single line → title is admitted (PR-author-cannot-edit-title case).
def test_pr_title_overclaim_body_licensed_admitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "GH_PR_TITLE",
        "feat(evidence): runtime hash binding + cryptographic evidence chain",
    )
    monkeypatch.setenv(
        "GH_PR_BODY",
        (
            "## Summary\n\n"
            "This PR is a runtime repo-file hash binding gate, "
            "**not** a 'cryptographic evidence chain'. Scope is "
            "intentionally narrow.\n"
        ),
    )
    v = find_overclaims(_REPO_ROOT)
    assert all("PR_TITLE" not in s for s in v), v
    assert all("PR_BODY" not in s for s in v), v


# 10 — body-license is *phrase-scoped*: a different forbidden phrase in
# the title is NOT licensed by an unrelated disavowal in the body.
def test_pr_title_overclaim_unrelated_body_disavowal_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "GH_PR_TITLE",
        "feat: hypothesis validated by Phase 2.1",
    )
    monkeypatch.setenv(
        "GH_PR_BODY",
        "This PR is **not** a 'cryptographic evidence chain'.\n",
    )
    v = find_overclaims(_REPO_ROOT)
    assert any("PR_TITLE" in s and "hypothesis validated" in s for s in v), v


# 11 — body that mentions a forbidden phrase *positively* (no disavowal
# token on the line) does NOT license the title. Both title and body
# remain hard-fail.
def test_pr_body_positive_phrase_does_not_license_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "GH_PR_TITLE",
        "feat: cryptographic evidence chain",
    )
    monkeypatch.setenv(
        "GH_PR_BODY",
        "We ship a cryptographic evidence chain in this PR.\n",
    )
    v = find_overclaims(_REPO_ROOT)
    assert any("PR_TITLE" in s and "cryptographic evidence chain" in s for s in v)
    assert any("PR_BODY" in s and "cryptographic evidence chain" in s for s in v)
