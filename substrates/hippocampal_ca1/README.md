# Substrate: hippocampal_ca1

Substrate class: simulated agent (CA1 laminar architecture model with
AdEx-style neurons and Graupner–Brunel calcium-based plasticity).

Verdict per `evidence/replications/registry.yaml`: not currently filed
as a standalone replication entry. No γ value from this substrate
licenses cross-substrate convergence under the current canon
(`../../CANONICAL_POSITION.md`).

## Contents

- `adapter.py` — neosynaptex adapter for the CA1 model trace.
- `core/`, `plasticity/`, `validation/`, `tools/` — CA1 model source
  trees vendored from the standalone Hippocampal-CA1-LAM project.
- `examples/`, `data/`, `configs/`, `scripts/` — supporting material
  for the standalone project.
- `test_golden_standalone.py`, `tests/` — golden / unit / integration
  tests of the standalone CA1 model.
- `UPSTREAM_README.md` — preserved upstream README (CA1-LAM v2.0
  workflow, `quick_start.sh`, demo script). Refer to it for the
  standalone simulation-tool instructions.
- `docs/README.md` — documentation index for the CA1 subproject.

## Requirements

Adapter usage from neosynaptex needs only the parent repo dependencies.
The standalone CA1 model has its own `requirements.txt`; see
`UPSTREAM_README.md`.

## Usage

Inside neosynaptex:

```python
from substrates.hippocampal_ca1.adapter import ...  # see adapter.py
```

For the standalone simulation entrypoint, see `UPSTREAM_README.md`
and `examples/`.

## Tests

`tests/` and `test_golden_standalone.py` belong to the upstream CA1
project. They are not aggregated into the parent neosynaptex test
count.

## Output

Adapter feeds windowed observables to the engine. The standalone
project emits its own analysis figures and golden artefacts.

## Notes

- "Production-Grade", "100% reproducible", "8-phase evolution plan"
  framings in the upstream README are not endorsed at the canon
  level. Cell-count and parameter citations (e.g. Pachicano 2025,
  Graupner-Brunel 2012) trace to `docs/BIBLIOGRAPHY.md` of the
  upstream tree; they are not γ-program evidence.
- Any γ value from this substrate must trace to a registry entry
  under `evidence/replications/`. None is filed at this commit.
