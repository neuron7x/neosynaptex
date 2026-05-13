from core.eai.psychophysiology import (
    LatentPsychophysiologyState,
    observe_state,
    step_state,
)


def _baseline() -> LatentPsychophysiologyState:
    return LatentPsychophysiologyState(
        neural=0.0,
        sympathetic=0.0,
        parasympathetic=0.0,
        hpa=0.0,
        interoceptive=0.0,
        metabolic=0.0,
        behavioral=0.0,
        contextual=0.0,
    )


def test_threat_increases_hr_and_eda() -> None:
    x1 = step_state(_baseline(), threat_input=1.0, safety_input=0.0)
    o1 = observe_state(x1)
    assert o1.hr > 70.0
    assert o1.eda > 2.0


def test_safety_bias_improves_hrv() -> None:
    x1 = step_state(_baseline(), threat_input=0.0, safety_input=1.0)
    o1 = observe_state(x1)
    assert o1.hrv >= 45.0
