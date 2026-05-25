from __future__ import annotations

from pathlib import Path

from substrates.bn_syn.scripts.validate_thinking_checklist import validate_file


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_research_v1_fails_when_sections_missing(tmp_path: Path) -> None:
    p = _write(tmp_path, "c.md", "## PRE-WORK\n- [x] done\n")
    report = validate_file(p, profile="research_v1", min_completion=1.0, min_capital_index=0.0)
    assert report["verdict"] == "FAIL"
    assert report["structure_errors"]


def test_research_v1_passes_when_all_sections_and_items_checked(tmp_path: Path) -> None:
    sections = [
        "PRE-WORK",
        "MATH",
        "IMPLEMENTATION",
        "VALIDATION",
        "FALSIFICATION",
        "ARTIFACT",
        "GOVERNANCE",
        "FINAL TEST",
    ]
    text = "\n".join([f"## {s}\n- [x] ok" for s in sections]) + "\n"
    p = _write(tmp_path, "ok.md", text)
    report = validate_file(p, profile="research_v1", min_completion=1.0, min_capital_index=0.0)
    assert report["verdict"] == "PASS"
    assert report["completion_ratio"] == 1.0


def test_basic_profile_ignores_canonical_structure(tmp_path: Path) -> None:
    p = _write(tmp_path, "basic.md", "- [x] single item\n")
    report = validate_file(p, profile="basic", min_completion=1.0, min_capital_index=0.0)
    assert report["verdict"] == "PASS"


def test_basic_profile_can_use_threshold(tmp_path: Path) -> None:
    p = _write(tmp_path, "threshold.md", "- [x] one\n- [ ] two\n")
    report = validate_file(p, profile="basic", min_completion=0.5, min_capital_index=0.0)
    assert report["verdict"] == "PASS"
    assert report["completion_ratio"] == 0.5


def test_basic_profile_does_not_receive_structure_bonus(tmp_path: Path) -> None:
    p = _write(tmp_path, "no_bonus.md", "- [x] one\n- [ ] two\n")
    report = validate_file(p, profile="basic", min_completion=0.5, min_capital_index=0.6)

    assert report["completion_ratio"] == 0.5
    assert report["value_score"] == 0.5
    assert report["capital_index"] == 0.4
    assert report["verdict"] == "FAIL"


def test_value_score_penalizes_falsification_gap(tmp_path: Path) -> None:
    text = "## FALSIFICATION\n- [ ] unresolved\n## ARTIFACT\n- [x] done\n"
    p = _write(tmp_path, "score.md", text)
    report = validate_file(p, profile="basic", min_completion=0.0, min_capital_index=0.0)
    assert report["value_score"] < report["completion_ratio"]


def test_capital_index_threshold_blocks_pass(tmp_path: Path) -> None:
    p = _write(tmp_path, "ci.md", "- [x] one\n- [ ] two\n")
    report = validate_file(p, profile="basic", min_completion=0.5, min_capital_index=0.8)
    assert report["verdict"] == "FAIL"


def test_intention_hints_present_when_unresolved(tmp_path: Path) -> None:
    p = _write(tmp_path, "h.md", "## FALSIFICATION\n- [ ] unresolved\n")
    report = validate_file(p, profile="basic", min_completion=0.0, min_capital_index=0.0)
    assert report["intention_hints"]


def test_action_plan_is_emitted_for_unresolved_sections(tmp_path: Path) -> None:
    p = _write(tmp_path, "ap.md", "## VALIDATION\n- [ ] unresolved\n")
    report = validate_file(p, profile="basic", min_completion=0.0, min_capital_index=0.0)
    assert "VALIDATION" in report["action_plan"]
