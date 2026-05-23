from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("evidence")
OUT = Path("artifacts/package/evidence_manifest.json")
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".log"}


def is_excluded(path: Path) -> bool:
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True
    return path.suffix in EXCLUDED_SUFFIXES


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, int | str]] = []

    if ROOT.exists():
        for candidate in sorted(ROOT.rglob("*")):
            if not candidate.is_file() or is_excluded(candidate):
                continue
            files.append({"path": str(candidate), "size": candidate.stat().st_size})

    OUT.write_text(json.dumps({"count": len(files), "files": files}, indent=2), encoding="utf-8")
    print(f"manifest: {len(files)} files")


if __name__ == "__main__":
    main()
