# Substrate: bn_syn (BN-Syn — critical branching network)

Substrate class: simulated agent (spiking neural network at branching
ratio σ = 1).

Verdict per `evidence/replications/registry.yaml`: not currently filed
as a standalone replication entry. The substrate is referenced from
`evidence/gamma_ledger.json` and from `docs/CLAIM_BOUNDARY.md` Claim
C-003. No γ value from this substrate licenses cross-substrate
convergence under the current canon
(`../../CANONICAL_POSITION.md`).

## Contents

- `adapter.py` — neosynaptex adapter (mean-field directed-percolation
  branching process, `topo` = windowed firing rate, `cost` = windowed
  rate CV, theoretical anchor γ ≈ 1 at σ = 1 per Beggs & Plenz 2003).
- `__init__.py` — package surface.
- `src/bnsyn/` — vendored BN-Syn standalone simulation tree (AdEx
  neurons + STDP + criticality / temperature control).
- `specs/`, `formal/coq/`, `formal/tla/` — formal specifications
  (limited Coq proof on gain bounds; see
  `formal/coq/bnsyn/README.md` and `formal/tla/bnsyn/README.md`).
- `tests/`, `benchmarks/` — BN-Syn-internal test and benchmark trees.
- `UPSTREAM_README.md` — preserved upstream BN-Syn standalone-repo
  README (CLI workflow, `make quickstart-smoke`, canonical proof
  bundle). Refer to it for the BN-Syn standalone tooling.

## Requirements

The neosynaptex adapter requires only the parent repo dependencies
(`numpy`, `scipy`). The BN-Syn standalone simulation under `src/bnsyn/`
has its own additional requirements documented in `UPSTREAM_README.md`
and `pyproject.toml` of the upstream tree.

## Usage

Inside neosynaptex:

```python
from substrates.bn_syn.adapter import BnSynAdapter
```

For the standalone BN-Syn proof bundle (CLI), see `UPSTREAM_README.md`.

## Tests

The substrate ships its own test tree under `tests/`. Pass/fail counts
are not separately tracked at the parent neosynaptex level for this
substrate.

## Output

The neosynaptex adapter emits `(topo, thermo_cost)` traces that feed
the engine's γ pipeline. The standalone BN-Syn CLI emits its own proof
bundle (`artifacts/canonical_run/`) — see upstream README.

## Notes

- "Production-grade" / "enterprise-grade" / similar framing in the
  preserved upstream README is **not** endorsed at the canon level
  here; treat those phrases as upstream-marketing artefacts.
- Any γ measured from this substrate must trace to a row in
  `evidence/replications/registry.yaml` before being cited
  externally. As of this commit, no such row is filed.
