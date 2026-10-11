# NeoSynaptex Repository Topology (historical v3.0 inventory)

> **CANONICAL STATUS OVERRIDE — 2026-10-11.** This is a historical architecture inventory, **not** an authoritative inventory of current test counts, validation status, or established scientific results. In this file, older labels such as `VALIDATED`, `SURVIVES`, `proof`, and `all green` describe **past project assertions**, not independently verified current status.
>
> **Live authority:** `evidence/gamma_ledger.json` v2.0.0; `docs/CLAIM_BOUNDARY.md` (C-001–C-004 and §5.1); `CANONICAL_POSITION.md`; `docs/audit/PHASE_4B_CANONICAL_KURAMOTO_OBSERVABLES.md`. The scientific evidence gate has **zero** substrates certified `VALIDATED` under all six current §5.1 conditions. Do not count BN-Syn structural κ as γ or null-failed candidates as validations. Phase 4b deprecates legacy `topo`/`thermo_cost` for canonical Kuramoto γ-claims.
>
> **CI truth:** The 2026-10-11 PR #1/#2 Actions runs failed before runner allocation (`steps=[]`, `runner_id=0`). This is infrastructure-observed failure, **not** a successfully run test suite and **not** proof that source code failed. See <https://github.com/neuron7x/neosynaptex/pull/1> for evidence. Runtime/test counts below are historical and unverified for this repository state.
>
> **Traceability:** Historical values and design notes remain below unchanged in substance; do not erase failed or superseded measurements. Any future validation promotion requires evidence-bound PR and all six gates, not a README or topology edit.



## Zeroth Axiom (INV-YV1: Gradient Ontology)

> **ΔV > 0 ∧ dΔV/dt ≠ 0**
>
> Existence = sustained non-equilibrium. Static gradient = capacitor.
> Zero gradient = noise. Intelligence = resistance to decay.
> — Yaroslav Vasylenko

## Architecture Overview

```
neosynaptex/
├── neosynaptex.py          ← Single-file engine (1384 LOC, all γ computation)
├── core/                   ← Infrastructure (30 modules, ~6000 LOC)
│   ├── constants.py        ← Single source of truth for ALL thresholds
│   ├── axioms.py           ← INV-YV1 + AXIOM_0 + check_inv_yv1()
│   ├── coherence_state_space.py  ← 4-D state-space model (S, γ, E_obj, σ²)
│   ├── gamma_fdt_estimator.py    ← FDT γ-estimator (auto, not manual tuning)
│   ├── objection_energy_budget.py ← PID critic gain controller + energy brake
│   ├── hallucination_benchmark.py ← 15 scenarios, ΔS prediction, perturbation
│   ├── resonance_map.py    ← Phase-space analytics, bifurcation detection
│   ├── ablation_study.py   ← Role vs energy vs hybrid Pareto comparison
│   └── ... (21 legacy modules: gamma, falsification, iaaft, rqa, etc.)
├── contracts/              ← Invariants (YV1 + I–IV) + truth criterion
├── formal/                 ← Proofs, falsification protocol, substrate diversity
│   ├── proofs.py           ← 3 machine-verifiable theorems (γ=2H+1, susceptibility, INV-YV1)
│   ├── falsification_protocol.py ← 8 conditions (F1–F8), Verdict: SURVIVES
│   └── substrate_diversity.py    ← Universality evidence across 3+ domains
├── substrates/             ← substrate adapters (status per evidence/gamma_ledger.json)
├── evl/                    ← Evidence Verification Ledger
├── experiments/            ← experiment_cards.py + reproducible outputs
├── tests/                  ← 651 tests, 50 test files
├── scripts/                ← 13 operational scripts
├── evidence/               ← gamma_ledger.json (16 entries) + proof chains
├── data/golden/            ← Benchmark anchors
├── docs/                   ← Science, manuscripts
├── agents/                 ← Agent subsystem
└── .github/workflows/      ← CI (workflows configured; current execution unverified)
```

