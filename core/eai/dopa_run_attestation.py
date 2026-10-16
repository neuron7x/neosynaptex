"""Optional keyed provenance for DOPA arithmetic verification runs.

This authenticates archived inputs, not claim correctness or DNCA calibration.
Keep the HMAC key isolated from the untrusted agent and routing process.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

_ATTEST_DOMAIN = "dopa.route-attestation.v1"
_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_MAX_BYTES = 8 * 1024 * 1024


def _id(value: str) -> str:
    if not isinstance(value, str) or value in (".", "..") or not _SAFE.fullmatch(value):
        raise ValueError("invalid_attestation_identifier")
    return value


def _key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("attestation_key_requires_32_random_bytes")
    return key


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("utf-8")


def _blob(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("untrusted_attestation_input")
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("oversize_attestation_input")
    raw = path.read_bytes()
    if len(raw) > _MAX_BYTES:
        raise ValueError("oversize_attestation_input")
    return raw


def _pairs_no_dup(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate_attestation_json_key")
        out[k] = v
    return out


def _json(path: Path) -> dict[str, Any]:
    def _constant(_: str) -> None:
        raise ValueError("nonfinite_attestation_json")
    obj = json.loads(_blob(path), object_pairs_hook=_pairs_no_dup,
                     parse_constant=_constant)
    if not isinstance(obj, dict):
        raise ValueError("invalid_attestation_json_object")
    return obj


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _inputs(run_dir: Path, claim_id: str) -> dict[str, str]:
    _id(run_dir.name)
    _id(claim_id)
    claim_dir = run_dir / "claims" / claim_id
    if any(p.is_symlink() or not p.is_dir() for p in
           (run_dir, run_dir / "claims", claim_dir)):
        raise ValueError("untrusted_attestation_directory")
    report = _json(run_dir / "final_verdict.json")
    route = _json(claim_dir / "route.json")
    config = _blob(run_dir / "config.yaml")
    config_digest = _digest(config)
    expected = (run_dir / "config.sha256").read_text(encoding="ascii").strip()
    if expected != config_digest or report.get("config_hash") != config_digest:
        raise ValueError("attestation_config_digest_mismatch")
    if report.get("run_id") != run_dir.name:
        raise ValueError("attestation_run_id_mismatch")
    if report.get("final_verdict") != "INADMISSIBLE":
        raise ValueError("attestation_instrument_state_mismatch")
    routes = report.get("routes")
    if not isinstance(routes, list):
        raise ValueError("attestation_routes_missing")
    matched = [r for r in routes if isinstance(r, dict) and r.get("claim_id") == claim_id]
    if len(matched) != 1 or matched[0] != route:
        raise ValueError("attestation_route_report_mismatch")
    commitment = route.get("claim_payload_sha256")
    if not isinstance(commitment, str) or not re.fullmatch(r"[a-f0-9]{64}", commitment):
        raise ValueError("attestation_claim_commitment_missing")
    return {
        "domain": _ATTEST_DOMAIN,
        "run_id": run_dir.name,
        "claim_id": claim_id,
        "claim_payload_sha256": commitment,
        "report_sha256": _digest(_blob(run_dir / "final_verdict.json")),
        "route_sha256": _digest(_blob(claim_dir / "route.json")),
        "config_sha256": config_digest,
    }


def _atomic_create(path: Path, payload: dict[str, Any]) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("untrusted_attestation_parent")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".attest-",
                                     suffix=".tmp", delete=False) as file:
        temp = Path(file.name)
        try:
            os.chmod(temp, 0o600)
            file.write(_canonical(payload) + b"\n")
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def seal_arithmetic_run(run_dir: str | Path, claim_id: str, key: bytes) -> dict[str, Any]:
    """Trusted-controller action ONLY; isolate the key from the untrusted agent."""
    k = _key(key)
    root = Path(run_dir)
    signed = _inputs(root, claim_id)
    tag = hmac.new(k, _canonical(signed), hashlib.sha256).hexdigest()
    record: dict[str, Any] = {"payload": signed, "mac_sha256": tag}
    _atomic_create(root / "claims" / claim_id / "route_attestation.json", record)
    return record


def verify_arithmetic_run_attestation(
    run_dir: str | Path, claim_id: str, key: bytes,
) -> dict[str, str]:
    """Authenticate a run/claim/config tuple; reject any archive drift."""
    k = _key(key)
    root = Path(run_dir)
    expected = _inputs(root, claim_id)
    record = _json(root / "claims" / claim_id / "route_attestation.json")
    if set(record) != {"payload", "mac_sha256"} or record["payload"] != expected:
        raise ValueError("attestation_payload_mismatch")
    tag = record["mac_sha256"]
    if not isinstance(tag, str) or not re.fullmatch(r"[a-f0-9]{64}", tag):
        raise ValueError("malformed_attestation_mac")
    computed = hmac.new(k, _canonical(expected), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(tag, computed):
        raise ValueError("attestation_mac_invalid")
    return {"status": "HMAC_AUTHENTICATED",
            "attestation_sha256": _digest(_canonical(record))}
