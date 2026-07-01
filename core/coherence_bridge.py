"""CoherenceBridge — production-ready external API surface for NeoSynaptex.

JSON-RPC style, no HTTP dependencies. SSI external enforced.

Determinism contract
--------------------

The bridge emits two kinds of timestamps:

* ``timestamp`` -- the wall-clock moment at which the
  snapshot was served. Useful for live monitoring, *not* part of the
  evidentiary surface.
* ``evidentiary_timestamp`` -- a caller-injected deterministic clock
  reading. ``export_bundle`` deliberately uses only this one so that
  the bytes it emits are stable under a fixed ``RuntimeContext``.

The legacy implementation called ``time.time()`` and
``subprocess.run(["git", ...])`` at export time, making the evidence
bundle non-reproducible and host-dependent. The ``RuntimeContext``
dependency injection below lets callers (tests, CI) supply a fixed
clock and git SHA; the default still works standalone on a developer
workstation because ``RuntimeContext.default()`` delegates to the real
wall clock and subprocess probe.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404  # only behind NEOSYNAPTEX_ALLOW_SUBPROCESS_GIT gate
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any, Protocol

# Environment gates for the git-SHA provider. The audited export path
# MUST NOT shell out to ``git rev-parse``; it reads ``build_git_sha``
# out of the injected ``RuntimeContext``. The default path (when no
# RuntimeContext is supplied) resolves the SHA in this order:
#
#   1. ``NEOSYNAPTEX_BUILD_GIT_SHA`` env var — canonical injection point
#      for CI / containerised runs (set at build time, never at runtime).
#   2. ``NEOSYNAPTEX_ALLOW_SUBPROCESS_GIT=1`` — explicit opt-in for
#      interactive developer use. Only this flag authorises a subprocess
#      call to ``git``; every other path returns ``"unknown"``.
#
# The opt-in flag is deliberately non-default: production / evidentiary
# pipelines must either pre-populate the env var at build time or inject
# a RuntimeContext, never rely on runtime subprocess discovery.
BUILD_SHA_ENV = "NEOSYNAPTEX_BUILD_GIT_SHA"
ALLOW_SUBPROCESS_GIT_ENV = "NEOSYNAPTEX_ALLOW_SUBPROCESS_GIT"

import numpy as np

from core.contracts import SSIDomain, ssi_apply
from core.event_bus import EventBus, SubstrateEvent

__all__ = [
    "CoherenceBridge",
    "DomainDiagnostics",
    "InterventionSuggestion",
    "ClockProtocol",
    "GitMetadataProvider",
    "RuntimeContext",
]


class ClockProtocol(Protocol):
    """Callable returning a monotonic-ish epoch-seconds timestamp."""

    def __call__(self) -> float: ...


class GitMetadataProvider(Protocol):
    """Returns an immutable identifier for the current build."""

    def __call__(self) -> str: ...


def _subprocess_git_sha() -> str:
    """DEV_ONLY helper: shell out to ``git rev-parse`` for the build SHA.

    Guarded by the ``NEOSYNAPTEX_ALLOW_SUBPROCESS_GIT`` environment flag.
    Without the flag this function returns ``"unknown"`` rather than
    invoking a subprocess, so audited / evidentiary paths cannot reach a
    ``subprocess.run`` call even if they accidentally construct a default
    RuntimeContext.

    Production and CI callers should instead set ``NEOSYNAPTEX_BUILD_GIT_SHA``
    at build time (see ``RuntimeContext.default``) or inject an explicit
    ``RuntimeContext`` into ``CoherenceBridge``.
    """
    if os.environ.get(ALLOW_SUBPROCESS_GIT_ENV) != "1":
        return "unknown"
    try:
        result = subprocess.run(  # nosec B603 B607  # hardcoded git command, no user input
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@dataclass(frozen=True)
class RuntimeContext:
    """Injected providers for time and build metadata.

    ``build_git_sha`` is captured once at construction (it never changes
    over the lifetime of a process), but ``clock`` is called at use time
    so that callers supplying a fixed clock get a deterministic surface.
    """

    build_git_sha: str
    clock: ClockProtocol = field(default_factory=lambda: time.time)

    @classmethod
    def default(cls) -> RuntimeContext:
        """Live runtime context.

        Resolution order for ``build_git_sha`` (subprocess never by default):

        1. ``NEOSYNAPTEX_BUILD_GIT_SHA`` env var -- canonical build-time
           injection point. Always preferred when set.
        2. ``NEOSYNAPTEX_ALLOW_SUBPROCESS_GIT=1`` + ``git`` available ->
           interactive developer fallback via ``_subprocess_git_sha``.
        3. Otherwise ``"unknown"`` -- no subprocess, no wall-clock SHA.

        Tests and audited export paths should pass an explicit
        ``RuntimeContext`` (e.g. ``RuntimeContext.fixed(...)``) rather
        than relying on this default.
        """
        env_sha = os.environ.get(BUILD_SHA_ENV)
        if env_sha:
            return cls(build_git_sha=env_sha, clock=time.time)
        return cls(build_git_sha=_subprocess_git_sha(), clock=time.time)

    @classmethod
    def fixed(cls, git_sha: str = "fixed", timestamp: float = 0.0) -> RuntimeContext:
        """Deterministic runtime context for tests and byte-stable exports."""
        return cls(build_git_sha=git_sha, clock=lambda: timestamp)


@dataclass(frozen=True)
class DomainDiagnostics:
    domain: str
    gamma: float
    gamma_ci: tuple[float, float]
    spectral_radius: float
    anomaly_score: float
    modulation: float
    phase_contribution: str


@dataclass(frozen=True)
class InterventionSuggestion:
    domain: str
    action: str
    magnitude: float
    reason: str
    ssi_domain: str = "EXTERNAL"


class CoherenceBridge:
    """External interface to NeoSynaptex — read-only diagnostics + bounded suggestions.

    All modulation suggestions are SSI.EXTERNAL enforced.
    """

    def __init__(
        self,
        engine: Any,
        event_bus: EventBus | None = None,
        *,
        runtime: RuntimeContext | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._engine = engine
        self._bus = event_bus or EventBus()
        self._runtime = runtime if runtime is not None else RuntimeContext.default()
        # ``subscribe`` sleeps between polls; allow callers to inject a
        # no-op sleep so the loop can be exercised deterministically in
        # tests without real wall-clock dependence.
        self._sleep: Callable[[float], None] = sleep if sleep is not None else time.sleep

    def snapshot(self) -> dict[str, Any]:
        """Current state of all substrates + global gamma + phase.

        The operational timestamp comes from the injected clock; the
        git SHA comes from the injected runtime context. Both are
        deterministic under a fixed ``RuntimeContext``.
        """
        history = self._engine.history()
        if not history:
            return {
                "error": "no observations",
                "timestamp": self._runtime.clock(),
                "git_sha": self._runtime.build_git_sha,
            }

        state = history[-1]
        git_sha = self._runtime.build_git_sha

        per_domain = {}
        for domain, gamma in state.gamma_per_domain.items():
            ci = state.gamma_ci_per_domain.get(domain, (float("nan"), float("nan")))
            per_domain[domain] = {
                "gamma": float(gamma) if np.isfinite(gamma) else None,
                "gamma_ci": [
                    float(ci[0]) if np.isfinite(ci[0]) else None,
                    float(ci[1]) if np.isfinite(ci[1]) else None,
                ],
                "spectral_radius": float(state.sr_per_domain.get(domain, float("nan")))
                if np.isfinite(state.sr_per_domain.get(domain, float("nan")))
                else None,
                "anomaly_score": float(state.anomaly_score.get(domain, float("nan")))
                if np.isfinite(state.anomaly_score.get(domain, float("nan")))
                else None,
                "modulation": state.modulation.get(domain, 0.0),
            }

        return {
            "timestamp": self._runtime.clock(),
            "git_sha": git_sha,
            "tick": state.t,
            "gamma_global": float(state.gamma_mean) if np.isfinite(state.gamma_mean) else None,
            "gamma_std": float(state.gamma_std) if np.isfinite(state.gamma_std) else None,
            "cross_coherence": float(state.cross_coherence)
            if np.isfinite(state.cross_coherence)
            else None,
            "phase": state.phase,
            "spectral_radius": float(state.spectral_radius)
            if np.isfinite(state.spectral_radius)
            else None,
            "per_domain": per_domain,
        }

    def subscribe(self, event_type: str) -> Generator[SubstrateEvent, None, None]:
        """Event stream generator. Yields events of given type."""
        queue: list[SubstrateEvent] = []
        self._bus.subscribe(event_type, lambda e: queue.append(e))
        while True:
            while queue:
                yield queue.pop(0)
            self._sleep(0.01)

    def query(self, domain: str) -> DomainDiagnostics | None:
        """Detailed diagnostics for a specific domain."""
        history = self._engine.history()
        if not history:
            return None

        state = history[-1]
        if domain not in state.gamma_per_domain:
            return None

        gamma = state.gamma_per_domain[domain]
        ci = state.gamma_ci_per_domain.get(domain, (float("nan"), float("nan")))
        sr = state.sr_per_domain.get(domain, float("nan"))
        anomaly = state.anomaly_score.get(domain, float("nan"))
        mod = state.modulation.get(domain, 0.0)

        return DomainDiagnostics(
            domain=domain,
            gamma=gamma,
            gamma_ci=ci,
            spectral_radius=sr,
            anomaly_score=anomaly,
            modulation=mod,
            phase_contribution=state.phase,
        )

    def suggest_intervention(self, domain: str) -> InterventionSuggestion:
        """Suggest bounded intervention. SSI.EXTERNAL enforced."""
        # Enforce SSI external — pass domain name as signal for validation
        ssi_apply(domain, SSIDomain.EXTERNAL)

        history = self._engine.history()
        if not history:
            return InterventionSuggestion(
                domain=domain,
                action="observe",
                magnitude=0.0,
                reason="no observations available",
            )

        state = history[-1]
        gamma = state.gamma_per_domain.get(domain, float("nan"))
        mod = state.modulation.get(domain, 0.0)

        if not np.isfinite(gamma):
            action = "observe"
            magnitude = 0.0
            reason = "gamma not yet computed"
        elif gamma > 1.15:
            action = "dampen"
            magnitude = min(abs(mod), 0.05)
            reason = f"gamma={gamma:.3f} above metastable band"
        elif gamma < 0.85:
            action = "excite"
            magnitude = min(abs(mod), 0.05)
            reason = f"gamma={gamma:.3f} below metastable band"
        else:
            action = "maintain"
            magnitude = 0.0
            reason = f"gamma={gamma:.3f} within metastable band"

        return InterventionSuggestion(
            domain=domain,
            action=action,
            magnitude=magnitude,
            reason=reason,
            ssi_domain="EXTERNAL",
        )

    def export_bundle(self, fmt: str = "json") -> bytes:
        """Export deterministic evidence bundle for external audit.

        Bytes are stable under a fixed ``RuntimeContext``: no wall-clock
        readings, no subprocess ``git rev-parse`` invocation at export
        time, and the JSON is emitted with ``sort_keys=True`` so dict
        insertion order cannot affect the hash.

        Layout: the proof dict is emitted at the top level (legacy
        consumers keep seeing ``gamma``, ``chain``, etc. directly), with
        deterministic metadata fields (``build_git_sha``,
        ``evidentiary_timestamp``) merged in alongside.
        """
        if fmt != "json":
            raise ValueError(f"Unsupported format: {fmt}")

        proof = self._engine.export_proof()
        bundle: dict[str, Any] = dict(proof)
        # Deterministic metadata from the injected RuntimeContext only;
        # no subprocess / no wall clock at export time.
        bundle["build_git_sha"] = self._runtime.build_git_sha
        bundle["evidentiary_timestamp"] = self._runtime.clock()
        return json.dumps(
            bundle,
            indent=2,
            default=str,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")

    @staticmethod
    def _get_git_sha() -> str:
        """Preserved for backwards compatibility; prefer ``RuntimeContext``."""
        return _subprocess_git_sha()