## Substrate Map (from gamma_ledger.json)

### Previously reported as VALIDATED (historical, statuses superseded)

| Substrate | γ | CI | Domain | Source |
|-----------|---|-----|--------|--------|
| Zebrafish | 1.055 | [0.89, 1.21] | Biology | McGuirl 2020 calcium imaging |
| Gray-Scott | 0.979 | [0.88, 1.01] | Chemistry | PDE reaction-diffusion, F-sweep |
| Kuramoto | 0.963 | [0.93, 1.00] | Network dynamics | 128-oscillator phase sync |
| BN-Syn | 0.946 | — | Network dynamics | 1/f spiking network |
| EEG PhysioNet | 1.068 | — | Neuroscience | EEGBCI motor imagery |
| EEG Resting | 1.255 | — | Neuroscience | Resting-state alpha |
| HRV Fantasia | 1.003 | — | Physiology | PhysioNet Fantasia RR |
| Serotonergic Kuramoto | 1.068 | — | Network dynamics | 5-HT modulated oscillators |

### Other entries (8: 4 DERIVED/mock, 2 PENDING, 1 CONSTRUCTED, 1 outlier)

| Substrate | γ | Status | Note |
|-----------|---|--------|------|
| HRV PhysioNet | 0.885 | EVIDENCE_CANDIDATE (current ledger) | Historical estimate; missing real-data hash |
| CNS-AI Loop | 1.059 | PENDING | Awaiting real cognitive data |
| NFI Unified | 0.899 | PENDING | Cross-substrate aggregate |
| CFP/ДІЙ | 1.832 | CONSTRUCTED | Outlier — ABM, not γ ≈ 1 |
| 4× Mock | 0.95–1.09 | DERIVED | Synthetic, not evidential |

## Core Modules (30)

| Module | Purpose |
|--------|---------|
| **`constants.py`** | **Single source of truth for ALL thresholds** |
| **`axioms.py`** | **INV-YV1 + AXIOM_0 + γ_PSD = 2H+1 + check_inv_yv1()** |
| **`coherence_state_space.py`** | **4-D state-space model (S, γ, E_obj, σ²)** |
| **`gamma_fdt_estimator.py`** | **FDT γ-estimator (auto-calibration, not manual)** |
| **`objection_energy_budget.py`** | **PID critic gain controller + energy brake** |
| **`hallucination_benchmark.py`** | **15 scenarios, ΔS prediction, perturbation** |
| **`resonance_map.py`** | **Phase-space analytics, bifurcation detection** |
| **`ablation_study.py`** | **Role vs energy vs hybrid Pareto comparison** |
| `adapter_registry.py` | Auto-discovery of substrate adapters |
| `coherence_bridge.py` | JSON-RPC API surface |
| `falsification.py` | Automated falsification (3 axes: estimator, null, bias) |
| `gamma.py` | Canonical compute_gamma() with bootstrap CI |
| `gamma_registry.py` | Read-only gateway to gamma_ledger.json |
| `evidence_pipeline.py` | Collect → validate → register → query |
| `granger_multilag.py` | Cross-substrate Granger causality |
| `block_bootstrap.py` | Bootstrap CI computation |
| `iaaft.py` | Surrogate generation (amplitude-adjusted FFT) |
| `rqa.py` | Recurrence quantification analysis |
| `value_function.py` | Internal value estimation |
| `multiverse.py` | Multi-parameter sensitivity analysis |
| `coherence.py` | Transfer entropy γ estimation |
| `config_registry.py` | Dynamic configuration management |
| `contracts.py` | Core-level invariant enforcement |
| `dnca_bridge.py` | Dynamic Network Coherence Adapter |
| `event_bus.py` | Pub/sub event system |
| `events.py` | Event dataclasses |
| `evidence_schema.py` | Evidence entry schema validation |
| `failure_regimes.py` | Noise × window failure mapping |
| `truth_function.py` | Truth function computation |
| `bootstrap.py` | Legacy bootstrap helpers |

