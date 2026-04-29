"""Substrate → null family list router.

Per ``docs/audit/PHASE_3_NULL_SCREEN_PLAN.md`` §3, every substrate
declares its full canonical family set explicitly. There is no
"default" surrogate. A request for a substrate not listed here is a
hard error — Phase 3 refuses to invent a null protocol on the fly.

Bonferroni correction lives in the runner (``run_null_screen.py``);
this module only fixes the family set per substrate.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

__all__ = [
    "REGISTERED_SUBSTRATES",
    "SUBSTRATE_FAMILIES",
    "UnknownSubstrateError",
    "UnknownFamilyError",
    "families_for",
    "validate_family",
]


class UnknownSubstrateError(KeyError):
    """Raised when a substrate has no pinned family list."""


class UnknownFamilyError(KeyError):
    """Raised when a requested family is not in the registry."""


#: All recognised null-family names this router may emit. The runner
#: dispatches on these names to the actual generator implementations
#: in ``core/nulls/__init__.py::FAMILIES`` and ``core/iaaft.py``.
_KNOWN_FAMILIES: frozenset[str] = frozenset(
    {
        "iaaft_surrogate",
        "kuramoto_iaaft",
        "constrained_randomization",
        "wavelet_phase",
        "linear_matched",
    }
)


_RAW_SUBSTRATE_FAMILIES: dict[str, tuple[str, ...]] = {
    # Kuramoto-class substrates: per-oscillator-phase IAAFT + linear
    # baseline. The cost trajectory is univariate and well-suited to
    # both. Two families ⇒ Bonferroni α/2 = 0.025.
    "serotonergic_kuramoto": (
        "kuramoto_iaaft",
        "linear_matched",
        "iaaft_surrogate",
    ),
    # HRV (RR-interval): univariate, non-Gaussian heavy-tail. IAAFT
    # for spectrum, constrained_randomization for short-lag ACF,
    # linear_matched for AR(p) baseline. Three families ⇒ α/3.
    "hrv_fantasia": (
        "iaaft_surrogate",
        "constrained_randomization",
        "linear_matched",
    ),
    # EEG resting (per-channel): univariate per channel; wavelet
    # families separate amplitude from phase coherence. Three families.
    "eeg_resting": (
        "iaaft_surrogate",
        "wavelet_phase",
        "linear_matched",
    ),
    # Synthetic harnesses used by the adversarial test battery. They
    # share the IAAFT + linear_matched two-family contract because they
    # are univariate scalar series.
    "synthetic_white_noise": (
        "iaaft_surrogate",
        "linear_matched",
    ),
    "synthetic_power_law": (
        "iaaft_surrogate",
        "linear_matched",
    ),
    "synthetic_constant": (
        "iaaft_surrogate",
        "linear_matched",
    ),
}


SUBSTRATE_FAMILIES: Mapping[str, tuple[str, ...]] = MappingProxyType(_RAW_SUBSTRATE_FAMILIES)
REGISTERED_SUBSTRATES: tuple[str, ...] = tuple(sorted(_RAW_SUBSTRATE_FAMILIES.keys()))


def families_for(substrate: str) -> tuple[str, ...]:
    """Return the canonical pinned family tuple for ``substrate``.

    Raises ``UnknownSubstrateError`` if the substrate is not registered.
    """
    try:
        return SUBSTRATE_FAMILIES[substrate]
    except KeyError as exc:
        raise UnknownSubstrateError(
            f"substrate {substrate!r} has no pinned family list; "
            f"registered: {REGISTERED_SUBSTRATES}"
        ) from exc


def validate_family(name: str) -> str:
    """Return ``name`` unchanged if it is a recognised family.

    Raises ``UnknownFamilyError`` otherwise.
    """
    if name not in _KNOWN_FAMILIES:
        raise UnknownFamilyError(
            f"family {name!r} is not in the registry; known: {sorted(_KNOWN_FAMILIES)}"
        )
    return name
