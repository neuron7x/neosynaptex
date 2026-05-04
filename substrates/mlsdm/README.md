# Substrate: mlsdm (Multi-Level Synaptic Dynamic Memory)

Substrate class: simulated agent (governed cognitive memory with
circadian wake/sleep, multi-level memory, moral filtering).

Verdict per `evidence/replications/registry.yaml`: not currently filed
as a standalone replication entry. No γ value from this substrate
licenses cross-substrate convergence under the current canon
(`../../CANONICAL_POSITION.md`).

## Contents

- `src/mlsdm/` — MLSDM package source (Python library, FastAPI HTTP
  server, CLI).
- `tests/` — unit, integration, load, benchmark, property-based.
- `deploy/`, `policies/`, `docs/`, `artifacts/` — standard project
  scaffolding.
- `UPSTREAM_README.md` — preserved upstream MLSDM README (Python
  library / HTTP API / CLI, install via `uv sync` or `pip install -e .`).

## Requirements

Adapter usage from neosynaptex needs only the parent repo dependencies.
The MLSDM package has its own dependency stack (FastAPI, uvicorn,
etc.); see `UPSTREAM_README.md` and the project's `pyproject.toml`.

## Usage

Inside neosynaptex this substrate provides observables consumable by
the engine. For the standalone HTTP / CLI usage, see
`UPSTREAM_README.md`.

## Tests

```bash
pytest substrates/mlsdm/tests -q
```

(The upstream MLSDM project tracks its own counts; they are not
aggregated into the parent neosynaptex test total.)

## Output

Adapter feeds observables into the γ pipeline. The standalone MLSDM
service emits its own response/metric artefacts.

## Notes

- "Production-ready" framing in the upstream README is not endorsed
  at the canon level.
- Any γ value from this substrate must trace to a registry entry
  under `evidence/replications/` before external citation.
