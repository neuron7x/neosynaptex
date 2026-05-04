# Substrate: mfn (MyceliumFractalNet)

Substrate class: simulated agent (reaction–diffusion field with
topological / causal analysis).

Verdict per `evidence/replications/registry.yaml`: not currently filed
as a standalone replication entry. No γ value from this substrate
licenses cross-substrate convergence under the current canon
(`../../CANONICAL_POSITION.md`).

## Contents

- `adapter.py` — neosynaptex adapter (R-D field state → `(topo, cost)`
  trace). Located in `mycelium_pre_admission_adapter.py` at the
  parent `substrates/` root for one of the entry points.
- `src/mycelium_fractal_net/` — vendored MFN package source.
- `examples/`, `experiments/`, `tests/`, `infra/`, `docs/` —
  standard MFN project layout.
- `UPSTREAM_README.md` — preserved upstream MFN README (R-D + TDA +
  causal pipeline, package install variants `[bio]` / `[science]` /
  `[accel]` / `[frontier]`, comparison table vs FiPy/FEniCSx/etc.).

## Requirements

Adapter usage from neosynaptex needs only the parent repo dependencies.
Full MFN feature set has its own dependency tree (numpy, pydantic,
scipy, gudhi, multipers, DAGMA, DoWhy, numba). See
`UPSTREAM_README.md`.

## Usage

Inside neosynaptex:

```python
# Adapter glue lives in substrates/mycelium_pre_admission_adapter.py
# and substrates/mfn/. See respective files for the entry surface.
```

For the MFN standalone usage, see `UPSTREAM_README.md`.

## Tests

`tests/` belongs to the upstream MFN project. The advertised "2428
tests / 82% coverage" badges describe the upstream MFN repository, not
the neosynaptex test count.

## Output

The adapter emits R-D-derived `(topo, thermo_cost)` traces. MFN
itself emits TDA / causal / persistence-diagram artefacts; see the
upstream README and `experiments/`.

## Notes

- "The only open-source framework that …", comparison-table superlatives
  and similar upstream marketing are not endorsed at the canon level.
- Any γ from this substrate must trace to a registry entry under
  `evidence/replications/` before external citation.
