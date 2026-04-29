"""Tests for tools.audit.ledger_evidence_binding (Phase 2.1, P1+P2).

Numbered tests:
1.  Real repository ledger has every declared hash bound to disk.
2.  Stored hash with no source path → REJECTED (UNBOUND HASH).
3.  Source path with stored=null → REJECTED (declared source without hash).
4.  Stored hash that doesn't match disk → REJECTED (DRIFT).
5.  Source file that does not exist → REJECTED.
6.  ``stored=None AND source=None`` → ADMITTED (honest null).
7.  P1: absolute path /etc/hosts → REJECTED.
8.  P1: ``../outside.txt`` traversal → REJECTED.
9.  P1: ``foo/../../etc/hosts`` indirect traversal → REJECTED.
10. P1: Windows drive ``C:/Windows/...`` → REJECTED.
11. P1: UNC share ``\\\\server\\share`` → REJECTED.
12. P1: empty path → REJECTED.
13. P1: NUL/control char in path → REJECTED.
14. P1: symlink that escapes the repo root → REJECTED.
15. P1: tmp_path absolute file → REJECTED.
16. P2: list as hash_binding → REJECTED.
17. P2: 0 as hash_binding → REJECTED.
18. P2: empty string as hash_binding → REJECTED.
19. P2: False as hash_binding → REJECTED.
20. P2: dict with no entries → ADMITTED (no bindings declared).
21. P2: missing hash_binding → ADMITTED.
22. ``compute_file_hash`` matches stdlib for a known fixture.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.audit.ledger_evidence_binding import (
    BindingError,
    collect_violations,
    compute_file_hash,
    is_safe_repo_path,
    resolve_repo_relative_source,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LEDGER = _REPO_ROOT / "evidence" / "gamma_ledger.json"


# 1
def test_real_ledger_passes_binding() -> None:
    ledger = json.loads(_LEDGER.read_text(encoding="utf-8"))
    violations = collect_violations(ledger)
    assert violations == [], f"binding drift in canonical ledger: {violations}"


# 2
def test_unbound_hash_rejected(tmp_path: Path) -> None:
    ledger = {
        "entries": {
            "x": {
                "data_sha256": "a" * 64,
                "adapter_code_hash": None,
            }
        }
    }
    v = collect_violations(ledger, repo_root=tmp_path)
    assert any("UNBOUND HASH" in s for s in v)


# 3
def test_source_without_hash_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "f.txt"
    fixture.write_bytes(b"x")
    ledger = {
        "entries": {
            "x": {
                "data_sha256": None,
                "adapter_code_hash": None,
                "hash_binding": {"data_sha256_source": "f.txt"},
            }
        }
    }
    v = collect_violations(ledger, repo_root=tmp_path)
    assert any("declared source without a hash" in s for s in v)


# 4
def test_drift_detected(tmp_path: Path) -> None:
    fixture = tmp_path / "f.txt"
    fixture.write_bytes(b"x")
    ledger = {
        "entries": {
            "x": {
                "data_sha256": "deadbeef" * 8,
                "adapter_code_hash": None,
                "hash_binding": {"data_sha256_source": "f.txt"},
            }
        }
    }
    v = collect_violations(ledger, repo_root=tmp_path)
    assert any("DRIFT" in s for s in v)


# 5
def test_missing_source_file_rejected(tmp_path: Path) -> None:
    ledger = {
        "entries": {
            "x": {
                "data_sha256": "a" * 64,
                "adapter_code_hash": None,
                "hash_binding": {"data_sha256_source": "does/not/exist.txt"},
            }
        }
    }
    v = collect_violations(ledger, repo_root=tmp_path)
    assert any("does not exist" in s for s in v)


# 6
def test_honest_null_admitted(tmp_path: Path) -> None:
    ledger = {
        "entries": {
            "x": {
                "data_sha256": None,
                "adapter_code_hash": None,
                "hash_binding": {},
            }
        }
    }
    assert collect_violations(ledger, repo_root=tmp_path) == []


# ───────── P1 path-safety adversarials ─────────


def _bad_path_ledger(source: str) -> dict:
    return {
        "entries": {
            "x": {
                "data_sha256": "a" * 64,
                "adapter_code_hash": None,
                "hash_binding": {"data_sha256_source": source},
            }
        }
    }


# 7
def test_absolute_etc_hosts_rejected(tmp_path: Path) -> None:
    v = collect_violations(_bad_path_ledger("/etc/hosts"), repo_root=tmp_path)
    assert any("absolute" in s for s in v)


# 8
def test_dotdot_traversal_rejected(tmp_path: Path) -> None:
    v = collect_violations(_bad_path_ledger("../outside.txt"), repo_root=tmp_path)
    assert any("traversal" in s for s in v)


# 9
def test_indirect_traversal_rejected(tmp_path: Path) -> None:
    v = collect_violations(_bad_path_ledger("foo/../../etc/hosts"), repo_root=tmp_path)
    assert any("traversal" in s for s in v)


# 10
def test_windows_drive_rejected(tmp_path: Path) -> None:
    v = collect_violations(_bad_path_ledger("C:/Windows/System32"), repo_root=tmp_path)
    assert any("drive" in s.lower() for s in v)


# 11
def test_unc_share_rejected(tmp_path: Path) -> None:
    v = collect_violations(_bad_path_ledger(r"\\server\share"), repo_root=tmp_path)
    assert any("drive" in s.lower() or "absolute" in s.lower() for s in v)


# 12
def test_empty_path_rejected(tmp_path: Path) -> None:
    # Empty source is treated as None at the binding level (declared source
    # absent), so the entry's stored hash becomes UNBOUND. Either way,
    # something must be rejected.
    v = collect_violations(_bad_path_ledger(""), repo_root=tmp_path)
    assert v, "empty path must produce a violation"


# 13
@pytest.mark.parametrize("payload", ["foo\x00bar", "foo\nbar", "foo\rbar", "foo\tbar"])
def test_control_char_rejected(tmp_path: Path, payload: str) -> None:
    v = collect_violations(_bad_path_ledger(payload), repo_root=tmp_path)
    assert any("control" in s.lower() for s in v)


# 14
@pytest.mark.skipif(os.name == "nt", reason="symlinks behave differently on Windows")
def test_symlink_escape_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.bin"
    outside.write_bytes(b"x")
    repo = tmp_path / "repo"
    repo.mkdir()
    link = repo / "trapdoor"
    link.symlink_to(outside)
    ledger = {
        "entries": {
            "x": {
                "data_sha256": hashlib.sha256(b"x").hexdigest(),
                "adapter_code_hash": None,
                "hash_binding": {"data_sha256_source": "trapdoor"},
            }
        }
    }
    v = collect_violations(ledger, repo_root=repo)
    assert any("outside the repository" in s for s in v), f"got: {v}"


# 15
def test_tmp_path_absolute_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "f.txt"
    fixture.write_bytes(b"x")
    # Pass the absolute path string directly as source
    abs_str = str(fixture.resolve())
    v = collect_violations(_bad_path_ledger(abs_str), repo_root=tmp_path)
    assert any("absolute" in s.lower() or "drive" in s.lower() for s in v)


# ───────── P2 hash_binding type adversarials ─────────


def _bad_hb_ledger(hb: object) -> dict:
    return {
        "entries": {
            "x": {
                "data_sha256": None,
                "adapter_code_hash": None,
                "hash_binding": hb,
            }
        }
    }


# 16-19
@pytest.mark.parametrize("hb", [[], 0, "", False, "abc", 42, ["a"]])
def test_falsy_or_nondict_hash_binding_rejected(tmp_path: Path, hb: object) -> None:
    v = collect_violations(_bad_hb_ledger(hb), repo_root=tmp_path)
    assert any("hash_binding must be a dict" in s for s in v)


# 20
def test_dict_hash_binding_admitted(tmp_path: Path) -> None:
    assert collect_violations(_bad_hb_ledger({}), repo_root=tmp_path) == []


# 21
def test_missing_hash_binding_admitted(tmp_path: Path) -> None:
    ledger = {"entries": {"x": {"data_sha256": None, "adapter_code_hash": None}}}
    assert collect_violations(ledger, repo_root=tmp_path) == []


# 22
def test_compute_file_hash_matches_stdlib(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    payload = b"phase-2.1-binding-test" * 1000
    p.write_bytes(payload)
    assert compute_file_hash(p) == hashlib.sha256(payload).hexdigest()


def test_binding_error_class_exists() -> None:
    assert issubclass(BindingError, ValueError)


# ───────── is_safe_repo_path direct unit checks ─────────


@pytest.mark.parametrize(
    "src, expected_ok",
    [
        ("substrates/eeg_resting/adapter.py", True),
        ("evidence/data_hashes.json", True),
        ("/etc/hosts", False),
        ("../outside.txt", False),
        ("C:/Windows", False),
        ("", False),
        ("foo\x00bar", False),
        (".", False),  # P1 stricter — bare repo root rejected
    ],
)
def test_is_safe_repo_path_unit(src: str, expected_ok: bool) -> None:
    ok, _err = is_safe_repo_path(src, repo_root=_REPO_ROOT)
    assert ok is expected_ok


# ───────── P1 stricter — resolve_repo_relative_source raise-style API ─────────


def test_resolve_resolves_real_repo_file() -> None:
    p = resolve_repo_relative_source("evidence/data_hashes.json", _REPO_ROOT)
    assert p.exists() and p.is_file()
    assert p.is_absolute()


@pytest.mark.parametrize(
    "src",
    [
        "/etc/hosts",
        "../outside.txt",
        "foo/../../etc/hosts",
        "C:/Windows/System32",
        r"\\server\share",
        "",
        "foo\x00bar",
        "foo\nbar",
        ".",
        "./",
    ],
)
def test_resolve_raises_on_unsafe(src: str, tmp_path: Path) -> None:
    with pytest.raises(BindingError):
        resolve_repo_relative_source(src, tmp_path)


def test_resolve_raises_on_non_string() -> None:
    with pytest.raises(BindingError, match="non-empty string"):
        resolve_repo_relative_source(42, _REPO_ROOT)
    with pytest.raises(BindingError, match="non-empty string"):
        resolve_repo_relative_source(None, _REPO_ROOT)
    with pytest.raises(BindingError, match="non-empty string"):
        resolve_repo_relative_source([], _REPO_ROOT)


def test_resolve_rejects_directory(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    with pytest.raises(BindingError, match="non-regular"):
        resolve_repo_relative_source("sub", tmp_path)
