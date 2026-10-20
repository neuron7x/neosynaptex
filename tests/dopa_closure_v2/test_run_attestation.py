"""Adversarial tests of keyed route/config/report provenance.

All keys in this module are TEST VECTORS, not deployment secrets.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.eai.dopa_run_attestation import (
    seal_arithmetic_run,
    verify_arithmetic_run_attestation,
)

TEST_KEY = b"k" * 32


def _run(tmp_path: Path) -> Path:
    root = tmp_path / "runs" / "run-1"
    claim_dir = root / "claims" / "c-1"
    claim_dir.mkdir(parents=True)
    config = b"a: test\n"
    digest = hashlib.sha256(config).hexdigest()
    (root / "config.yaml").write_bytes(config)
    (root / "config.sha256").write_text(digest + "\n", encoding="utf-8")
    route = {
        "claim_id": "c-1",
        "config_hash": digest,
        "claim_payload_sha256": "a" * 64,
        "route_mode": "verify",
        "final_status": "VERIFY",
    }
    (claim_dir / "route.json").write_text(json.dumps(route), encoding="utf-8")
    (root / "final_verdict.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "config_hash": digest,
                "final_verdict": "INADMISSIBLE",
                "routes": [route],
            }
        ),
        encoding="utf-8",
    )
    return root


def test_valid_key_binds_entire_run(tmp_path: Path) -> None:
    root = _run(tmp_path)
    sealed = seal_arithmetic_run(root, "c-1", TEST_KEY)
    outcome = verify_arithmetic_run_attestation(root, "c-1", TEST_KEY)
    assert len(sealed["mac_sha256"]) == 64
    assert outcome["status"] == "HMAC_AUTHENTICATED"
    assert len(outcome["attestation_sha256"]) == 64


def test_wrong_key_does_not_authorize(tmp_path: Path) -> None:
    root = _run(tmp_path)
    seal_arithmetic_run(root, "c-1", TEST_KEY)
    with pytest.raises(ValueError, match="attestation_mac_invalid"):
        verify_arithmetic_run_attestation(root, "c-1", b"x" * 32)


def test_missing_attestation_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        verify_arithmetic_run_attestation(_run(tmp_path), "c-1", TEST_KEY)


@pytest.mark.parametrize(
    "filename,replace_from,replace_to",
    [
        ("final_verdict.json", "VERIFY", "ESCALATE"),
        ("claims/c-1/route.json", "VERIFY", "ESCALATE"),
        ("config.yaml", "test", "evil"),
    ],
)
def test_tampering_fails(tmp_path: Path, filename: str, replace_from: str, replace_to: str) -> None:
    root = _run(tmp_path)
    seal_arithmetic_run(root, "c-1", TEST_KEY)
    path = root / filename
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            replace_from,
            replace_to,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        verify_arithmetic_run_attestation(root, "c-1", TEST_KEY)


def test_replayed_seal_cannot_replace_original(tmp_path: Path) -> None:
    root = _run(tmp_path)
    seal_arithmetic_run(root, "c-1", TEST_KEY)
    target = root / "claims" / "c-1" / "route_attestation.json"
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        seal_arithmetic_run(root, "c-1", TEST_KEY)
    assert target.read_bytes() == before


def test_forged_signature_fails(tmp_path: Path) -> None:
    root = _run(tmp_path)
    seal_arithmetic_run(root, "c-1", TEST_KEY)
    target = root / "claims" / "c-1" / "route_attestation.json"
    original = json.loads(target.read_text(encoding="utf-8"))
    original["mac_sha256"] = "0" * 64
    target.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="attestation_mac_invalid"):
        verify_arithmetic_run_attestation(root, "c-1", TEST_KEY)


def test_short_key_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="32_random_bytes"):
        seal_arithmetic_run(_run(tmp_path), "c-1", b"short")


def test_consistent_tampering_of_report_and_route_fails(tmp_path: Path) -> None:
    root = _run(tmp_path)
    seal_arithmetic_run(root, "c-1", TEST_KEY)
    path = root / "claims" / "c-1" / "route.json"
    route = json.loads(path.read_text(encoding="utf-8"))
    route["priority"] = "forged"
    path.write_text(json.dumps(route), encoding="utf-8")
    report_path = root / "final_verdict.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["routes"][0] = route
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="attestation_payload_mismatch"):
        verify_arithmetic_run_attestation(root, "c-1", TEST_KEY)


def test_symlinked_archive_input_rejected(tmp_path: Path) -> None:
    root = _run(tmp_path)
    seal_arithmetic_run(root, "c-1", TEST_KEY)
    path = root / "final_verdict.json"
    original = root / "original.json"
    path.rename(original)
    path.symlink_to(original)
    with pytest.raises(ValueError, match="untrusted_attestation_input"):
        verify_arithmetic_run_attestation(root, "c-1", TEST_KEY)
