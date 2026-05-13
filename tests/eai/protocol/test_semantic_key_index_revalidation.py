from core.eai.constraint_index import SemanticKeyIndex
from core.eai.guardrail_registry import (
    GuardrailRegistry,
    build_invalidation_condition,
    build_revalidation_artifact,
)
from core.eai.intelligence_cycle import ClaimCard, ClaimType, KillArtifact


def test_semantic_key_index_lookup() -> None:
    idx = SemanticKeyIndex()
    idx.add("library:y:supports:z", "GRD-1")
    assert "GRD-1" in idx.lookup_many(["x", "library:y:supports:z"])


def test_invalidation_condition_is_structured() -> None:
    reg = GuardrailRegistry()
    patch = reg.register_from_kill(
        KillArtifact(
            "KILL-1", ClaimCard("CLM-1", "library y supports z", ClaimType.SOFTWARE), "r", "f", "g"
        ),
        "a" * 64,
    )
    cond = build_invalidation_condition(patch)
    assert cond.subject and cond.predicate and cond.object


def test_revalidation_artifact_append_only_object() -> None:
    ra = build_revalidation_artifact("GRD-1", "EVD-1", "ACTIVE", "SCOPED_DOWN", "SCOPED_DOWN")
    assert ra.decision == "SCOPED_DOWN"
