## DNCA — Distributed Neuromodulatory Cognitive Architecture

Cognition is the regulated succession of metastable dominant regimes over a shared
predictive state. Six neuromodulatory operators (DA, ACh, NE, 5-HT, GABA, Glu) compete
through Lotka-Volterra dynamics, couple via Kuramoto phase oscillators, and maintain
metastability through active regulation. Each operator runs its own Dominant-Acceptor
Cycle over a SharedPredictiveState.

```python
from neuron7x_agents.dnca import DNCA
system = DNCA(state_dim=64, hidden_dim=128)
output = system.step(sensory_input, reward=0.5)
# output.dominant_nmo, output.r_order, output.mismatch, ...
```

**Benchmarks** (4 cognitive tasks): N-Back, Stroop, WCST, Metastability health.
**Gamma probe**: TDA-based gamma-scaling measurement. gamma_DNCA ~ +1.0 (consistent with gamma_WT = +1.043, McGuirl 2020 zebrafish).

```bash
python -m neuron7x_agents.dnca.smoke_test   # quick validation
python -m pytest tests/ -q                   # full test suite
```

---

<p align="center">
<pre align="center">
                    ╔══════════════════════════════════════╗
                    ║                                      ║
                    ║     ◈ ─── ◈ ─── ◈ ─── ◈ ─── ◈      ║
                    ║     │     │     │     │     │        ║
                    ║     ◈ ─── ◈ ─── ◈ ─── ◈ ─── ◈      ║
                    ║     │     │     │     │     │        ║
                    ║     ◈ ─── ◈ ─── ◈ ─── ◈ ─── ◈      ║
                    ║     │     │     │     │     │        ║
                    ║     ◈ ─── ◈ ─── ◈ ─── ◈ ─── ◈      ║
                    ║                                      ║
                    ╚══════════════════════════════════════╝
</pre>
</p>

<h1 align="center">neuron7x-agents</h1>

<p align="center">
<strong>Hybrid Cognitive Functions for Intelligent Systems</strong>
</p>

<p align="center">
<em>Biologically-inspired cognitive primitives engineered as composable modules<br>for AI agents, models, and multi-agent architectures.</em>
</p>

<p align="center">
<a href="https://github.com/neuron7xLab/neuron7x-agents/actions"><img src="https://github.com/neuron7xLab/neuron7x-agents/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue" alt="Python">
<img src="https://img.shields.io/badge/tests-76%20passed-brightgreen" alt="Tests">
<img src="https://img.shields.io/badge/license-MIT-green" alt="License">
<img src="https://img.shields.io/badge/typed-strict-blue" alt="Typed">
</p>

---

## What this is

A library of **cognitive functions** — not wrappers, not prompt templates, not LangChain plugins.

Each module implements a specific **biologically-grounded mechanism** as executable Python with formal properties, deterministic tests, and composable interfaces. The mechanisms come from neuroscience, control theory, and epistemology. They are engineered for integration into AI agents, reasoning systems, and multi-agent architectures.

