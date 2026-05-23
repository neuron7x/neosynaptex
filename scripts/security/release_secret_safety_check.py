from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.security.secret_safety_check import PATTERNS

OUT = Path("artifacts/security/gitleaks.json")
SCAN_ROOTS = (
    Path(".github"),
    Path("contracts"),
    Path("core"),
    Path("docs"),
    Path("evidence"),
    Path("evl"),
    Path("scripts"),
    Path("substrates"),
    Path("tools"),
    Path("Makefile"),
    Path("pyproject.toml"),
    Path("neosynaptex.py"),
)
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
}
SKIP_FILES = {
    Path("scripts/security/secret_safety_check.py"),
    Path("scripts/security/release_secret_safety_check.py"),
    Path("artifacts/security/gitleaks.json"),
}
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".npy",
    ".npz",
    ".parquet",
    ".onnx",
    ".pt",
    ".pth",
    ".pyc",
    ".pyo",
}
ALLOW_MARKERS = (
    "dummy",
    "example",
    "fake",
    "fixture",
    "placeholder",
    "test token",
    "test-token",
)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
        else:
            files.extend(p for p in root.rglob("*") if p.is_file())
    return sorted(set(files))


def should_skip(path: Path) -> bool:
    normalized = Path(path.as_posix())
    if normalized in SKIP_FILES:
        return True
    if any(part in SKIP_DIRS for part in normalized.parts):
        return True
    return normalized.suffix.lower() in BINARY_SUFFIXES


def main() -> int:
    findings: list[dict[str, str | int]] = []
    for path in iter_files():
        if should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if any(marker in lowered for marker in ALLOW_MARKERS):
                continue
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append({"file": str(path), "line": line_no, "rule": name})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"findings": findings}, indent=2), encoding="utf-8")
    if findings:
        print(f"FAIL: secret findings: {len(findings)}")
        for finding in findings[:25]:
            print(f"{finding['file']}:{finding['line']} {finding['rule']}")
        return 1
    print("secret-scan: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
