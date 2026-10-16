"""Fail-closed local NeuroAI validation, independent of GitHub Actions.

Records raw tool logs and hash-bound source manifests. PASS proves only that
the specified tool commands completed successfully in the recorded environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

_SOURCE_PATHS = (
    "scripts/verify_neuroai_offline.py",
    "pyproject.toml",
    "tests/dopa_closure_v2/test_neuroai_offline_gate.py",
    "tests/dopa_closure_v2/test_failclosed_security.py",
    "tests/dopa_closure_v2/test_independent_arithmetic_verifier.py",
    "core/eai/dopa_closure_v2.py",
    "core/eai/dopa_independent_verifier.py",
    "core/eai/dopa_run_attestation.py",
    "core/eai/dopa_controls.py",
    "core/eai/dopa_budget.py",
    "core/eai/dopa_runtime_config.py",
    "configs/dopa_closure_v2/allocator.yaml",
    "tests/dopa_closure_v2/test_run_attestation.py",
    "tests/dopa_closure_v2/test_independent_arithmetic_full_path.py",
    "tests/dopa_closure_v2/test_control_construct_validity.py",
)
_LINT_PATHS = (
    "core/eai/dopa_independent_verifier.py",
    "core/eai/dopa_run_attestation.py",
    "core/eai/dopa_controls.py",
    "tests/dopa_closure_v2/test_run_attestation.py",
    "tests/dopa_closure_v2/test_control_construct_validity.py",
)
_MYPY_PATHS = (
    "core/eai/dopa_run_attestation.py",
    "core/eai/dopa_independent_verifier.py",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_manifest(root: Path) -> tuple[dict[str, str], list[str]]:
    hashes: dict[str, str] = {}
    problems: list[str] = []
    for name in _SOURCE_PATHS:
        path = root / name
        if path.is_symlink() or not path.is_file():
            problems.append(f"source_missing_or_symlink:{name}")
            continue
        hashes[name] = _sha(path.read_bytes())
    return hashes, problems


def _git(root: Path, *args: str) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True,
            errors="replace", timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"git_unavailable:{type(exc).__name__}"
    if result.returncode:
        return None, f"git_error:{result.returncode}:{result.stderr.strip()[:500]}"
    return result.stdout.strip(), None


def _plan() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Stable command plan; no shell, wildcard expansion, or untrusted command."""
    return (
        ("compile", ("-m", "compileall", "-q", "core/eai", "tests/dopa_closure_v2")),
        ("pytest", ("-m", "pytest", "-q", "tests/dopa_closure_v2")),
        ("pytest_required", (
            "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "tests/dopa_closure_v2/test_neuroai_offline_gate.py",
            "tests/dopa_closure_v2/test_failclosed_security.py",
            "tests/dopa_closure_v2/test_independent_arithmetic_verifier.py",
            "tests/dopa_closure_v2/test_independent_arithmetic_full_path.py",
            "tests/dopa_closure_v2/test_run_attestation.py",
            "tests/dopa_closure_v2/test_control_construct_validity.py",
        )),
        ("ruff", ("-m", "ruff", "check", *_LINT_PATHS)),
        ("mypy", ("-m", "mypy", *_MYPY_PATHS)),
    )


def _run(root: Path, name: str, args: tuple[str, ...],
         output: Path, timeout: int) -> dict[str, Any]:
    command = [sys.executable, *args]
    if name == "pytest_required":
        command.append("--junitxml=" + str((output / "required-tests.xml").resolve()))
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["NO_COLOR"] = "1"
    try:
        proc = subprocess.run(
            command, cwd=root, capture_output=True, text=True,
            errors="replace", env=env, timeout=timeout, check=False,
        )
        status = "PASS" if proc.returncode == 0 else "FAIL"
        rc = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        status, rc = "FAIL", None
        stdout = str(exc.stdout or "")
        stderr = "TIMEOUT: " + str(exc.stderr or "")
    except OSError as exc:
        status, rc, stdout = "FAIL", None, ""
        stderr = f"EXECUTION_ERROR:{type(exc).__name__}:{exc}"
    raw = (
        "COMMAND: " + " ".join(command) + "\n"
        + "STDOUT:\n" + stdout + "\nSTDERR:\n" + stderr + "\n"
    ).encode("utf-8", errors="replace")
    log_path = output / f"{name}.log"
    log_path.write_bytes(raw)
    return {
        "command": command, "status": status, "returncode": rc,
        "log_file": log_path.name, "log_sha256": _sha(raw),
    }


