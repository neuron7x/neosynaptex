"""Offline validation runner tests; no shell invocation and no external CI."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts import verify_neuroai_offline as gate


def test_fixed_plan_uses_python_modules_and_no_shell() -> None:
    commands = gate._plan()
    assert tuple(name for name, _ in commands) == (
        "compile", "pytest", "ruff", "mypy",
    )
    assert all(args[0] == "-m" for _, args in commands)
    assert all(";" not in part and "|" not in part for _, args in commands
               for part in args)


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
        (output / f"{name}.log").write_bytes(data)
        status = "FAIL" if failure == "stage" and name == "pytest" else "PASS"
        return {
            "command": ["python", *args], "status": status,
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
    assert len(verdict["stages"]) == 4


def test_gate_records_pass_only_with_clean_sources_and_all_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for relative in gate._SOURCE_PATHS:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("test", encoding="utf-8")

    monkeypatch.setattr(gate, "_git", lambda root, *args: (
        ("", None) if "status" in args else ("b" * 40, None)
    ))

    def fake_run(root: Path, name: str, args, output: Path, timeout: int):
        raw = b"logged\n"
        (output / f"{name}.log").write_bytes(raw)
        return {
            "command": ["python", *args], "status": "PASS", "returncode": 0,
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
