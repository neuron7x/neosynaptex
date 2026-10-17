#!/usr/bin/env python3
"""Verify every Git-tracked base file against the release Git-blob inventory.

Run from the extracted GitHub commit-pinned source ZIP. This does not validate
the absent .git history or ChatGPT messages not present in the archive.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import sys

EXPECTED_COUNT = 10694
EXPECTED_MANIFEST_CHUNKS = 6

def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()

def verify(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    manifests = sorted((root / "RELEASE_CANONICAL" / "MANIFEST").glob("part-*.tsv"))
    errors: list[str] = []
    if len(manifests) != EXPECTED_MANIFEST_CHUNKS:
        return 0, [f"expected {EXPECTED_MANIFEST_CHUNKS} manifest parts, found {len(manifests)}"]
    seen: set[str] = set()
    count = 0
    for manifest in manifests:
        for line_num, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            try:
                mode, digest, size, rel = line.split("\t", 3)
                if rel in seen or rel.startswith("/") or "\\" in rel or any(x in ("..", "") for x in rel.split("/")):
                    raise ValueError("duplicate_or_unsafe_path")
                if mode not in ("100644", "100755") or len(digest) != 40:
                    raise ValueError("malformed_blob_identity")
                if any(c not in "0123456789abcdef" for c in digest):
                    raise ValueError("bad_blob_hex")
                size_num = int(size)
                if size_num < 0:
                    raise ValueError("negative_size")
                candidate = root / rel
                if candidate.is_symlink() or not candidate.is_file():
                    raise ValueError("file_missing_or_symlink")
                raw = candidate.read_bytes()
                if len(raw) != size_num:
                    raise ValueError("size_mismatch")
                if git_blob_sha1(raw) != digest:
                    raise ValueError("git_blob_mismatch")
                seen.add(rel)
                count += 1
            except Exception as error:
                errors.append(f"{manifest.name}:{line_num}:{type(error).__name__}:{error}")
    if count != EXPECTED_COUNT:
        errors.append(f"file_count_mismatch expected={EXPECTED_COUNT} observed={count}")
    return count, errors

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="extracted GitHub ZIP source directory")
    parser.add_argument("--archive", type=Path, help="optional original ZIP to SHA-256")
    args = parser.parse_args()
    count, errors = verify(args.root)
    if args.archive:
        if not args.archive.is_file():
            errors.append("zip_file_missing")
        else:
            h = hashlib.sha256()
            with args.archive.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            print("ZIP_SHA256=" + h.hexdigest())
    for e in errors[:40]:
        print("ERROR: " + e, file=sys.stderr)
    if len(errors) > 40:
        print("ERROR: more errors omitted", file=sys.stderr)
    print(f"SOURCE_FILE_COUNT={count}; ERRORS={len(errors)}; STATUS={'FAIL' if errors else 'PASS'}")
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
