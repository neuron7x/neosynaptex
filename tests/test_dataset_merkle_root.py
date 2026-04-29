"""Tests for tools.audit.dataset_merkle_root (Phase 2.1 P8).

Numbered tests:
1.  Empty file map raises.
2.  Bad sha256 (wrong length) raises.
3.  Root depends on file content (changing one sha changes the root).
4.  Root depends on file PATH (renaming a file changes the root).
5.  Root is invariant under input ordering (sorted internally).
6.  Real manifest produces stable roots — roots file matches recompute.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit.dataset_merkle_root import build_roots_doc, compute_dataset_root

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST = _REPO_ROOT / "evidence" / "data_hashes.json"
_ROOTS = _REPO_ROOT / "evidence" / "data_merkle_roots.json"


# 1
def test_empty_dataset_rejected() -> None:
    with pytest.raises(ValueError, match="no file hashes"):
        compute_dataset_root({})


# 2
def test_bad_sha_length_rejected() -> None:
    with pytest.raises(ValueError, match="bad sha256"):
        compute_dataset_root({"a.bin": "deadbeef"})


# 3
def test_root_depends_on_content() -> None:
    a = compute_dataset_root({"f.bin": "a" * 64})
    b = compute_dataset_root({"f.bin": "b" * 64})
    assert a != b


# 4
def test_root_depends_on_path() -> None:
    a = compute_dataset_root({"foo": "a" * 64})
    b = compute_dataset_root({"bar": "a" * 64})
    assert a != b


# 5
def test_root_invariant_under_ordering() -> None:
    raw = {"b": "1" * 64, "a": "2" * 64, "c": "3" * 64}
    reordered = {"c": "3" * 64, "a": "2" * 64, "b": "1" * 64}
    assert compute_dataset_root(raw) == compute_dataset_root(reordered)


# 6
def test_real_roots_match_manifest_recompute() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    roots_recomputed = build_roots_doc(manifest)
    roots_stored = json.loads(_ROOTS.read_text(encoding="utf-8"))
    assert roots_stored == roots_recomputed, (
        "evidence/data_merkle_roots.json drifted from evidence/data_hashes.json — "
        "rerun: python -m tools.audit.dataset_merkle_root"
    )
