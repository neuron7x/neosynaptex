"""Every substrate and mock adapter must declare canonical Provenance.

Follow-up to the REPLICATION_GATE_v1.0 Phase 4 closure: once the bundle
carries per-domain provenance, the adapters themselves must populate
the metadata honestly. An adapter without a ``provenance`` attribute
would silently emit ``"unknown"`` and could sneak into REAL-mode
pipelines only when the engine mode allowed it, but the ledger would
be noisy. This parametrised battery pins the declared provenance of
every first-party adapter so drift is caught immediately.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from contracts.provenance import (
    ClaimStatus,
    EngineMode,
    Provenance,
    ProvenanceClass,
    ProvenanceViolation,
    ensure_admissible,
)

_Factory = Callable[[], object]
from neosynaptex import (
    MockBnSynAdapter,
    MockMarketAdapter,
    MockMfnAdapter,
    MockPsycheCoreAdapter,
    Neosynaptex,
)
from substrates.bn_syn.adapter import BnSynAdapter
from substrates.cns_ai_loop.adapter import SyntheticCnsAiLoopAdapter
from substrates.gray_scott.adapter import GrayScottAdapter
from substrates.kuramoto.adapter import KuramotoAdapter
from substrates.zebrafish.adapter import ZebrafishAdapter

_VALID_CLASSES = {pc.value for pc in ProvenanceClass}
_VALID_STATUSES = {cs.value for cs in ClaimStatus}

_EXPECTED: list[tuple[_Factory, ProvenanceClass, ClaimStatus]] = [
    (lambda: ZebrafishAdapter("WT"), ProvenanceClass.REAL, ClaimStatus.ADMISSIBLE),
    (lambda: GrayScottAdapter(), ProvenanceClass.SYNTHETIC, ClaimStatus.ADMISSIBLE),
    (lambda: KuramotoAdapter(), ProvenanceClass.SYNTHETIC, ClaimStatus.ADMISSIBLE),
    (lambda: BnSynAdapter(), ProvenanceClass.SYNTHETIC, ClaimStatus.ADMISSIBLE),
    (
        lambda: SyntheticCnsAiLoopAdapter(seed=0),
        ProvenanceClass.SYNTHETIC,
        ClaimStatus.DOWNGRADED,
    ),
    (lambda: MockBnSynAdapter(), ProvenanceClass.MOCK, ClaimStatus.DOWNGRADED),
    (lambda: MockMfnAdapter(), ProvenanceClass.MOCK, ClaimStatus.DOWNGRADED),
    (lambda: MockPsycheCoreAdapter(), ProvenanceClass.MOCK, ClaimStatus.DOWNGRADED),
    (lambda: MockMarketAdapter(), ProvenanceClass.MOCK, ClaimStatus.DOWNGRADED),
]


@pytest.mark.parametrize("factory, want_class, want_status", _EXPECTED)
def test_adapter_declares_expected_provenance(
    factory: _Factory,
    want_class: ProvenanceClass,
    want_status: ClaimStatus,
) -> None:
    adapter = factory()
    prov = getattr(adapter, "provenance", None)
    assert isinstance(prov, Provenance), (
        f"{type(adapter).__name__}: missing or wrong-typed provenance attribute"
    )
    assert prov.provenance_class == want_class
    assert prov.claim_status == want_status


@pytest.mark.parametrize("factory, _c, _s", _EXPECTED)
def test_provenance_values_inside_canonical_enums(
    factory: _Factory,
    _c: ProvenanceClass,
    _s: ClaimStatus,
) -> None:
    adapter = factory()
    prov_attr = adapter.provenance  # type: ignore[attr-defined]
    assert isinstance(prov_attr, Provenance)
    assert prov_attr.provenance_class.value in _VALID_CLASSES
    assert prov_attr.claim_status.value in _VALID_STATUSES


def test_only_zebrafish_registers_in_real_mode() -> None:
    """In REAL mode the registration gate admits only real+admissible
    substrates. Of our first-party adapters that means Zebrafish alone;
    every synthetic / mock / downgraded adapter raises
    ``ProvenanceViolation``."""
    engine = Neosynaptex(window=16, mode="real")
    engine.register(ZebrafishAdapter("WT"))
    assert (
        "zebrafish" in engine._adapters
        or "zebrafish_WT" in engine._adapters
        or any("zebra" in k for k in engine._adapters)
    )

    rejected = [
        GrayScottAdapter(),
        KuramotoAdapter(),
        BnSynAdapter(),
        SyntheticCnsAiLoopAdapter(seed=0),
        MockBnSynAdapter(),
        MockMfnAdapter(),
        MockPsycheCoreAdapter(),
        MockMarketAdapter(),
    ]
    for ad in rejected:
        fresh = Neosynaptex(window=16, mode="real")
        with pytest.raises(ProvenanceViolation):
            fresh.register(ad)  # type: ignore[arg-type]


def test_every_adapter_accepted_in_demo_mode() -> None:
    """Demo mode is permissive; every annotated adapter registers cleanly."""
    for factory, _, _ in _EXPECTED:
        ad = factory()
        # ensure_admissible must not raise in demo mode regardless of prov class.
        ensure_admissible(ad, EngineMode.DEMO)
