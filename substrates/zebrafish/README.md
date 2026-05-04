# Substrate: zebrafish

Substrate class: simulated agent (zebrafish pigment-pattern ABM).

Verdict per `evidence/replications/registry.yaml`: not currently filed as a
standalone replication entry. Historical γ ≈ 1.043 (n = 47, R² = 0.82) is
referenced in `evidence/gamma_ledger.json` as a pre-registry pilot and is
**not** licensed to claim cross-substrate convergence under the current
canon (see `../../CANONICAL_POSITION.md`).

## Contents

- `adapter.py` — substrate adapter wired into the neosynaptex engine.
- `__init__.py` — package surface.
- `src/` — vendored upstream pipeline from McGuirl, Volkening &
  Sandstede, "Topological data analysis of zebrafish patterns,"
  *PNAS* 2020, 117 (10) 5113–5124
  (https://doi.org/10.1073/pnas.1917763117). Original repo:
  https://github.com/sandstede-lab/Quantifying_Zebrafish_Patterns.
- `UPSTREAM_README.md` — mirror of the upstream README (preserved
  verbatim for attribution; see "Upstream usage" below).

## Requirements

- Python and matplotlib for the pipeline glue.
- MATLAB and Ripser.py v0.3.2 for the upstream TDA pipeline; required
  only when regenerating barcodes from raw cell-coordinate inputs.

The neosynaptex `BnSynAdapter`-style consumer here only needs the
already-derived feature trace; MATLAB is not required to import or run
the adapter inside neosynaptex.

## Usage

Inside neosynaptex (using cached features):

```python
from substrates.zebrafish import ZebrafishAdapter  # see adapter.py
```

For the upstream pattern-quantification pipeline see the original
McGuirl et al. instructions preserved below under "Upstream usage".

## Tests

No automated tests are filed for this substrate at this commit.

## Output

Adapter feeds windowed `(topo, thermo_cost)` into the engine. The
underlying barcode artefacts are produced by the upstream pipeline.

## Notes

- This substrate is treated as agent-based-model output, not as in-vivo
  data.
- Any γ value reported from this substrate must trace to a registry
  entry under `evidence/replications/`. None is filed at this commit.
- The upstream code and figures retain their original authorship
  (McGuirl, Volkening, Sandstede). Modifications, if any, are limited
  to adapter glue under `adapter.py`.

## Upstream usage (verbatim, preserved for attribution)

> Source: McGuirl, Volkening, Sandstede 2020 — see
> https://github.com/sandstede-lab/Quantifying_Zebrafish_Patterns.
> The full original instructions are preserved at
> `UPSTREAM_README.md` in this directory if present, and were the
> previous content of this file. The instructions describe a MATLAB +
> Python pipeline that is not part of the neosynaptex test path.
