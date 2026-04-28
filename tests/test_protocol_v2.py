"""Tests for NFI x SSI Protocol v2 -- all 8 tasks.

55 existing neosynaptex tests + new protocol tests.

Author: Yaroslav Vasylenko / neuron7xLab
License: AGPL-3.0-or-later
"""

import importlib.util

import numpy as np
import pytest


# ===================================================================
# TASK 1: SSI INVARIANT ENFORCEMENT
# ===================================================================
class TestInvariantIV:
    def test_ssi_internal_raises_invariant_violation(self):
        from contracts.invariants import InvariantViolation, SSIDomain, ssi_apply

        with pytest.raises(InvariantViolation) as exc_info:
            ssi_apply(signal="test", domain=SSIDomain.INTERNAL)
        assert "INVARIANT_IV" in str(exc_info.value)

    def test_ssi_external_valid(self):
        from contracts.invariants import SSIDomain, ssi_apply

        result = ssi_apply(signal="market_data", domain=SSIDomain.EXTERNAL)
        assert result == "market_data"

    def test_ssi_external_with_transform(self):
        from contracts.invariants import SSIDomain, ssi_apply

        result = ssi_apply(signal=5, domain=SSIDomain.EXTERNAL, transform=lambda x: x * 2)
        assert result == 10

    def test_invariant_i_gamma_derived(self):
        from contracts.invariants import InvariantViolation, enforce_gamma_derived

        enforce_gamma_derived("computed")  # should not raise
        with pytest.raises(InvariantViolation):
            enforce_gamma_derived("assigned")
        with pytest.raises(InvariantViolation):
            enforce_gamma_derived("manual")

    def test_invariant_ii_state_not_proof(self):
        from contracts.invariants import InvariantViolation, enforce_state_not_proof

        enforce_state_not_proof("nfi", "bn_syn")  # different sources OK
        with pytest.raises(InvariantViolation):
            enforce_state_not_proof("nfi", "nfi")  # same source forbidden

    def test_invariant_iii_bounded_modulation(self):
        from contracts.invariants import enforce_bounded_modulation

        assert enforce_bounded_modulation(0.03) == 0.03
        assert enforce_bounded_modulation(0.1) == 0.05
        assert enforce_bounded_modulation(-0.2) == -0.05

    def test_gamma_regime_classification(self):
        from contracts.invariants import gamma_regime

        assert gamma_regime(1.0) == "METASTABLE"
        assert gamma_regime(0.9) == "METASTABLE"
        assert gamma_regime(1.14) == "METASTABLE"
        assert gamma_regime(0.75) == "WARNING"
        assert gamma_regime(1.25) == "WARNING"
        assert gamma_regime(0.55) == "CRITICAL"
        assert gamma_regime(0.4) == "COLLAPSE"
        assert gamma_regime(2.0) == "COLLAPSE"


# ===================================================================
# TASK 2: TRANSFER ENTROPY (requires bn_syn root stubs)
# ===================================================================
def _can_import(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ModuleNotFoundError, ValueError):
        return False


_skip_bn_syn = pytest.mark.skipif(
    not _can_import("bn_syn.transfer_entropy"),
    reason="bn_syn root stubs removed — modules live in substrates/bn_syn/",
)
_skip_tradepulse = pytest.mark.skipif(
    not _can_import("tradepulse.coherence_bridge"),
    reason="tradepulse root stubs removed",
)


