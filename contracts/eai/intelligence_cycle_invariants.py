from __future__ import annotations

INVARIANTS = [
    "No evidence without boundary",
    "No integration without artifact",
    "No artifact without reproducibility",
    "No promotion without falsification",
    "No claim expansion beyond verified scope",
    "No intent update without falsification-boundary-artifact-retention-revalidation",
]


def may_update_intent(
    artifact: object | None,
    *,
    retention_hash: str | None,
    revalidation_passed: bool,
) -> bool:
    """Canonical gate: no inference may update intent unless fully verified."""
    return bool(
        artifact
        and hasattr(artifact, "can_be_promoted")
        and artifact.can_be_promoted()
        and retention_hash
        and revalidation_passed
    )
