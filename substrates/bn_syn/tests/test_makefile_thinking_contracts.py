from __future__ import annotations

from pathlib import Path


def test_world_class_target_is_fail_closed_and_showcase_based() -> None:
    mk = Path("Makefile").read_text(encoding="utf-8")
    block_start = mk.index("thinking_world_class_artifact:")
    block = mk[block_start:block_start + 600]

    assert "MACHINE_THINKING_SHOWCASE_CHECKLIST.md" in block
    assert "|| true" not in block


def test_thinking_product_report_uses_showcase_input() -> None:
    mk = Path("Makefile").read_text(encoding="utf-8")
    block_start = mk.index("thinking_product_report:")
    block = mk[block_start:block_start + 400]

    assert "MACHINE_THINKING_SHOWCASE_CHECKLIST.md" in block
