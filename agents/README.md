# neuron7x-agents

> Cognitive primitives library, vendored under the neosynaptex repo. The
> γ-related framing must be read against the parent canon
> ([`../CANONICAL_POSITION.md`](../CANONICAL_POSITION.md)) — γ ≈ 1 is a
> candidate marker under active falsification, not a confirmed law.

## What it is

A Python library of biologically-inspired cognitive components designed to
be composed inside agent pipelines. The package layout under
`src/neuron7x_agents/` includes:

- `primitives/` — shared building blocks (`column.py`, `confidence.py`,
  `evidence.py`).
- `cognitive/` — NCE (Neurosymbolic Cognitive Engine): `engine.py`,
  `strategies.py` (predictive coding, abduction, reductio, foraging).
- `regulation/` — SERO (Hormonal Vector Regulation): `hvr.py`,
  `immune.py`.
- `verification/` — Kriterion verification gates and the
  `kriterion/benchmark/` synthetic-demo benchmark.
- `dnca/` — distributed neuromodulatory cognitive architecture experiment
  (Lotka–Volterra × Kuramoto coupling).
- `ensemble/`, `agents/` — composite agent assemblies.

## Contents

- `src/neuron7x_agents/` — package source.
- `tests/` — 9 `test_*.py` files (141 test functions by static count).
- `pyproject.toml` — package metadata.
- `examples/`, `docs/`, `manuscript/`, `scripts/` — supporting material.

## Requirements

Python ≥ 3.10. Concrete pinned dependencies live in `pyproject.toml`; some
requirements (e.g. for the manuscript build) could not be verified
automatically.

## Installation

From the agents directory:

```bash
pip install -e .
```

## Usage

```python
from neuron7x_agents import HybridAgent
from neuron7x_agents.cognitive.engine import Domain

agent = HybridAgent(domain=Domain.ANALYSIS)
```

The DNCA experiment exposes a smoke test:

```bash
python -m neuron7x_agents.dnca.smoke_test
```

## Tests

```bash
python -m pytest -q
```

`tests/` contains 9 test files with 141 test functions by static
enumeration. Pass/fail counts under the parent neosynaptex test runner are
not separately tracked here.

## Output

Library artefacts (no canonical evidence files). The Kriterion benchmark
under `src/neuron7x_agents/verification/kriterion/benchmark/` produces
`metrics.json` and per-case JSON in `results/` from synthetic fixtures only.

## Notes

- The DNCA "γ probe" output is **not** a substrate γ-row in
  `evidence/gamma_ledger.json`; it is an internal observable of the agent
  loop and is not licensed to claim cross-substrate γ ≈ 1 convergence
  (see `../CANONICAL_POSITION.md`).
- The Kriterion benchmark is explicitly a synthetic demonstration of the
  evaluation pipeline; it does not claim model superiority on any external
  benchmark.
