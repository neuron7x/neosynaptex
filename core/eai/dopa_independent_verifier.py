"""Independent, exact integer arithmetic verifier for DOPA routing experiments.

No neural signal or risk score influences this verdict. This fixture proves
only bounded integer arithmetic, not general factual truth or model quality.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from core.eai.dopa_run_attestation import verify_arithmetic_run_attestation

_DOMAIN = "dopa.arithmetic.v1"
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_OPERATIONS = {"add", "subtract", "multiply"}
_BOUND = 1_000_000_000
_MAX_JSON_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class ArithmeticClaim:
    claim_id: str
    operation: str
    left: int
    right: int
    asserted: int

    def __post_init__(self) -> None:
        if not isinstance(self.claim_id, str) or not _SAFE_ID.fullmatch(self.claim_id):
            raise ValueError("invalid_claim_id")
        if self.claim_id in (".", ".."):
            raise ValueError("invalid_claim_id")
        if self.operation not in _OPERATIONS:
            raise ValueError("unsupported_operation")
        for key in ("left", "right", "asserted"):
            v = getattr(self, key)
            if type(v) is not int or abs(v) > _BOUND * _BOUND:
                raise ValueError(f"invalid_{key}")
        if abs(self.left) > _BOUND or abs(self.right) > _BOUND:
            raise ValueError("operand_limit_exceeded")


def canonical_json_bytes(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def arithmetic_commitment(claim: ArithmeticClaim) -> str:
    """Bind claim semantics, not just its user-supplied identifier."""
    payload = {"domain": _DOMAIN, "claim": asdict(claim)}
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _deny_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate_json_key")
        obj[key] = value
    return obj


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > _MAX_JSON_BYTES:
        raise ValueError("untrusted_or_oversize_evidence")
    def _bad_constant(value: str) -> None:
        raise ValueError("nonfinite_json_constant")
    result = json.loads(path.read_text(encoding="utf-8"),
                        object_pairs_hook=_deny_duplicates,
                        parse_constant=_bad_constant)
    if not isinstance(result, dict):
        raise ValueError("invalid_json_object")
    return result


def _exact_arithmetic(claim: ArithmeticClaim) -> int:
    if claim.operation == "add":
        return claim.left + claim.right
    if claim.operation == "subtract":
        return claim.left - claim.right
    return claim.left * claim.right


def _preflight(run_dir: Path, claim: ArithmeticClaim) -> tuple[dict[str, Any], dict[str, Any]]:
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("untrusted_run_directory")
    if not _SAFE_ID.fullmatch(run_dir.name) or run_dir.name in (".", ".."):
        raise ValueError("invalid_run_id")
    if (run_dir / "claims").is_symlink() or (run_dir / "claims" / claim.claim_id).is_symlink():
        raise ValueError("untrusted_claims_directory")
    report = _load_json(run_dir / "final_verdict.json")
    if report.get("final_verdict") != "INADMISSIBLE":
        raise ValueError("unexpected_instrument_state")
    if report.get("run_id") != run_dir.name:
        raise ValueError("run_id_mismatch")
    routes = report.get("routes")
    if not isinstance(routes, list):
        raise ValueError("missing_routes")
    matches = [r for r in routes if isinstance(r, dict) and r.get("claim_id") == claim.claim_id]
    if len(matches) != 1:
        raise ValueError("missing_or_ambiguous_route")
    route_path = run_dir / "claims" / claim.claim_id / "route.json"
    route = _load_json(route_path)
    if route != matches[0] or route.get("config_hash") != report.get("config_hash"):
        raise ValueError("route_report_mismatch")
    if route.get("claim_payload_sha256") != arithmetic_commitment(claim):
        raise ValueError("claim_payload_commitment_mismatch")
    if route.get("route_mode") not in ("verify", "escalate"):
        raise ValueError("not_scheduled_for_verification")
    if route.get("final_status") not in ("VERIFY", "ESCALATE"):
        raise ValueError("not_pending_verification")
    if route.get("verification_result") != "not_run":
        raise ValueError("already_verification_marked")
    if route.get("unmet_verification_need") is not False:
        raise ValueError("verification_budget_unavailable")
    budget = route.get("budget")
    if not isinstance(budget, dict) or budget.get("overspend") is not False:
        raise ValueError("budget_overspend_or_missing")
    return report, route


def _exclusive_write(path: Path, payload: dict[str, Any]) -> None:
    """Atomic no-overwrite publication; even a symlink at target blocks the link."""
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("untrusted_receipt_parent")
    raw = canonical_json_bytes(payload) + b"\n"
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".receipt-",
                                     suffix=".tmp", delete=False) as fp:
        tmp = Path(fp.name)
        os.chmod(tmp, 0o600)
        try:
            fp.write(raw)
            fp.flush()
            os.fsync(fp.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.link(tmp, path)  # fails when target already exists; no replacement
    finally:
        tmp.unlink(missing_ok=True)


def verify_scheduled_arithmetic(
    run_dir: str | Path,
    claim: ArithmeticClaim,
    *,
    attestation_key: bytes | None = None,
) -> dict[str, Any]:
    """Independently recompute a precommitted, eligible claim and publish receipt.

    A hash is an integrity commitment, not a signature or authority guarantee.
    Publication is scoped to the exact integer task only. This function never
    edits the allocator's original report or changes its INADMISSIBLE status.
    """
    path = Path(run_dir)
    report, route = _preflight(path, claim)
    # This stronger path authenticates the *archive origin*, not factual truth.
    # The key must be independently provisioned in a separate trust domain.
    attestation = (
        verify_arithmetic_run_attestation(path, claim.claim_id, attestation_key)
        if attestation_key is not None else
        {"status": "UNATTESTED", "attestation_sha256": None}
    )
    computed = _exact_arithmetic(claim)
    verdict = "VERIFIED" if computed == claim.asserted else "REFUTED"
    receipt: dict[str, Any] = {
        "domain": _DOMAIN,
        "scope": "EXACT_INTEGER_ARITHMETIC_ONLY",
        "run_id": report["run_id"],
        "claim_id": claim.claim_id,
        "claim_payload_sha256": arithmetic_commitment(claim),
        "route_sha256": hashlib.sha256(canonical_json_bytes(route)).hexdigest(),
        "config_hash": report["config_hash"],
        "verifier": "stdlib_exact_integer_recomputation_v1",
        "computed": computed,
        "asserted": claim.asserted,
        "verdict": verdict,
        "archive_authentication": attestation["status"],
        "attestation_sha256": attestation["attestation_sha256"],
        "does_not_attest": ["general_truthfulness", "dnca_value_validity", "model_accuracy"],
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()
    _exclusive_write(path / "claims" / claim.claim_id / "verification_receipt.json", receipt)
    return receipt
