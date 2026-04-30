"""Artifact signing and verification using Ed25519 via the ``cryptography`` library.

Replaces the custom Ed25519 implementation (crypto/signatures.py, 592 LOC)
with the audited, maintained ``cryptography.hazmat`` backend.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

_logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError:  # cryptography is optional (crypto extra)
    Ed25519PrivateKey = None  # type: ignore[assignment,misc]
    Ed25519PublicKey = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass
class _KeyPair:
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey
    public_key_bytes: bytes


def _reject_traversal(p: str | Path) -> Path:
    """Defense-in-depth: reject paths with ``..`` segments.

    Caller-supplied paths in this module flow from operator-controlled
    deployment config (artifact roots, audit-log paths), not from
    adversarial input. This guard exists to catch accidental traversal
    in misconfigured deployments. ``.resolve()`` was deliberately removed
    after PR #164 — it added new CodeQL py/path-injection sinks without
    closing the original alerts (CodeQL's barriers do not include
    ``Path.resolve()``). The original parameter→sink flow is dismissed
    in the security tab as not-exploitable under this admin-controlled
    threat model.
    """
    raw = os.fspath(p)
    if ".." in Path(raw).parts:
        raise ValueError(f"path traversal disallowed: {raw!r}")
    return Path(raw)


def sha256_file(path: str | Path) -> str:
    safe_path = _reject_traversal(path)
    h = hashlib.sha256()
    with safe_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _derive_keypair_from_seed(seed_text: str) -> _KeyPair:
    """Derive Ed25519 keypair from a deterministic seed string.

    Uses SHA256 of the seed as the 32-byte private key material.
    This is compatible with the ``cryptography`` library's
    ``Ed25519PrivateKey.from_private_bytes()``.
    """
    seed_bytes = hashlib.sha256(seed_text.encode("utf-8")).digest()
    private_key = Ed25519PrivateKey.from_private_bytes(seed_bytes)
    public_key = private_key.public_key()
    public_key_bytes = public_key.public_bytes_raw()
    return _KeyPair(
        private_key=private_key,
        public_key=public_key,
        public_key_bytes=public_key_bytes,
    )


def _sign_message(message: bytes, private_key: Ed25519PrivateKey) -> bytes:
    """Sign a message with Ed25519."""
    return private_key.sign(message)


def _verify_signature(message: bytes, signature: bytes, public_key_bytes: bytes) -> bool:
    """Verify an Ed25519 signature."""
    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, message)
        return True
    except Exception:
        return False


def _crypto_config_seed(config_path: str | Path) -> str:
    # Prefer environment variable for per-deployment uniqueness
    env_seed = os.environ.get("MFN_ARTIFACT_SEED")
    if env_seed:
        return env_seed

    try:
        text = Path(config_path).read_text(encoding="utf-8")
        match = re.search(r'deterministic_artifact_seed:\s*"?([^"\n]+)"?', text)
        if match:
            seed = match.group(1).strip()
            if seed == "mfn-artifact-signing-v1":
                _logger.warning(
                    "Using default artifact signing seed. Set MFN_ARTIFACT_SEED "
                    "env var for per-deployment key uniqueness."
                )
            return seed
    except FileNotFoundError:
        pass
    _logger.warning(
        "No artifact signing seed configured. Using default. "
        "Set MFN_ARTIFACT_SEED for production deployments."
    )
    return "mfn-artifact-signing-v1"


def _append_audit_event(audit_log: str | Path, event: dict[str, Any]) -> None:
    safe_log = _reject_traversal(audit_log)
    safe_log.parent.mkdir(parents=True, exist_ok=True)
    with safe_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def sign_artifact(
    path: str | Path,
    *,
    config_path: str | Path,
    audit_log: str | Path | None = None,
) -> Path:
    artifact_path = _reject_traversal(path)
    keypair = _derive_keypair_from_seed(_crypto_config_seed(config_path))
    digest = sha256_file(artifact_path)
    signature = _sign_message(digest.encode("utf-8"), keypair.private_key)
    payload = {
        "schema_version": "mfn-artifact-signature-v1",
        "algorithm": "Ed25519",
        "path": artifact_path.name,
        "sha256": digest,
        "signature_hex": signature.hex(),
        "public_key_hex": keypair.public_key_bytes.hex(),
        "signed_at": datetime.now(timezone.utc).isoformat(),
    }
    sig_path = artifact_path.with_suffix(artifact_path.suffix + ".sig.json")
    sig_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if audit_log is not None:
        _append_audit_event(
            audit_log,
            {
                "event": "sign",
                "path": str(artifact_path),
                "sha256": digest,
                "signature_path": str(sig_path),
                "timestamp": payload["signed_at"],
            },
        )
    return sig_path


def verify_artifact_signature(
    path: str | Path,
    *,
    signature_path: str | Path | None = None,
    audit_log: str | Path | None = None,
) -> bool:
    artifact_path = _reject_traversal(path)
    sig_path = (
        _reject_traversal(signature_path)
        if signature_path is not None
        else artifact_path.with_suffix(artifact_path.suffix + ".sig.json")
    )
    payload = json.loads(sig_path.read_text(encoding="utf-8"))
    digest = sha256_file(artifact_path)
    ok = digest == payload["sha256"] and _verify_signature(
        digest.encode("utf-8"),
        bytes.fromhex(payload["signature_hex"]),
        bytes.fromhex(payload["public_key_hex"]),
    )
    if audit_log is not None:
        _append_audit_event(
            audit_log,
            {
                "event": "verify",
                "path": str(artifact_path),
                "signature_path": str(sig_path),
                "sha256": digest,
                "ok": bool(ok),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    return bool(ok)


def sign_artifacts(
    paths: Iterable[str | Path],
    *,
    config_path: str | Path,
    audit_log: str | Path | None = None,
) -> list[dict[str, str]]:
    signed = []
    for path in paths:
        sig_path = sign_artifact(path, config_path=config_path, audit_log=audit_log)
        signed.append({"artifact": Path(path).name, "signature": sig_path.name})
    return signed


def _verify_default_signature_if_present(target: Path, failures: list[str]) -> None:
    sig_path = target.with_suffix(target.suffix + ".sig.json")
    if not sig_path.exists():
        return
    if not verify_artifact_signature(target, signature_path=sig_path):
        failures.append(f"signature-invalid:{target.name}")


def manifest_entries_ok(manifest_path: str | Path) -> tuple[bool, list[str]]:
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    if path.name == "manifest.json":
        for section in ("artifact_manifest", "optional_artifact_manifest"):
            for entry in (
                data.get(section, {}).values()
                if isinstance(data.get(section), dict)
                else data.get(section, [])
            ):
                rel = entry["path"]
                target = path.parent / rel
                if not target.exists():
                    failures.append(f"missing:{rel}")
                    continue
                actual = sha256_file(target)
                if actual != entry["sha256"]:
                    failures.append(f"sha256-mismatch:{rel}")
                _verify_default_signature_if_present(target, failures)
    else:
        for entry in data.get("bundle_artifacts", []):
            rel = entry["path"]
            target = path.parent / rel
            if not target.exists():
                failures.append(f"missing:{rel}")
                continue
            actual = sha256_file(target)
            if actual != entry["sha256"]:
                failures.append(f"sha256-mismatch:{rel}")
            _verify_default_signature_if_present(target, failures)
    _verify_default_signature_if_present(path, failures)
    for entry in data.get("signatures", []):
        artifact = path.parent / entry["artifact"]
        signature_path = path.parent / entry["signature"]
        if not artifact.exists() or not signature_path.exists():
            failures.append(f"missing-signature:{entry}")
            continue
        if not verify_artifact_signature(artifact, signature_path=signature_path):
            failures.append(f"signature-invalid:{entry['artifact']}")
    return len(failures) == 0, failures


def verify_bundle(root_or_manifest: str | Path) -> dict[str, Any]:
    root = Path(root_or_manifest)
    manifests: list[Path]
    if root.is_file():
        manifests = [root]
    else:
        candidates = [
            root / "manifest.json",
            root / "release_manifest.json",
            root / "showcase_manifest.json",
        ]
        manifests = [item for item in candidates if item.exists()]
        if not manifests:
            manifests = (
                list(root.rglob("manifest.json"))
                + list(root.rglob("release_manifest.json"))
                + list(root.rglob("showcase_manifest.json"))
            )
    results = []
    ok = True
    for manifest in manifests:
        manifest_ok, failures = manifest_entries_ok(manifest)
        ok = ok and manifest_ok
        results.append({"manifest": str(manifest), "ok": manifest_ok, "failures": failures})
    return {"ok": ok, "manifests": results}


__all__ = [
    "sha256_file",
    "sign_artifact",
    "sign_artifacts",
    "verify_artifact_signature",
    "verify_bundle",
]
