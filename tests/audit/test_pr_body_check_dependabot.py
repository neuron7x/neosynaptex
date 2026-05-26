from __future__ import annotations

from tools.audit.pr_body_check import DEPENDABOT_ACTOR, ValidationContext, validate


def test_dependabot_dependency_pr_passes_without_claim_status() -> None:
    body = "Bumps pkg from 1.0.0 to 1.0.1.\n\nDependabot will resolve conflicts.\n"
    context = ValidationContext(
        actor=DEPENDABOT_ACTOR,
        title="deps: bump pkg from 1.0.0 to 1.0.1",
        head_ref="dependabot/npm_and_yarn/pkg-1.0.1",
    )

    ok, reason = validate(body, context)

    assert ok
    assert "measured" in reason


def test_dependabot_dependency_pr_rejects_invalid_claim_status() -> None:
    body = (
        "claim_status: confirmed\n\n"
        "Bumps pkg from 1.0.0 to 1.0.1.\n\n"
        "Dependabot will resolve conflicts.\n"
    )
    context = ValidationContext(
        actor=DEPENDABOT_ACTOR,
        title="deps: bump pkg from 1.0.0 to 1.0.1",
        head_ref="dependabot/npm_and_yarn/pkg-1.0.1",
    )

    ok, reason = validate(body, context)

    assert not ok
    assert "outside the canonical taxonomy" in reason
    assert "confirmed" in reason


def test_dependabot_exception_requires_actor() -> None:
    body = "Bumps pkg from 1.0.0 to 1.0.1.\n\nDependabot will resolve conflicts.\n"
    context = ValidationContext(
        actor="neuron7xLab",
        title="deps: bump pkg from 1.0.0 to 1.0.1",
        head_ref="dependabot/npm_and_yarn/pkg-1.0.1",
    )

    ok, reason = validate(body, context)

    assert not ok
    assert "missing" in reason.lower()


def test_dependabot_exception_requires_head_ref() -> None:
    body = "Bumps pkg from 1.0.0 to 1.0.1.\n\nDependabot will resolve conflicts.\n"
    context = ValidationContext(
        actor=DEPENDABOT_ACTOR,
        title="deps: bump pkg from 1.0.0 to 1.0.1",
        head_ref="feature/pkg-1.0.1",
    )

    ok, reason = validate(body, context)

    assert not ok
    assert "missing" in reason.lower()


def test_dependabot_exception_requires_title_shape() -> None:
    body = "Bumps pkg from 1.0.0 to 1.0.1.\n\nDependabot will resolve conflicts.\n"
    context = ValidationContext(
        actor=DEPENDABOT_ACTOR,
        title="rewrite docs",
        head_ref="dependabot/npm_and_yarn/pkg-1.0.1",
    )

    ok, reason = validate(body, context)

    assert not ok
    assert "missing" in reason.lower()