```
┌─────────────────────────────────────────────────────────────────┐
│                        HybridAgent                               │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐   │
│  │   NCE        │    │   SERO        │    │   Kriterion       │   │
│  │   Cognitive  │◄──►│   Regulation  │◄──►│   Verification    │   │
│  │   Engine     │    │   HVR+Immune  │    │   Gate+Anti-GM    │   │
│  └──────┬──────┘    └──────┬───────┘    └────────┬──────────┘   │
│         │                  │                      │              │
│  ┌──────┴──────────────────┴──────────────────────┴──────────┐  │
│  │              Cortical Column (shared primitive)             │  │
│  │         Creator → Critic → Auditor → Verifier              │  │
│  └────────────────────────────────────────────────────────────┘  │
│         │                  │                      │              │
│  ┌──────┴──────────────────┴──────────────────────┴──────────┐  │
│  │           Evidence + Confidence + Markov Blanket           │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## The three pillars

### NCE — Neurosymbolic Cognitive Engine

Reasoning primitives inspired by computational neuroscience:

| Primitive | Mechanism | Source |
|-----------|-----------|--------|
| **Predictive Coding** | predict → observe → error → update | Friston free energy principle |
| **Abductive Inference** | competing hypotheses ranked by parsimony × falsifiability | Peirce / Harman |
| **Reductio ad Absurdum** | assume negation, seek contradiction with established facts | Classical logic |
| **Epistemic Foraging** | "what don't I know that would most change this?" | Active inference |

Domain adaptation: CODE (correctness-first), ANALYSIS (multi-hypothesis), RESEARCH (maximize unknowns), CREATIVE (maximize surprise × coherence).

### SERO — Hormonal Vector Regulation

Control theory for agent homeostasis — executable equations, not metaphors:

| Equation | Name | Formula |
|----------|------|---------|
| **Eq.3** | Throughput | `T(t) = max(T_min, T_0 · (1 - α · Ŝ(t)))` |
| **Eq.4** | Safety invariant | `∀t: T(t) ≥ T_min > 0` |
| **Eq.6** | Stress estimator | `Ŝ(t) = Σ(s_i · u_i) / Σ(s_i)` |
| **Eq.7** | Damping | `Ŝ(t) ← Ŝ(t-1) + γ · (Ŝ_raw - Ŝ(t-1))` |

**Key property**: throughput never drops to zero. T_min > 0 is guaranteed by construction, not by hope. Damping prevents oscillation. α is the critical parameter (safe range: 0.30–0.55).

**Bayesian Immune System**: dual-signal detection. Single-channel alert → quarantine. Two independent channels → real threat. P(autoimmune) reduced 12× vs single-signal.

### Kriterion — Epistemic Verification

Fail-closed evaluation gates:

| Principle | Implementation |
|-----------|---------------|
| **Fail-closed** | Missing evidence = score cap, not gap to fill with judgment |
| **Evidence tiering** | GIVEN / INFERRED / SPECULATED — never mixed |
| **Anti-gaming** | Artifact reuse detection, self-review loop detection, provenance gaps |
| **0.95 gate** | Proof OR reproducible evidence + reductio completed + zero objections |

---

## Quick start

```bash
pip install neuron7x-agents
```

```python
from neuron7x_agents import HybridAgent
from neuron7x_agents.cognitive.engine import Domain
from neuron7x_agents.regulation.hvr import SeverityWeight
from neuron7x_agents.primitives.evidence import EvidenceItem, EvidenceTier, EvidenceSource

# Create a hybrid cognitive agent
agent = HybridAgent(domain=Domain.ANALYSIS)

# Process a query with stress monitoring
response = agent.process(
    "What drives gamma oscillations in cortical circuits?",
    stress_channels=[
        SeverityWeight("cpu", severity=10.0, current_value=0.3),
        SeverityWeight("memory", severity=5.0, current_value=0.1),
    ],
    evidence=[
        EvidenceItem(
            "PV+ interneurons generate gamma via PING mechanism",
            EvidenceTier.GIVEN,
            EvidenceSource.PEER_REVIEWED,
            provenance="doi:10.1038/nn.2156",
        ),
        EvidenceItem(
            "Gamma power correlates with cognitive load",
            EvidenceTier.GIVEN,
            EvidenceSource.EXPERIMENT,
            provenance="doi:10.1016/j.neuron.2009.06.016",
        ),
    ],
)

print(f"Confidence: {response.confidence.level.value}")      # "reasonable"
print(f"Throughput: {response.regulation_throughput:.2f}")     # 1.00
print(f"Gate: {response.gate_verdict.status.value}")          # "passed"
print(f"Trustworthy: {response.is_trustworthy}")              # True
```

---

## Confidence calibration

```python
from neuron7x_agents.primitives.confidence import enforce_gate, ProofGate

# Try to claim 0.97 confidence without proof → FORCED DOWNGRADE
result = enforce_gate(0.97)
assert result.calibrated_score == 0.94  # downgraded
assert result.was_downgraded is True