def _junit_summary(path: Path) -> tuple[dict[str, int] | None, str | None]:
    """Reject absent, empty, corrupt or skipped mandatory test evidence."""
    if path.is_symlink() or not path.is_file():
        return None, "required_junit_missing_or_symlink"
    if path.stat().st_size > 4 * 1024 * 1024:
        return None, "required_junit_oversize"
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError, ValueError) as exc:
        return None, f"required_junit_invalid:{type(exc).__name__}"
    if root.tag not in ("testsuite", "testsuites"):
        return None, "required_junit_wrong_root"
    cases = root.findall(".//testcase")
    summary = {
        "collected": len(cases),
        "skipped": sum(x.find("skipped") is not None for x in cases),
        "failures": sum(x.find("failure") is not None for x in cases),
        "errors": sum(x.find("error") is not None for x in cases),
    }
    if not cases or any(summary[key] for key in ("skipped", "failures", "errors")):
        return summary, "required_tests_missing_skipped_or_failed"
    return summary, None


def _log_blockers(output: Path, stages: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for stage_name, stage in stages.items():
        logfile = output / str(stage.get("log_file", ""))
        if logfile.is_symlink() or not logfile.is_file():
            failures.append(f"stage_log_missing:{stage_name}")
        elif _sha(logfile.read_bytes()) != stage.get("log_sha256"):
            failures.append(f"stage_log_sha256_mismatch:{stage_name}")
    return failures


def execute_gate(root: Path, output: Path, timeout: int = 240) -> dict[str, Any]:
    """Execute fixed validation stages and generate an independently replayable record."""
    if timeout < 1 or timeout > 3600:
        raise ValueError("timeout_seconds_outside_1_3600")
    if output.exists():
        raise FileExistsError("output_directory_already_exists")
    output.mkdir(parents=True, exist_ok=False)
    commit, commit_error = _git(root, "rev-parse", "HEAD")
    dirty, status_error = _git(root, "status", "--porcelain", "--untracked-files=all")
    manifest, missing = _read_manifest(root)
    blockers = list(missing)
    if commit_error:
        blockers.append(commit_error)
    if status_error:
        blockers.append(status_error)
    elif dirty:
        blockers.append("git_worktree_dirty")
    stages = {
        name: _run(root, name, args, output, timeout)
        for name, args in _plan()
    }
    # Validate mandatory test evidence independently of subprocess exit codes.
    required_summary, required_error = _junit_summary(output / "required-tests.xml")
    post_manifest, post_missing = _read_manifest(root)
    post_commit, post_commit_error = _git(root, "rev-parse", "HEAD")
    post_dirty, post_status_error = _git(root, "status", "--porcelain", "--untracked-files=all")
    postflight: list[str] = list(post_missing)
    if post_manifest != manifest:
        postflight.append("source_manifest_changed_during_validation")
    if post_commit_error or post_commit != commit:
        postflight.append("git_head_changed_during_validation")
    if post_status_error or post_dirty:
        postflight.append("git_worktree_changed_during_validation")
    if required_error:
        postflight.append(required_error)
    postflight.extend(_log_blockers(output, stages))
    result: dict[str, Any] = {
        "protocol": "NEUROAI_OFFLINE_GATE_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repository_commit": commit,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "source_sha256": manifest,
        "source_sha256_post": post_manifest,
        "preflight_blockers": blockers,
        "postflight_blockers": postflight,
        "mandatory_test_summary": required_summary,
        "stages": stages,
        "overall": "PASS"
        if not blockers and not postflight
        and all(v["status"] == "PASS" for v in stages.values())
        else "FAIL",
        "epistemic_scope": "LOCAL_CODE_AND_TOOL_EXECUTION_ONLY",
        "does_not_establish": [
            "general_truthfulness", "neuromodulation_performance",
            "production_safety", "external_replication",
        ],
    }
    manifest_file = output / "evidence.json"
    temp_path = output / "evidence.json.tmp"
    temp_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                         encoding="utf-8")
    temp_path.replace(manifest_file)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline fail-closed NeuroAI test gate")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output_dir or (
        Path(tempfile.gettempdir()) / "neosynaptex-offline-evidence" / uuid.uuid4().hex
    )
    try:
        verdict = execute_gate(root, output, timeout=args.timeout)
    except (ValueError, FileExistsError, OSError) as exc:
        print(f"GATE_ERROR:{exc}", file=sys.stderr)
        return 2
    print(f"{verdict['overall']} evidence={output / 'evidence.json'}")
    return 0 if verdict["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
