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

_SOURCE_PATHS = (
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
        ("ruff", ("-m", "ruff", "check", *_LINT_PATHS)),
        ("mypy", ("-m", "mypy", *_MYPY_PATHS)),
    )


def _run(root: Path, name: str, args: tuple[str, ...],
         output: Path, timeout: int) -> dict[str, Any]:
    command = [sys.executable, *args]
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
    result: dict[str, Any] = {
        "protocol": "NEUROAI_OFFLINE_GATE_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repository_commit": commit,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "source_sha256": manifest,
        "preflight_blockers": blockers,
        "stages": stages,
        "overall": "PASS"
        if not blockers and all(v["status"] == "PASS" for v in stages.values())
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