# With valid proof gate → passes
gate = ProofGate(
    has_formal_proof=True,
    reductio_completed=True,
    unrebutted_objections=0,
)
result = enforce_gate(0.97, gate)
assert result.calibrated_score == 0.97  # earned
```

---

## Safety invariant

```python
from neuron7x_agents.regulation.hvr import HormonalRegulator, SeverityWeight

reg = HormonalRegulator()

# 100 ticks of maximum stress
for _ in range(100):
    reg.tick([SeverityWeight("chaos", severity=100.0, current_value=1.0)])

# T_min NEVER violated — guaranteed by construction (Eq.4)
assert reg.safety_invariant_holds()
assert reg.state.throughput >= 0.05
```

---

## Architecture

```
src/neuron7x_agents/
├── primitives/          ← Shared cognitive building blocks
│   ├── column.py        ← CorticalColumn: adversarial multi-role reasoning
│   ├── confidence.py    ← Calibration gates (0.95 forbidden without proof)
│   └── evidence.py      ← Markov blanket: GIVEN / INFERRED / SPECULATED
├── cognitive/           ← NCE: Neurosymbolic Cognitive Engine
│   ├── engine.py        ← CognitiveEngine: orchestrates strategies
│   └── strategies.py    ← PredictiveCoding, Abduction, Reductio, Foraging
├── regulation/          ← SERO: Hormonal Vector Regulation
│   ├── hvr.py           ← HormonalRegulator: Eq.3/4/6/7
│   └── immune.py        ← BayesianImmune: dual-signal threat detection
├── verification/        ← Kriterion: Epistemic Verification
│   ├── gate.py          ← EpistemicGate: fail-closed evidence gates
│   └── anti_gaming.py   ← AntiGamingDetector: reuse/self-review/provenance
└── agents/
    └── hybrid.py        ← HybridAgent: NCE + SERO + Kriterion composed
```

---

## Part of the neuron7xLab cognitive stack

```
                        ┌─────────────────────┐
                        │   neuron7x-agents    │  ← YOU ARE HERE
                        │  cognitive functions  │
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
   ┌──────────┴──────┐  ┌────────┴────────┐  ┌────────┴──────────┐
   │ mycelium-fractal │  │     bnsyn        │  │  Hippocampal-CA1  │
   │ -net (MFN)       │  │  phase-dynamics  │  │  -LAM             │
   │                  │  │                  │  │                   │
   │ R-D substrate    │  │ Spiking dynamics │  │ Memory system     │
   │ TDA + causal     │  │ STDP + criticality│ │ theta-SWR replay  │
   │ gamma-scaling    │  │ sleep-wake       │  │ HippoRAG for LLM  │
   └──────────────────┘  └─────────────────┘  └───────────────────┘
              │                    │                     │
              └────────────────────┼────────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │       mlsdm          │
                        │  governed cognitive   │
                        │  memory for LLMs      │
                        └─────────────────────┘
```

---

## Design principles

1. **Evidence over eloquence.** A claim that cannot survive provenance checking, tier enforcement, and anti-gaming detection does not get scored — it gets blocked.

2. **Fail closed.** Missing evidence is a constraint, not a gap to fill with judgment. No system should be more confident than its evidence permits.

3. **Executable equations.** Every control-theoretic mechanism maps to a numbered equation with formal properties and deterministic tests. "Biologically inspired" means the math works, not that it sounds nice.

4. **Composable primitives.** Each cognitive function is a standalone module with clear inputs and outputs. The HybridAgent is one composition — not the only one.

5. **Adversarial by default.** The CorticalColumn runs Creator against Critic against Auditor. Sycophantic agreement is treated as a failure mode, not a feature.

---

## Tests

```bash
# 76 tests, 0.15s, strict markers, typed
python -m pytest -v

# With coverage
python -m pytest --cov=neuron7x_agents --cov-report=term-missing

# Lint + type check
ruff check src/
mypy src/
```

---

## Author

Researcher

Building the cognitive infrastructure for the next generation of intelligent systems.

*gamma = coherence. not a metric — a consequence.*

---

<p align="center">
<sub>neuron7xLab · 2026 · MIT License</sub>
</p>
