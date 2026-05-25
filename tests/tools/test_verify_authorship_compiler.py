from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.verify_authorship_compiler as vac


def _sentinel(*parts: str) -> str:
    return " ".join(parts)


def test_i1_rejects_disallowed_path() -> None:
    with pytest.raises(vac.InvariantError):
        vac._check_i1(["bad/file.txt"], ["core/"])


def test_i2_rejects_forbidden_pattern(tmp_path: Path) -> None:
    forbidden = _sentinel("seamless", "integration")
    f = tmp_path / "a.md"
    f.write_text(forbidden, encoding="utf-8")
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        with pytest.raises(vac.InvariantError):
            vac._check_i2(["a.md"], [forbidden])
    finally:
        os.chdir(cwd)


def test_i2_skips_authorship_policy_file_during_pattern_scan(tmp_path: Path) -> None:
    policy = tmp_path / ".repo" / "authorship_compiler.yaml"
    policy.parent.mkdir(parents=True)
    policy_sentinel = _sentinel("policy", "sentinel")
    policy.write_text(f"forbidden_patterns: ['{policy_sentinel}']\n", encoding="utf-8")
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        vac._check_i2(
            [".repo/authorship_compiler.yaml"],
            [policy_sentinel],
            ignored_paths=[".repo/authorship_compiler.yaml"],
        )
    finally:
        os.chdir(cwd)


def test_i6_fails_when_no_verified_edges(tmp_path: Path) -> None:
    f = tmp_path / "README.md"
    f.write_text("hello world", encoding="utf-8")
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        with pytest.raises(vac.InvariantError):
            vac._check_i6(["README.md"], min_verified_edges=1, max_public_tokens=100)
    finally:
        os.chdir(cwd)


def test_i7_passes_when_no_runtime_changes(tmp_path: Path) -> None:
    snap = tmp_path / ".repo" / "public_symbols.sha256"
    snap.parent.mkdir(parents=True)
    snap.write_text("x", encoding="utf-8")
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        vac._check_i7(["README.md"], ".repo/public_symbols.sha256", ["core/"], ["README.md"])
    finally:
        os.chdir(cwd)


def test_i7_rejects_ack_that_omits_changed_runtime_file(tmp_path: Path) -> None:
    core_file = tmp_path / "core" / "dre.py"
    core_file.parent.mkdir(parents=True)
    core_file.write_text("runtime", encoding="utf-8")
    repo = tmp_path / ".repo"
    repo.mkdir()
    (repo / "public_symbols.sha256").write_text("stale", encoding="utf-8")
    (repo / "runtime_api_change_ack.json").write_text(
        json.dumps(
            {
                "ack_id": "ACK-1",
                "runtime_surface": ["core/other.py"],
                "reason": "Intentional runtime API change under explicit review boundary.",
                "claim_status": "derived",
            }
        ),
        encoding="utf-8",
    )
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        with pytest.raises(vac.InvariantError, match="omits changed runtime files"):
            vac._check_i7(
                ["core/dre.py", "tests/test_dre.py", ".repo/runtime_api_change_ack.json"],
                ".repo/public_symbols.sha256",
                ["core/"],
                ["README.md", "docs/", ".github/"],
            )
    finally:
        os.chdir(cwd)


def test_i7_accepts_substantive_ack_covering_changed_runtime_file(tmp_path: Path) -> None:
    core_file = tmp_path / "core" / "dre.py"
    core_file.parent.mkdir(parents=True)
    core_file.write_text("runtime", encoding="utf-8")
    repo = tmp_path / ".repo"
    repo.mkdir()
    (repo / "public_symbols.sha256").write_text("stale", encoding="utf-8")
    (repo / "runtime_api_change_ack.json").write_text(
        json.dumps(
            {
                "ack_id": "ACK-1",
                "runtime_surface": ["core/dre.py"],
                "reason": "Intentional runtime API change under explicit review boundary.",
                "claim_status": "derived",
            }
        ),
        encoding="utf-8",
    )
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        vac._check_i7(
            ["core/dre.py", "tests/test_dre.py", ".repo/runtime_api_change_ack.json"],
            ".repo/public_symbols.sha256",
            ["core/"],
            ["README.md", "docs/", ".github/"],
        )
    finally:
        os.chdir(cwd)
