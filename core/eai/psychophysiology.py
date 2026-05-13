from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LatentPsychophysiologyState:
    neural: float
    sympathetic: float
    parasympathetic: float
    hpa: float
    interoceptive: float
    metabolic: float
    behavioral: float
    contextual: float


@dataclass(frozen=True)
class PsychophysiologyObservation:
    hr: float
    hrv: float
    eda: float
    rsp: float
    bp: float
    cort: float
    self_report_arousal: float


@dataclass(frozen=True)
class PsychophysiologyParameters:
    k_sympathetic: float = 0.25
    k_parasympathetic: float = 0.20
    k_hpa: float = 0.15
    k_interoceptive_precision: float = 0.30


_DEFAULT_PARAMETERS = PsychophysiologyParameters()


def observe_state(x: LatentPsychophysiologyState) -> PsychophysiologyObservation:
    hr = 70.0 + 18.0 * x.sympathetic - 12.0 * x.parasympathetic
    hrv = max(5.0, 45.0 + 20.0 * x.parasympathetic - 15.0 * x.sympathetic)
    eda = max(0.0, 2.0 + 3.0 * x.sympathetic)
    rsp = 12.0 + 4.0 * x.sympathetic - 2.0 * x.parasympathetic
    bp = 110.0 + 20.0 * x.sympathetic - 8.0 * x.parasympathetic
    cort = max(0.0, 8.0 + 5.0 * x.hpa)
    self_report_arousal = max(0.0, min(10.0, 4.0 + 2.5 * x.interoceptive + 1.5 * x.contextual))
    return PsychophysiologyObservation(
        hr=hr, hrv=hrv, eda=eda, rsp=rsp, bp=bp, cort=cort, self_report_arousal=self_report_arousal
    )


def step_state(
    x: LatentPsychophysiologyState,
    *,
    threat_input: float,
    safety_input: float,
    params: PsychophysiologyParameters = _DEFAULT_PARAMETERS,
) -> LatentPsychophysiologyState:
    net = threat_input - safety_input
    sympathetic = x.sympathetic + params.k_sympathetic * net - 0.1 * x.sympathetic
    parasympathetic = x.parasympathetic - params.k_parasympathetic * net - 0.1 * x.parasympathetic
    hpa = x.hpa + params.k_hpa * net - 0.05 * x.hpa
    intero = (
        x.interoceptive
        + params.k_interoceptive_precision * (sympathetic - parasympathetic)
        - 0.1 * x.interoceptive
    )

    return LatentPsychophysiologyState(
        neural=x.neural + 0.05 * net,
        sympathetic=sympathetic,
        parasympathetic=parasympathetic,
        hpa=hpa,
        interoceptive=intero,
        metabolic=x.metabolic + 0.03 * hpa,
        behavioral=x.behavioral + 0.04 * net,
        contextual=x.contextual + 0.05 * net,
    )
