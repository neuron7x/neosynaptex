from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.eai.dopa_artifacts import claim_artifact_name, sha256_file, write_json
from core.eai.dopa_budget import BudgetLedger
from core.eai.dopa_construct_gate import ConstructContext, validate_construct_context
from core.eai.dopa_controls import run_controls
from core.eai.dopa_result import Err, Ok, Result
from core.eai.dopa_runtime_config import load_and_validate_config
from core.eai.dopa_types import ClaimSignal, FinalStatus, RouteMode

_SCHEMA_PATH = Path("schemas/dopa_closure_v2_config.schema.json")


def _git_head_sha() -> str:
    return (
        os.getenv("COMMIT_SHA")
        or os.getenv("GITHUB_SHA")
        or "UNSTAMPED:dopa_closure_v2"
    )


def _run_id() -> str:
    return os.getenv("DOPA_RUN_ID") or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )


class DopaClosureV2Allocator:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        loaded = load_and_validate_config(self.config_path, _SCHEMA_PATH)
        if isinstance(loaded, Err):
            raise ValueError(loaded.reason)
        self.config = loaded.value.payload
        self.config_hash = loaded.value.config_hash

    def priority_of_verification(
        self,
        claim: ClaimSignal,
        budget_ratio: float = 1.0,
    ) -> float:
        w = self.config["priority_gate"]["weights"]
        drive = (
            w["prediction_error"] * claim.prediction_error
            + w["uncertainty"] * claim.uncertainty
            + w["novelty"] * claim.novelty
            + w["evidence_risk"] * claim.evidence_risk
            + w["reversibility"] * (1.0 - claim.reversibility)
        )
        center = float(self.config["priority_gate"]["load_center"])
        spread = float(self.config["priority_gate"]["load_spread"])
        load_gate = max(0.0, 1.0 - ((claim.load - center) / (spread + 1e-9)) ** 2)
        budget_floor = max(0.0, min(1.0, budget_ratio))
        scarcity_boost = (1.0 - budget_floor) * claim.prediction_error * 0.35
        return max(0.0, float((drive + scarcity_boost) * load_gate))


def _provenance(config_path: str | Path, claims: list[ClaimSignal]) -> dict[str, str]:
    """Content-binding diagnostics, not independent verifier attestation."""
    encoded = json.dumps(
        [asdict(claim) for claim in claims],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "claims_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _write_config_snapshot(
    output: Path, config_path: str | Path, config_hash: str
) -> None:
    # Reject config change between validation and evidence snapshot.
    config_bytes = Path(config_path).read_bytes()
    if hashlib.sha256(config_bytes).hexdigest() != config_hash:
        raise ValueError("config_snapshot_hash_mismatch")
    (output / "config.sha256").write_text(config_hash + "\n", encoding="utf-8")
    (output / "config.yaml").write_bytes(config_bytes)


def _empty_budget_snapshot(cfg: dict[str, Any]) -> dict[str, float | bool | int]:
    envelope = float(cfg["budget"]["envelope"])
    return {
        "envelope": envelope,
        "probe_tax": float(cfg["budget"].get("probe_tax", 0.0)),
        "spent": 0.0,
        "remaining": envelope,
        "failure_streak": 0,
        "conserved": True,
    }


def _inadmissible_result(
    run_id: str,
    verdict: Any,
    allocator: DopaClosureV2Allocator,
    config_path: str | Path,
    claims: list[ClaimSignal],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "commit_sha": _git_head_sha(),
        "final_verdict": verdict.verdict,
        "failure_reasons": verdict.reasons,
        "config_hash": allocator.config_hash,
        "construct_gate": {
            **asdict(verdict),
            "scope": "ROUTING_ONLY",
            "evidence_level": "UNATTESTED_CALLER_DECLARATION",
        },
        "controls": asdict(run_controls([], [], seed=0)),
        "budget_ledger": _empty_budget_snapshot(allocator.config),
        "routes": [],
        "artifact_hashes": {},
        "provenance": _provenance(config_path, claims),
        "deferred_due_budget": 0,
    }


