"""Dataset Merkle root computation (Phase 2.1 P8).

Treats ``evidence/data_hashes.json`` as the manifest from which a per-
dataset Merkle root is computed. The root is **not** the file's own
hash (the previous mistake) but a hash over the canonicalised
sequence of (path, sha256) pairs for that dataset, so a malicious
edit anywhere in the manifest changes the root.

P8 partial-implementation note (honest scope)
---------------------------------------------

The full P8 spec asks for ``SHA256(sorted(path, size_bytes,
sha256(raw_file)))``. The committed manifest does not yet record
``size_bytes`` for every file — the raw datasets live on PhysioNet,
not in the repo. This implementation:

* hashes ``path|sha256`` pairs (without size_bytes), AND
* surfaces the missing-size gap explicitly in the output payload
  (``size_bytes_known`` boolean).

A follow-up will add size_bytes to the manifest and lift the partial
flag. Until then, downstream consumers must treat the root as binding
the *manifest's claim about each file's hash*, not the raw bytes
themselves.

Output format
-------------

Writes ``evidence/data_merkle_roots.json`` with shape::

    {
        "datasets": {
            "<name>": {
                "n_files": <int>,
                "size_bytes_known": false,
                "merkle_root_sha256": "<64-hex>",
                "first_file": "...", "last_file": "..."
            }, ...
        }
    }

Exit codes
----------

* 0 — manifest read, roots written, every dataset has at least one file.
* 2 — manifest missing or malformed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

__all__ = [
    "compute_dataset_root",
    "main",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / "evidence" / "data_hashes.json"
_OUT = _REPO_ROOT / "evidence" / "data_merkle_roots.json"


def compute_dataset_root(file_hashes: dict[str, str]) -> str:
    """Compute the Merkle-style root for one dataset's ``{path: sha256}`` map.

    The root is::

        SHA256(b"\\n".join(f"{path}\\0{sha256}" for path in sorted(file_hashes)))

    Sorting + NUL separator + per-line newline gives a canonical encoding
    that is collision-resistant under SHA-256 *given* the SHA-256 hashes
    themselves (no malleability through path reordering or ambiguity).
    """
    if not file_hashes:
        raise ValueError("dataset has no file hashes")
    parts: list[bytes] = []
    for path in sorted(file_hashes):
        sha = file_hashes[path]
        if not isinstance(sha, str) or len(sha) != 64:
            raise ValueError(f"bad sha256 for {path!r}: {sha!r}")
        parts.append(f"{path}\0{sha}".encode())
    return hashlib.sha256(b"\n".join(parts)).hexdigest()


def build_roots_doc(manifest: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"datasets": {}}
    for name, ds in manifest.get("datasets", {}).items():
        sha_map = ds.get("sha256")
        if not isinstance(sha_map, dict) or not sha_map:
            continue
        root = compute_dataset_root(sha_map)
        keys = sorted(sha_map)
        out["datasets"][name] = {
            "n_files": len(sha_map),
            "size_bytes_known": False,
            "merkle_root_sha256": root,
            "first_file": keys[0],
            "last_file": keys[-1],
        }
    return out


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", default=str(_MANIFEST), type=Path)
    p.add_argument("--out", default=str(_OUT), type=Path)
    p.add_argument(
        "--check",
        action="store_true",
        help="exit 2 if recomputing the manifest does not match the existing roots file",
    )
    args = p.parse_args(argv)
    if not args.manifest.is_file():
        print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    roots = build_roots_doc(manifest)
    if args.check:
        if not args.out.is_file():
            print(
                f"ERROR: roots file missing: {args.out}; run without --check to generate",
                file=sys.stderr,
            )
            return 2
        existing = json.loads(args.out.read_text(encoding="utf-8"))
        if existing != roots:
            print(
                "DRIFT: data_merkle_roots.json does not match recomputed roots",
                file=sys.stderr,
            )
            for name, current in roots["datasets"].items():
                stored = existing.get("datasets", {}).get(name)
                if stored != current:
                    print(
                        f"  - {name}: stored={stored} recomputed={current}",
                        file=sys.stderr,
                    )
            return 2
        print(f"OK: {len(roots['datasets'])} dataset Merkle root(s) match the manifest.")
        return 0
    args.out.write_text(json.dumps(roots, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.out} ({len(roots['datasets'])} dataset(s); "
        "size_bytes_known=False — see module docstring)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