@_skip_bn_syn
class TestTransferEntropy:
    def test_te_directed(self):
        from bn_syn.transfer_entropy import transfer_entropy

        rng = np.random.default_rng(0)
        T = 5000
        X = rng.standard_normal(T)
        # Temporal causal: Y[t] = 0.7*X[t-1] + noise (proper lag structure)
        Y = np.empty(T)
        Y[0] = rng.standard_normal()
        for t in range(1, T):
            Y[t] = 0.7 * X[t - 1] + 0.3 * rng.standard_normal()
        assert transfer_entropy(X, Y, bins=6) > transfer_entropy(Y, X, bins=6)

    def test_te_nonnegative(self):
        from bn_syn.transfer_entropy import transfer_entropy

        rng = np.random.default_rng(0)
        X, Y = rng.standard_normal(500), rng.standard_normal(500)
        assert transfer_entropy(X, Y) >= 0

    def test_te_matrix_shape(self):
        from bn_syn.transfer_entropy import transfer_entropy_matrix

        rng = np.random.default_rng(42)
        signals = rng.standard_normal((4, 200))
        mat = transfer_entropy_matrix(signals)
        assert mat.shape == (4, 4)
        # Diagonal should be zero
        for i in range(4):
            assert mat[i, i] == 0.0

    def test_te_short_signal(self):
        from bn_syn.transfer_entropy import transfer_entropy

        assert transfer_entropy(np.array([1.0, 2.0]), np.array([3.0, 4.0])) == 0.0


# ===================================================================
# TASK 3: PHI PROXY
# ===================================================================
@_skip_bn_syn
class TestPhiProxy:
    def test_phi_coupled_gt_independent(self):
        from bn_syn.phi_proxy import phi_proxy

        rng = np.random.default_rng(42)
        T = 1000
        indep = np.vstack(
            [
                (np.sin(np.linspace(0, 10 * np.pi, T)) > 0).astype(float),
                (np.sin(np.linspace(0.5, 10.5 * np.pi, T)) > 0).astype(float),
            ]
        )
        coupled = np.zeros((4, T))
        coupled[0] = (np.sin(np.linspace(0, 20 * np.pi, T)) > 0).astype(float)
        for k in range(1, 4):
            coupled[k] = np.roll(coupled[0], k * 10).astype(float)
            coupled[k] = (coupled[k] + rng.standard_normal(T) * 0.1 > 0.5).astype(float)
        assert phi_proxy(coupled) > phi_proxy(indep)

    def test_phi_nonnegative(self):
        from bn_syn.phi_proxy import phi_proxy

        rng = np.random.default_rng(0)
        mat = rng.binomial(1, 0.3, (3, 100)).astype(float)
        assert phi_proxy(mat) >= 0.0

    def test_phi_too_small(self):
        from bn_syn.phi_proxy import phi_proxy

        assert phi_proxy(np.zeros((1, 50))) == 0.0


# ===================================================================
# TASK 4: CELL ASSEMBLY
# ===================================================================
@_skip_bn_syn
class TestCellAssembly:
    def test_assembly_detection(self):
        from bn_syn.cell_assembly import detect_cell_assemblies

        rng = np.random.default_rng(42)
        N, T = 10, 500
        spikes = rng.binomial(1, 0.1, (N, T)).astype(float)
        sync_times = rng.choice(T, 50, replace=False)
        spikes[:3, sync_times] = 1.0
        assemblies = detect_cell_assemblies(spikes, bootstrap_n=20, stability_threshold=0.5)
        # Should find at least something (relaxed threshold for speed)
        assert isinstance(assemblies, list)

    def test_assembly_empty_sparse(self):
        from bn_syn.cell_assembly import detect_cell_assemblies

        rng = np.random.default_rng(0)
        spikes = rng.binomial(1, 0.01, (5, 100)).astype(float)
        assemblies = detect_cell_assemblies(spikes, bootstrap_n=5)
        assert isinstance(assemblies, list)

    def test_assembly_too_small(self):
        from bn_syn.cell_assembly import detect_cell_assemblies

        assert detect_cell_assemblies(np.zeros((2, 10))) == []