def _select_route_mode(
    claim: ClaimSignal,
    priority: float,
    thresholds: dict[str, Any],
) -> RouteMode:
    if claim.evidence_risk >= thresholds["reject_evidence_risk"]:
        return RouteMode.REJECT
    if priority >= thresholds["escalate"]:
        return RouteMode.ESCALATE
    if priority >= thresholds["verify"]:
        return RouteMode.VERIFY
    if priority >= thresholds["triage"]:
        return RouteMode.CHEAP_TRIAGE
    return RouteMode.QUARANTINE


def _final_status_for(mode: RouteMode) -> FinalStatus:
    return {
        RouteMode.REJECT: FinalStatus.REJECTED,
        RouteMode.ESCALATE: FinalStatus.ESCALATE,
        RouteMode.VERIFY: FinalStatus.VERIFY,
        RouteMode.CHEAP_TRIAGE: FinalStatus.CHEAP_TRIAGE,
        RouteMode.QUARANTINE: FinalStatus.QUARANTINED,
    }[mode]


def _failure_reasons(
    final_verdict: str,
    controls_doc: dict[str, Any],
    degraded: bool,
) -> list[str]:
    if final_verdict == "ADMISSIBLE":
        return []
    reasons: list[str] = []
    if not controls_doc["passed"]:
        reasons.append("controls_failed")
    if degraded:
        reasons.append("allocator_degradation_triggered")
    return reasons


