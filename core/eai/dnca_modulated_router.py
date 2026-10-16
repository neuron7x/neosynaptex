"""DNCA -> DOPA-CLOSURE v2 routing-only boundary.

Neuromodulator signals change *verification priority*, never truth.
No route from this module can emit CLOSED / VERIFIED.
Scientific status: experimental; DNCA vRPE predictive utility unvalidated.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.eai.dopa_budget import BudgetLedger
from core.eai.dopa_closure_v2 import DopaClosureV2Allocator
from core.eai.dopa_construct_gate import ConstructContext, validate_construct_context
from core.eai.dopa_result import Err, Ok, Result
from core.eai.dopa_types import ClaimSignal, RouteMode

DEFAULT_CONFIG = "configs/dopa_closure_v2/allocator.yaml"


def _scalar(name: str, obj: Any, *, signed: bool = False) -> float:
    """Require one finite scalar; reject silent tensor truncation and NaNs."""
    if hasattr(obj, "numel"):
        if obj.numel() != 1:
            raise ValueError(f"{name}_not_scalar")
        obj = obj.detach().item()
    if isinstance(obj, bool) or not isinstance(obj, (int, float)):
        raise ValueError(f"{name}_not_numeric")
    value = float(obj)
    if not math.isfinite(value):
        raise ValueError(f"{name}_not_finite")
    if not (-1.0 <= value <= 1.0 if signed else 0.0 <= value <= 1.0):
        raise ValueError(f"{name}_outside_bounds")
    return value


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    """Independent claim metadata; never inferred from DA/5-HT."""
    claim_id: str
    uncertainty: float
    novelty: float
    evidence_risk: float
    reversibility: float
    load: float
    epistemic_status: str = "unknown"

    def to_claim(self, prediction_error: float) -> ClaimSignal:
        return ClaimSignal(
            self.claim_id, prediction_error, self.uncertainty, self.novelty,
            self.evidence_risk, self.reversibility, self.load, self.epistemic_status,
        )


@dataclass(frozen=True, slots=True)
class DNCAObservation:
    """Detached projection of a genuine DNCA shared predictive state."""
    prediction_error: float
    signed_valence: float
    dopamine_signal: float
    inhibition_signal: float
    step: int


def observe_sps(snapshot: Mapping[str, Any]) -> DNCAObservation:
    """Extract observables; not by itself proof of DNCA provenance."""
    try:
        step = snapshot["step"]
        if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
            raise ValueError("dnca_step_missing_or_unexecuted")
        pe = snapshot["prediction_error"]
        if not hasattr(pe, "detach") or not hasattr(pe, "numel") or pe.numel() < 1:
            raise ValueError("prediction_error_tensor_missing")
        detached = pe.detach().float()
        magnitude = float(detached.norm().item())
        if not math.isfinite(magnitude):
            raise ValueError("prediction_error_not_finite")
        return DNCAObservation(
            prediction_error=magnitude / (1.0 + magnitude),
            signed_valence=_scalar("valence", snapshot["valence"], signed=True),
            dopamine_signal=_scalar("dopamine", snapshot["dopamine_signal"], signed=True),
            inhibition_signal=_scalar("inhibition", snapshot["inhibition_signal"]),
            step=step,
        )
    except KeyError as exc:
        raise ValueError(f"missing_sps_field:{exc.args[0]}") from exc


def route_observation(
    observation: DNCAObservation,
    claims: Sequence[EvidenceInput],
    construct_context: ConstructContext,
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    dopamine_gain: float = 0.0,
    inhibition_threshold: float = 0.8,
) -> Result[dict[str, Any]]:
    """Experimental *global regime* routing; cannot perform claimwise salience.

    Gain=0 is the control. A single shared valence is applied equally to every
    claim: at identical fixed baseline priorities it cannot strictly reorder
    claims (although clipping creates ties and threshold/ledger effects differ).
    Both arms share evidence inputs, costs, verification criteria and gates.
    No independent verifier runs in this function.
    """
    try:
        gain = _scalar("dopamine_gain", dopamine_gain)
        hold_at = _scalar("inhibition_threshold", inhibition_threshold)
        if gain > 0.25:
            raise ValueError("dopamine_gain_above_experimental_cap")
        if observation.step <= 0:
            raise ValueError("unexecuted_dnca_observation")
        for key in ("prediction_error", "signed_valence", "dopamine_signal", "inhibition_signal"):
            _scalar(key, getattr(observation, key), signed=key in ("signed_valence", "dopamine_signal"))
        signals = [item.to_claim(observation.prediction_error) for item in claims]
        if len({c.claim_id for c in signals}) != len(signals):
            raise ValueError("duplicate_claim_ids")
        allocator = DopaClosureV2Allocator(config_path)
        verdict = validate_construct_context(construct_context)
        cfg = allocator.config
        ledger = BudgetLedger.create(
            float(cfg["budget"]["envelope"]),
            float(cfg["budget"].get("probe_tax", 0.0)),
            lambda_penalty=float(cfg["budget"].get("burn_rate_lambda", 0.0)),
        )
        if not verdict.admissible:
            return Ok({
                "status": "INSTRUMENT_INADMISSIBLE",
                "reasons": verdict.reasons,
                "routes": [],
                "budget_ledger": ledger.snapshot(),
                "closure_count": 0,
                "signal_validity": "UNTESTED",
                "modulation_scope": "GLOBAL_THRESHOLD_SHIFT_NOT_CLAIM_SPECIFIC",
            })
        thresholds = cfg["priority_gate"]["thresholds"]
        costs = cfg["budget"]["action_costs"]
        routes: list[dict[str, Any]] = []
        for claim in signals:
            remaining = float(ledger.remaining)
            envelope = float(ledger.envelope)
            base = allocator.priority_of_verification(
                claim, budget_ratio=(remaining / envelope if envelope > 0 else 0.0)
            )
            priority = max(0.0, base + gain * observation.signed_valence)
            if observation.inhibition_signal >= hold_at:
                mode = RouteMode.QUARANTINE
                reason = "INHIBITION_HOLD"
            elif claim.evidence_risk >= thresholds["reject_evidence_risk"]:
                mode, reason = RouteMode.REJECT, "EVIDENCE_RISK"
            elif priority >= thresholds["escalate"]:
                mode, reason = RouteMode.ESCALATE, "PRIORITY"
            elif priority >= thresholds["verify"]:
                mode, reason = RouteMode.VERIFY, "PRIORITY"
            elif priority >= thresholds["triage"]:
                mode, reason = RouteMode.CHEAP_TRIAGE, "PRIORITY"
            else:
                mode, reason = RouteMode.QUARANTINE, "LOW_PRIORITY"
            # Ledger is a reservation for later verification, not evidence of execution.
            budget = ledger.apply(
                float(costs[mode.value]), float(costs[RouteMode.QUARANTINE.value])
            )
            if budget.overspend:
                mode, reason = RouteMode.QUARANTINE, "INSUFFICIENT_BUDGET"
            routes.append({
                "claim_id": claim.claim_id,
                "mode": mode.value,
                "reason": reason,
                "priority": priority,
                "verification_result": "not_run",
                "epistemic_status": claim.epistemic_status,
                "reserved_budget": asdict(budget),
            })
            ledger.register_failure(False)  # Reservation is not verifier failure.
        return Ok({
            "status": "ROUTING_ONLY",
            "source": "UNTRUSTED_SPS_PROJECTION",
            "dnca_step": observation.step,
            "signal_validity": "UNTESTED",
            "modulation_scope": "GLOBAL_THRESHOLD_SHIFT_NOT_CLAIM_SPECIFIC",
            "claim_specific_signal_qualified": False,
            "dopamine_gain": gain,
            "closure_count": 0,
            "routes": routes,
            "budget_ledger": ledger.snapshot(),
            "config_hash": allocator.config_hash,
        })
    except (ValueError, TypeError, OverflowError) as exc:
        return Err(str(exc))


def route_live_dnca(
    dnca: Any,
    claims: Sequence[EvidenceInput],
    construct_context: ConstructContext,
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    dopamine_gain: float = 0.0,
    inhibition_threshold: float = 0.8,
) -> Result[dict[str, Any]]:
    """Only accept an actual executed DNCA instance, never a stand-in proxy."""
    try:
        from neuron7x_agents.dnca.orchestrator import DNCA
    except ImportError:
        return Err("dnca_package_unavailable_install_agents_package")
    if not isinstance(dnca, DNCA):
        return Err("dnca_runtime_type_required")
    try:
        observation = observe_sps(dnca.sps.snapshot())
    except (ValueError, AttributeError, TypeError) as exc:
        return Err(f"dnca_snapshot_invalid:{exc}")
    routed = route_observation(
        observation, claims, construct_context, config_path,
        dopamine_gain=dopamine_gain, inhibition_threshold=inhibition_threshold,
    )
    if isinstance(routed, Ok):
        routed.value["source"] = "EXECUTED_DNCA_SPS"
    return routed
