from __future__ import annotations

from pathlib import Path


def _block(text: str, target: str, span: int = 700) -> str:
    start = text.index(f"{target}:")
    return text[start : start + span]


def test_thinking_finalize_target_is_deterministic_pipeline() -> None:
    mk = Path("Makefile").read_text(encoding="utf-8")
    block = _block(mk, "thinking_finalize")

    assert "pytest" in block
    assert "generate_thinking_product_report.py" in block
    assert "compile_thinking_artifact.py" in block
    assert "MACHINE_THINKING_SHOWCASE_CHECKLIST.md" in block


def test_thinking_finalize_target_is_fail_closed() -> None:
    mk = Path("Makefile").read_text(encoding="utf-8")
    block = _block(mk, "thinking_finalize")

    assert "|| true" not in block