## Formal (3)

| Module | Purpose |
|--------|---------|
| `proofs.py` | 3 machine-verifiable theorems (γ=2H+1, susceptibility, INV-YV1) |
| `falsification_protocol.py` | 8 conditions (F1–F8), Verdict: SURVIVES |
| `substrate_diversity.py` | Universality evidence across 3+ scientific domains |

## Experiments

| Experiment | Path | Key Finding |
|------------|------|-------------|
| Experiment Cards | `experiments/experiment_cards.py` | 5 TRL-kit cards covering Tasks 1–6 |
| Scaffolding Trap | `experiments/scaffolding_trap/` | dskill/dt = 0.02 × gap × effort |
| LM Substrate | `experiments/lm_substrate/` | Stateless γ≈0 (null result) |

## CI Workflows (6)

| Workflow | File | Jobs | Status |
|----------|------|------|--------|
| NFI CI | `ci.yml` | lint, typecheck, verify×3, invariants, coverage, canonical-gate, ci-gate | GREEN |
| Security | `security.yml` | bandit SAST, pip-audit, gitleaks | GREEN |
| CodeQL | `codeql.yml` | SAST analysis | GREEN |
| Benchmarks | `benchmarks.yml` | γ substrate benchmarks, core test performance | GREEN |
| Dependency Review | `dependency-review.yml` | License + vulnerability scan on PRs | GREEN |
| Docker Reproduce | `docker-reproduce.yml` | One-command reproduction validation | GREEN |

## Invariants (5)

| # | Name | Enforcement |
|---|------|-------------|
| **YV1** | **Gradient Ontology: ΔV > 0 ∧ dΔV/dt ≠ 0** | `check_inv_yv1()` + `observe()` runtime diagnosis |
| I | γ derived only, never assigned | `gamma_registry.py` + AST tests |
| II | STATE ≠ PROOF | Independent substrate verification |
| III | Bounded modulation (\|m\| ≤ 0.05) | `enforce_bounded_modulation()` clamp |
| IV | SSI external only | `ssi_enforce_domain()` raises on INTERNAL |
- `Bounded modulation` — CPR drift triggers recalibration

## Evidence Chain

```
gamma_ledger.json → gamma_registry.py → neosynaptex.py (read-only)
                  → evidence_pipeline.py (append-only)
                  → proof_chain.jsonl (immutable log)
```

## Resolved Conflicts (2026-04-01)

1. `bn_syn/` vs `substrates/bn_syn/` — root is deprecated re-export shim
2. `mfn_plus/` vs `mycelium/` — mycelium is surviving authority
3. Kuramoto license — AGPL-3.0-or-later
4. CRR as metric — invalidated for ordered curricula, replaced by dskill/dt

## Verified Canonical Paths (2026-04-03, Hole 13 resolution)

No stale root-level `bn_syn/` or `mfn/` directories exist outside `substrates/`.
Canonical ownership is enforced by `CANONICAL_OWNERSHIP.yaml`:
- `substrates/bn_syn/` — sole authority for BN-Syn AdEx SNN
- `substrates/mfn/` — sole authority for MFN/Mycelium (pending merge from mfn_plus)
- Mock adapters in `neosynaptex.py` are test stubs only, not canonical implementations

## Canonical Gamma Computation (2026-04-03, Hole 4/11 resolution)

Single source of truth: `core/gamma.py:compute_gamma()`.
All other gamma implementations (`neosynaptex.py:_per_domain_gamma`, `xform_session_probe.py:gamma_probe`)
delegate to this canonical function. MFN research scripts retain OLS for historical comparison only.

## Manuscript Location (2026-04-03, Hole 12 resolution)

Canonical manuscript: `manuscript/XFORM_MANUSCRIPT_DRAFT.md`.
Root `XFORM_MANUSCRIPT_DRAFT.md` is a redirect pointer, not the canonical copy.
