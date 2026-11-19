"""Offline validation runner tests; no shell invocation and no external CI."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts import verify_neuroai_offline as gate


def _valid_junit() -> str:
    cases = "".join(f'<testcase name="{name}"/>' for name in sorted(gate._MANDATORY_CASES))
    return f"<testsuite>{cases}</testsuite>"


def test_fixed_plan_uses_python_modules_and_no_shell() -> None:
    commands = gate._plan()
    assert tuple(name for name, _ in commands) == (
        "compile",
        "pytest",
        "pytest_required",
        "ruff",
        "mypy",
    )
    assert all(args[0] == "-m" for _, args in commands)
    assert all(";" not in part and "|" not in part for _, args in commands for part in args)


def test_source_manifest_digest_matches_source_bytes(tmp_path: Path) -> None:
    for relative in gate._SOURCE_PATHS:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(relative.encode())
    hashes, blockers = gate._read_manifest(tmp_path)
    assert not blockers
    assert set(hashes) == set(gate._SOURCE_PATHS)
    for relative, expected in hashes.items():
        assert expected == hashlib.sha256(relative.encode()).hexdigest()


def test_missing_source_is_never_silently_accepted(tmp_path: Path) -> None:
    hashes, blockers = gate._read_manifest(tmp_path)
    assert hashes == {}
    assert len(blockers) == len(gate._SOURCE_PATHS)


@pytest.mark.parametrize("failure", ["stage", "dirty", "missing"])
def test_overall_fails_closed_on_any_precondition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    for relative in gate._SOURCE_PATHS:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("test", encoding="utf-8")

    def fake_git(root: Path, *args: str):
        if "status" in args:
            return (" M core/eai/dopa_budget.py", None) if failure == "dirty" else ("", None)
        return ("a" * 40, None)

    def fake_run(root: Path, name: str, args, output: Path, timeout: int):
        data = b"fixture\n"
        if name == "pytest_required":
            (output / "required-tests.xml").write_text(
                _valid_junit(),
                encoding="utf-8",
            )
        (output / f"{name}.log").write_bytes(data)
        status = "FAIL" if failure == "stage" and name == "pytest" else "PASS"
        return {
            "command": ["python", *args],
            "status": status,
            "returncode": 1 if status == "FAIL" else 0,
            "log_file": f"{name}.log",
            "log_sha256": hashlib.sha256(data).hexdigest(),
        }

    monkeypatch.setattr(gate, "_git", fake_git)
    monkeypatch.setattr(gate, "_run", fake_run)
    if failure == "missing":
        (tmp_path / gate._SOURCE_PATHS[0]).unlink()
    verdict = gate.execute_gate(tmp_path, tmp_path / "output")
    assert verdict["overall"] == "FAIL"
    assert (tmp_path / "output" / "evidence.json").exists()
    assert len(verdict["stages"]) == 5


def test_gate_records_pass_only_with_clean_sources_and_all_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for relative in gate._SOURCE_PATHS:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("test", encoding="utf-8")

    monkeypatch.setattr(
        gate, "_git", lambda root, *args: ("", None) if "status" in args else ("b" * 40, None)
    )

    def fake_run(root: Path, name: str, args, output: Path, timeout: int):
        raw = b"logged\n"
        if name == "pytest_required":
            (output / "required-tests.xml").write_text(
                _valid_junit(),
                encoding="utf-8",
            )
        (output / f"{name}.log").write_bytes(raw)
        return {
            "command": ["python", *args],
            "status": "PASS",
            "returncode": 0,
            "log_file": f"{name}.log",
            "log_sha256": hashlib.sha256(raw).hexdigest(),
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    result = gate.execute_gate(tmp_path, tmp_path / "gate-output")
    assert result["overall"] == "PASS"
    assert result["repository_commit"] == "b" * 40
    assert result["epistemic_scope"] == "LOCAL_CODE_AND_TOOL_EXECUTION_ONLY"


def test_preexisting_evidence_directory_is_not_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "evidence"
    target.mkdir()
    with pytest.raises(FileExistsError):
        gate.execute_gate(tmp_path, target)


def test_required_junit_rejects_missing_empty_and_skipped(tmp_path: Path) -> None:
    path = tmp_path / "required-tests.xml"
    assert gate._junit_summary(path)[1] == "required_junit_missing_or_symlink"
    path.write_text("<testsuite/>", encoding="utf-8")
    summary, reason = gate._junit_summary(path)
    assert summary == {"collected": 0, "skipped": 0, "failures": 0, "errors": 0}
    assert reason == "required_tests_missing_skipped_or_failed"
    path.write_text(
        '<testsuite><testcase name="a"><skipped/></testcase></testsuite>',
        encoding="utf-8",
    )
    summary, reason = gate._junit_summary(path)
    assert summary["skipped"] == 1
    assert reason == "required_tests_missing_skipped_or_failed"
    path.write_text(
        '<testsuite><testcase name="a"/></testsuite>',
        encoding="utf-8",
    )
    assert gate._junit_summary(path)[1] == "mandatory_named_tests_not_executed"
    path.write_text(_valid_junit(), encoding="utf-8")
    assert gate._junit_summary(path)[1] is None


def test_log_integrity_requires_matching_bytes(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    data = b"passed"
    (output / "pytest.log").write_bytes(data)
    stage = {
        "pytest": {
            "log_file": "pytest.log",
            "log_sha256": hashlib.sha256(data).hexdigest(),
        }
    }
    assert gate._log_blockers(output, stage) == []
    (output / "pytest.log").write_bytes(b"forged")
    assert gate._log_blockers(output, stage) == ["stage_log_sha256_mismatch:pytest"]


def test_postflight_fails_if_source_changes_during_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for relative in gate._SOURCE_PATHS:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"original")
    monkeypatch.setattr(
        gate, "_git", lambda root, *args: ("", None) if "status" in args else ("b" * 40, None)
    )

    def mutate(root: Path, name: str, args, output: Path, timeout: int):
        data = b"fixture"
        (output / f"{name}.log").write_bytes(data)
        if name == "pytest_required":
            (output / "required-tests.xml").write_text(
                _valid_junit(),
                encoding="utf-8",
            )
        if name == "pytest":
            (root / gate._SOURCE_PATHS[0]).write_bytes(b"mutated")
        return {
            "command": ["python", *args],
            "status": "PASS",
            "returncode": 0,
            "log_file": f"{name}.log",
            "log_sha256": hashlib.sha256(data).hexdigest(),
        }

    monkeypatch.setattr(gate, "_run", mutate)
    result = gate.execute_gate(tmp_path, tmp_path / "evidence")
    assert result["overall"] == "FAIL"
    assert "source_manifest_changed_during_validation" in result["postflight_blockers"]
