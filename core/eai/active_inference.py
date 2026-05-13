from __future__ import annotations

from dataclasses import dataclass

from core.falsification_engine import falsification_decision


@dataclass
class InferenceStep:
    claim_text: str
    predicted_status: str
    falsification_reason: str


@dataclass
class ActiveInferenceResult:
    steps: list[InferenceStep]
    entropy_score: float
    stabilized: bool


def run_active_inference_loop(
    claims: list[str], contradiction_markers: list[str], stabilization_threshold: float = 0.2
) -> ActiveInferenceResult:
    steps: list[InferenceStep] = []
    uncertainty_hits = 0

    for claim in claims:
        passed, reason = falsification_decision(claim, contradiction_markers)
        status = "EVIDENCE" if passed else "KILLED"
        if status != "EVIDENCE":
            uncertainty_hits += 1
        steps.append(
            InferenceStep(claim_text=claim, predicted_status=status, falsification_reason=reason)
        )

    entropy_score = uncertainty_hits / max(1, len(claims))
    stabilized = entropy_score <= stabilization_threshold
    return ActiveInferenceResult(steps=steps, entropy_score=entropy_score, stabilized=stabilized)
