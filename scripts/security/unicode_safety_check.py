from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

FORBIDDEN_CATEGORIES = {"Cf", "Cc"}
FORBIDDEN_CODEPOINTS = {
    *range(0x202A, 0x202F),
    *range(0x2066, 0x2070),
    0x200B,
    0x200C,
    0x200D,
    0xFEFF,
}
ALLOWED_CONTROL = {"\n", "\r", "\t"}
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
    ".lock",
}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return path.suffix.lower() in BINARY_SUFFIXES


def is_forbidden(ch: str) -> bool:
    cp = ord(ch)
    if cp in FORBIDDEN_CODEPOINTS:
        return True
    return unicodedata.category(ch) in FORBIDDEN_CATEGORIES and ch not in ALLOWED_CONTROL


def main() -> int:
    findings: list[str] = []
    for path in Path(".").rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
            for col_no, ch in enumerate(line, start=1):
                if is_forbidden(ch):
                    findings.append(
                        f"{path}:{line_no}:{col_no}: U+{ord(ch):04X} "
                        f"{unicodedata.name(ch, 'UNKNOWN')} category={unicodedata.category(ch)}"
                    )
    if findings:
        print("FAIL: hidden/control Unicode detected")
        for item in findings:
            print(item)
        return 1
    print("unicode-scan: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
