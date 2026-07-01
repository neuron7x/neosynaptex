from __future__ import annotations

import hashlib
import json
import subprocess  # nosec B404  # argv-list runner for verifier protocols; no shell.
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class VerificationReport:
    verifier_id: str
    claim_id: str
    verification_type: str
    status: str
    command_or_query: str
    environment: str
    network: str
    stdout_hash: str
    stderr_hash: str
    artifact_hash: str
    timestamp_utc: str
    boundary: str
    report_hash: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _report_payload(report: VerificationReport) -> dict[str, str]:
    payload = asdict(report).copy()
    payload.pop("report_hash", None)
    payload.pop("timestamp_utc", None)
    return payload


def compute_report_hash(report: VerificationReport) -> str:
    canonical = json.dumps(_report_payload(report), sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical)


def run_local_command(
    claim_id: str,
    command: list[str],
    verification_type: str = "software_protocol",
    timeout_sec: int = 10,
) -> VerificationReport:
    try:
        proc = subprocess.run(  # nosec B603  # argv list, shell=False, deterministic local verifier
            command,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        status = "PASS" if proc.returncode == 0 else "FAIL"
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        status = "FAIL"

        def _as_text(raw: bytes | str | None) -> str:
            if raw is None:
                return ""
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace")
            return raw

        stdout = _as_text(exc.stdout)
        stderr = _as_text(exc.stderr) + f"\nTIMEOUT after {timeout_sec}s"

    stdout_hash = sha256_text(stdout)
    stderr_hash = sha256_text(stderr)
    artifact_hash = sha256_text(stdout_hash + stderr_hash + " ".join(command))

    report = VerificationReport(
        verifier_id="docker_pytest_v0",
        claim_id=claim_id,
        verification_type=verification_type,
        status=status,
        command_or_query=" ".join(command),
        environment="local-subprocess",
        network="disabled",
        stdout_hash=stdout_hash,
        stderr_hash=stderr_hash,
        artifact_hash=artifact_hash,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        boundary="local deterministic verification only",
        report_hash="",
    )
    report.report_hash = compute_report_hash(report)
    return report


def write_report(path: str, report: VerificationReport) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, sort_keys=True)
