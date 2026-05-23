from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUT = Path("artifacts/security/gitleaks.json")
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
}
PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "generic_private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return path.suffix.lower() in BINARY_SUFFIXES


def main() -> int:
    findings: list[dict[str, str | int]] = []
    for path in Path(".").rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append({"file": str(path), "line": line_no, "rule": name})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"findings": findings}, indent=2), encoding="utf-8")
    if findings:
        print(f"FAIL: secret findings: {len(findings)}")
        return 1
    print("secret-scan: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