def run_allocator_full_path(
    config_path: str | Path,
    claims: list[ClaimSignal],
    output_root: str | Path,
    construct_context: ConstructContext,
    *,
    claim_commitments: Mapping[str, str] | None = None,
) -> Result[dict[str, Any]]:
    """Optional precommitted claim-content hashes enable independent receipt checks.

    Uncommitted routes remain routing-only and cannot receive independent receipts.
    """
    try:
        allocator = DopaClosureV2Allocator(config_path)
    except ValueError as exc:
        return Err(str(exc))

    # A run identifier is a file-system component, not an arbitrary path.
    run_id = _run_id()
    if run_id in (".", "..") or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        return Err("invalid_run_id")
    if len({c.claim_id for c in claims}) != len(claims):
        return Err("duplicate_claim_ids")
    if claim_commitments is not None:
        claim_ids = {c.claim_id for c in claims}
        if set(claim_commitments) != claim_ids:
            return Err("claim_commitments_must_match_all_claim_ids")
        if any(not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
               for digest in claim_commitments.values()):
            return Err("invalid_claim_payload_digest")
    output = Path(output_root) / "runs" / run_id
    try:
        # Atomic exclusive creation prevents artifact clobbering on ID collisions.
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return Err("run_id_collision")
    verdict = validate_construct_context(construct_context)
    try:
        _write_config_snapshot(output, config_path, allocator.config_hash)
    except (OSError, ValueError) as exc:
        return Err(f"config_snapshot_failed:{exc}")
    write_json(output / "construct_gate.json", {
        **asdict(verdict),
        "scope": "ROUTING_ONLY",
        "evidence_level": "UNATTESTED_CALLER_DECLARATION",
    })
    if not verdict.admissible:
        final = _inadmissible_result(run_id, verdict, allocator, config_path, claims)
        write_json(output / "budget_ledger.json", final["budget_ledger"])
        write_json(output / "controls.json", final["controls"])
        write_json(output / "final_verdict.json", final)
        return Ok(final)

    cfg = allocator.config
    thresholds = cfg["priority_gate"]["thresholds"]
    costs = cfg["budget"]["action_costs"]
    ledger = BudgetLedger.create(
        float(cfg["budget"]["envelope"]),
        float(cfg["budget"].get("probe_tax", 0.0)),
        lambda_penalty=float(cfg["budget"].get("burn_rate_lambda", 0.0)),
    )
    routes: list[dict[str, Any]] = []
    priorities: list[float] = []
    artifact_hashes: dict[str, str] = {}
    deferred_due_budget = 0

    for claim in claims:
        budget_ratio = 0.0
        if float(ledger.envelope) > 0:
            budget_ratio = float(ledger.remaining / ledger.envelope)
        priority = allocator.priority_of_verification(claim, budget_ratio=budget_ratio)
        priorities.append(priority)

        desired_mode = _select_route_mode(claim, priority, thresholds)
        executed_mode = desired_mode
        unmet_verification_need = False
        quarantine_reason = None

        requested = float(costs[desired_mode.value])
        needs_budgeted_verification = desired_mode in (
            RouteMode.ESCALATE,
            RouteMode.VERIFY,
        )
        verify_unaffordable = needs_budgeted_verification and (
            requested + float(ledger.probe_tax) > float(ledger.remaining)
        )
        if verify_unaffordable:
            unmet_verification_need = True
            deferred_due_budget += 1
            quarantine_reason = "INSUFFICIENT_BUDGET_FOR_VERIFICATION"
            triage_cost = float(costs[RouteMode.CHEAP_TRIAGE.value])
            triage_cost += float(ledger.probe_tax)
            executed_mode = (
                RouteMode.CHEAP_TRIAGE
                if triage_cost <= float(ledger.remaining)
                else RouteMode.QUARANTINE
            )

        step = ledger.apply(
            float(costs[executed_mode.value]),
            float(costs[RouteMode.QUARANTINE.value]),
        )
        verification_result = "not_run"
        final_status = _final_status_for(executed_mode)

        if step.overspend:
            executed_mode = RouteMode.QUARANTINE
            final_status = FinalStatus.QUARANTINED
            quarantine_reason = "INSUFFICIENT_BUDGET"
        elif verify_unaffordable:
            final_status = _final_status_for(executed_mode)
        elif executed_mode == RouteMode.VERIFY:
            # Routing is not verification. An evidence-risk threshold cannot
            # manufacture a verifier result or authorize CLOSED.
            verification_result = "not_run"
            final_status = FinalStatus.VERIFY

        # No verifier ran in this path; do not treat deferred verification
        # as either successful closure or a failed independent verification.
        ledger.register_failure(False)

        claim_dir = output / "claims" / claim.claim_id
        artifact = claim_artifact_name(executed_mode.value, final_status.value)
        route_doc: dict[str, Any] = {
            "claim_id": claim.claim_id,
            "desired_route_mode": desired_mode.value,
            "route_mode": executed_mode.value,
            "epistemic_status": claim.epistemic_status,
            "final_status": final_status.value,
            "priority_of_verification": priority,
            "verification_result": verification_result,
            "quarantine_reason": quarantine_reason,
            "unmet_verification_need": unmet_verification_need,
            "budget": asdict(step),
            "config_hash": allocator.config_hash,
        }
        if claim_commitments is not None:
            route_doc["claim_payload_sha256"] = claim_commitments[claim.claim_id]
        write_json(claim_dir / artifact, route_doc)
        # Hashing a routing request would not constitute independent evidence.
        route_doc["verification_artifact_hash"] = None
        write_json(claim_dir / "route.json", route_doc)
        artifact_hashes[f"{claim.claim_id}/{artifact}"] = sha256_file(
            claim_dir / artifact
        )
        routes.append(route_doc)

    controls_doc = asdict(
        run_controls(
            claims,
            priorities,
            seed=int(cfg["negative_controls"]["random_routing_seed"]),
        )
    )
    write_json(output / "controls.json", controls_doc)
    random_u = controls_doc.get("random_routing_mean_priority", 0.0)
    allocator_u = sum(priorities) / max(1, len(priorities))
    degradation_triggered = allocator_u <= random_u
    # Diagnostic proxy controls may inform routing development, but without
    # a separately executed, qualified verifier the closure instrument is
    # categorically INADMISSIBLE, regardless of internal priority scores.
    final_verdict = "INADMISSIBLE"
    result: dict[str, Any] = {
        "run_id": run_id,
        "commit_sha": _git_head_sha(),
        "final_verdict": final_verdict,
        "failure_reasons": [
            "independent_verifier_not_executed",
            "construct_context_not_independently_attested",
            *_failure_reasons(final_verdict, controls_doc, degradation_triggered),
        ],
        "config_hash": allocator.config_hash,
        "construct_gate": asdict(verdict),
        "controls": controls_doc,
        "budget_ledger": ledger.snapshot(),
        "deferred_due_budget": deferred_due_budget,
        "routes": routes,
        "artifact_hashes": artifact_hashes,
        "provenance": _provenance(config_path, claims),
    }
    write_json(output / "budget_ledger.json", result["budget_ledger"])
    write_json(output / "final_verdict.json", result)
    return Ok(result)