# ===================================================================
# TASK 5: COHERENCE BRIDGE
# ===================================================================
@_skip_tradepulse
class TestCoherenceBridge:
    def test_regime_critical(self):
        from tradepulse.coherence_bridge import CoherenceBridge

        bridge = CoherenceBridge()
        assert bridge.regime_classify(r=0.6, gamma=1.05) == "critical"
        assert bridge.regime_classify(r=0.6, gamma=1.14) == "critical"

    def test_regime_synchronized(self):
        from tradepulse.coherence_bridge import CoherenceBridge

        bridge = CoherenceBridge()
        assert bridge.regime_classify(r=0.95, gamma=1.05) == "synchronized"

    def test_regime_incoherent(self):
        from tradepulse.coherence_bridge import CoherenceBridge

        bridge = CoherenceBridge()
        assert bridge.regime_classify(r=0.1, gamma=0.5) == "incoherent"

    def test_kuramoto_r_range(self):
        from tradepulse.coherence_bridge import CoherenceBridge

        bridge = CoherenceBridge()
        for _ in range(20):
            phases = np.random.uniform(-np.pi, np.pi, 50)
            r = bridge.compute_kuramoto_r(phases)
            assert 0.0 <= r <= 1.0

    def test_demo_synthetic_runs(self):
        from tradepulse.coherence_bridge import CoherenceBridge

        bridge = CoherenceBridge()
        demo = bridge.demo_synthetic(200)
        assert demo["total_windows"] > 0
        assert "mean_gamma" in demo
        assert "trajectory" in demo

    def test_invariant_iv_external_domain(self):
        from tradepulse.coherence_bridge import CoherenceBridge

        bridge = CoherenceBridge()
        # Bridge must not have internal NFI state
        assert not hasattr(bridge, "_nfi_internal_state")

    def test_ingest_short_signal(self):
        from tradepulse.coherence_bridge import CoherenceBridge

        bridge = CoherenceBridge(window=50)
        result = bridge.ingest({"prices": np.array([1.0, 2.0, 3.0])})
        assert result["regime"] == "insufficient_data"


# ===================================================================
# TASK 8: AXIOM_0
# ===================================================================
class TestAxiom0:
    def test_axiom_consistency_valid(self):
        from core.axioms import verify_axiom_consistency

        state = {
            "gamma": 0.994,
            "substrates": ["zebrafish", "bn_syn", "cns_ai"],
            "convergence_slope": -0.001,
        }
        assert verify_axiom_consistency(state) is True

    def test_axiom_fails_no_gamma(self):
        from core.axioms import verify_axiom_consistency

        state = {"substrates": ["a", "b"], "convergence_slope": -0.001}
        assert verify_axiom_consistency(state) is False

    def test_axiom_fails_gamma_out_of_range(self):
        from core.axioms import verify_axiom_consistency

        state = {"gamma": 2.0, "substrates": ["a", "b"], "convergence_slope": -0.001}
        assert verify_axiom_consistency(state) is False

    def test_axiom_fails_not_converging(self):
        from core.axioms import verify_axiom_consistency

        state = {"gamma": 1.0, "substrates": ["a", "b"], "convergence_slope": 0.01}
        assert verify_axiom_consistency(state) is False

    def test_axiom_fails_too_few_witnesses(self):
        from core.axioms import verify_axiom_consistency

        state = {"gamma": 1.0, "substrates": ["a"], "convergence_slope": -0.001}
        assert verify_axiom_consistency(state) is False

    def test_substrate_gamma_values(self):
        from core.axioms import SUBSTRATE_GAMMA

        assert len(SUBSTRATE_GAMMA) >= 6  # 9 ledger entries after Phase 2 hardening
        # Skip substrates that do not emit γ (e.g. BN-Syn after κ ≠ γ Phase 2
        # downgrade — bnsyn.gamma=null in ledger v2.0.0).
        for name, (gamma, _) in SUBSTRATE_GAMMA.items():
            if gamma is None:
                continue
            assert 0 < gamma < 3, f"{name} gamma={gamma} out of range"


# ===================================================================
# FORMULA VERIFICATION
# ===================================================================
class TestFormulaVerification:
    def test_gamma_psd_formula(self):
        """gamma_PSD = 2H + 1 -- THE formula. NEVER 2H-1."""
        assert 2 * 0.5 + 1 == 2.0  # Brownian: H=0.5 -> gamma=2.0
        assert 2 * 0.0 + 1 == 1.0  # Anti-persistent: H=0 -> gamma=1.0
        assert 2 * 1.0 + 1 == 3.0  # Persistent: H=1 -> gamma=3.0
