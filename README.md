# neosynaptex

> Cross-substrate γ-scaling diagnostics. γ ≈ 1 is treated as a **candidate
> regime marker under active falsification**, not a confirmed law and not a
> definition of intelligence. The canonical statement is in
> [`CANONICAL_POSITION.md`](CANONICAL_POSITION.md); the per-claim layering
> ladder is in [`docs/CLAIM_BOUNDARY.md`](docs/CLAIM_BOUNDARY.md).

## What it is

`neosynaptex` is a measurement protocol and Python implementation for
estimating a scaling exponent γ between a thermodynamic-cost proxy `K` and
a topological-complexity proxy `C` on coupled dynamical substrates, under
the working ansatz `K(C) ~ κ₀ · C^{-γ}`. The protocol enforces:

- per-substrate adapter-code hash binding (a drifted adapter refuses to load),
- pre-registered null families (shuffled, IAAFT, AR(1), block-bootstrap, plus
  the wavelet-phase null in `core/nulls/`),
- per-substrate prereg + verdict in `evidence/replications/registry.yaml`,
- a canon-closure overclaim gate (`tools/audit/claim_overclaim_gate.py`).

There is **one anchored proven row** (Lemma 1, Kuramoto on dense graphs,
γ̂ = 0.9923 numerically); every other substrate row is empirical and
substrate-conditional.

## Current evidence state

Source of truth: `evidence/replications/registry.yaml`.

Falsifying / null-result records (reduce, do not extend, the γ ≈ 1 framing):

- `binance_btcusdt_1h_pilot_2026_04_14` — γ ≈ 0, r² ≈ 0.001, all nulls
  indistinguishable. Hourly BTC/USDT log-returns are inconsistent with a
  γ ≈ 1 marker at this resolution.
- `fred_indpro_pilot_2026_04_14` — verdict pending; bounded-secondary, does
  not license any market criticality claim.
- `physionet_nsr2db_n5_multifractal_2026_04_14` — verdict
  `theory_revision`. Across n = 5 NSR subjects γ mean = 0.50, std = 0.44,
  range [0.07, 1.09]. The cardiac substrate is **not** consistent with
  universal γ ≈ 1 at the 5-subject pilot level.
- `physionet_nsr2db_nsr001_pilot_2026_04_14` — superseded by the
  multifractal n = 5 result; the n = 1 outlier is retained for record only.
- The EEG MNE eegbci pilot (n = 20) and the within-substrate falsification
  for stateless-LLM inference (`experiments/lm_substrate/`) are documented
  separately and do not pass the cross-substrate convergence claim either.

The single positive within-substrate finding currently on file:

- `physionet_chf2db_pathology_contrast_2026_04_14` — verdict `support`. The
  2D `(h(q=2), Δh)` cardiac fingerprint discriminates n = 5 healthy NSR
  from n = 5 CHF; Welch t = −4.05, Cohen d = −2.56 on `h(q=2)`. This is a
  within-cardiac contrast at pilot scale; it does **not** license clinical,
  diagnostic, or cross-substrate conclusions.

Net position: γ ≈ 1 has **no surviving cross-substrate convergence claim**
at this commit. It remains a candidate regime marker, falsifiable per
substrate.

## Repository layout

- `neosynaptex.py` — engine module: γ-scaling, Jacobian/spectral, phase
  state and adapter health monitor.
- `core/` — measurement primitives: `gamma.py`, `gamma_registry.py`,
  `nulls/` (shuffled, IAAFT, AR(1), block-bootstrap, wavelet-phase),
  `iaaft.py`, `multiverse.py`, `falsification.py`, plus axiom/contract
  helpers. Approximately 60 modules.
- `contracts/` — invariant enforcement (`invariants.py`,
  `truth_criterion.py`, `provenance.py`, `claim_strength.py`,
  `fail_closed.py`).
- `substrates/` — per-substrate adapters and per-substrate READMEs. Current
  substrates: `bn_syn`, `bridge`, `cfp_diy`, `cns_ai_loop`, `eeg_physionet`,
  `eeg_resting`, `geosync_market`, `gray_scott`, `hippocampal_ca1`, `hrv`,
  `hrv_fantasia`, `hrv_physionet`, `kuramoto`, `lotka_volterra`,
  `market_crypto`, `market_fred`, `mfn`, `mlsdm`, `mycelium`,
  `physionet_hrv`, `serotonergic_kuramoto`, `zebrafish`.
- `evidence/` — registries and ledgers (`gamma_ledger.json`,
  `replications/`, `levin_bridge/`, `surrogates/`, `manifests/`).
- `evl/` — evidence verification ledger.
- `experiments/` — replication runners (e.g. `lm_substrate/` for the
  stateless-LLM null result, `lemma_1_verification/`).
- `tests/` — 136 `test_*.py` files (145 .py files total in `tests/`).
- `tools/audit/` — overclaim gate, replication index check, horizon-trace
  lint, hash-binding gate.
- `docs/` — `CLAIM_BOUNDARY.md`, `REPLICATION_PROTOCOL.md`,
  `NULL_MODEL_HIERARCHY.md`, `MEASUREMENT_METHOD_HIERARCHY.md`, plus the
  archived pre-canon material under `docs/archive/`.
- `formal/` — Coq and TLA+ specifications (skeletons; see
  `formal/coq/bnsyn/README.md` and `formal/tla/bnsyn/README.md`).
- `manuscript/` — arXiv submission source for the Kuramoto Lemma 1.
- `.github/workflows/` — 21 CI workflow files (overclaim gate, ledger
  binding, claim-status, replication index, kill-signal coverage,
  measurement contract, semantic-drift, etc.).

## Requirements

Hard runtime dependencies (`pyproject.toml`):

- Python ≥ 3.10
- `numpy >= 2.2.6`
- `scipy >= 1.15.3`

Replication runners and dev tooling additionally need: `PyWavelets`,
`wfdb`, `scikit-learn`, `pytest`, `pytest-cov`, `pytest-timeout`, `mypy`,
`ruff`, `import-linter`, `pyyaml`. See `pyproject.toml [project.optional-dependencies]`.

Some replication scripts download external datasets (PhysioNet, FRED,
Binance public REST). Network access is not assumed by tests.

## Installation

```bash
pip install -e .[dev]
```

## Usage

The smallest in-tree demonstration:

```python
from neosynaptex import Neosynaptex
# Adapter classes live under substrates/; see each substrate README for
# the import path and contract.
```

Replication scripts at the repo root each correspond to one registry
entry, e.g.:

```bash
python run_btcusdt_replication.py            # falsifying record
python run_nsr2db_hrv_multifractal.py        # theory_revision record
python run_chf2db_hrv_contrast.py            # within-cardiac support record
python run_null_family_screening.py          # null-screen pipeline
```

Each script writes its artifact under `evidence/` or `results/`. The
expected output structure is documented inside the matching prereg under
`evidence/replications/<slug>/`.

## Tests

```bash
pytest -q
```

The repo currently ships **136 `test_*.py` files** under `tests/`. The
runtime hash-binding gate refuses to load if the on-disk substrate-adapter
SHA-256 does not match the value pinned in `evidence/gamma_ledger.json`;
this is by design and not a test failure. To rebind after an intentional
adapter change, follow `tools/audit/replication_baseline.json`.

## Output

- `evidence/gamma_ledger.json` — pinned per-substrate γ records and adapter
  hashes (the binding source).
- `evidence/replications/registry.yaml` — pre-registration index; canonical
  list of substrate verdicts.
- `evidence/proof_chain.jsonl` — append-only proof-chain log.
- `results/`, `reports/`, `figures/` — per-script artifacts.

## Notes and limits

- γ ≈ 1 is **not** validated as a cross-substrate law. Treat any artefact
  that says otherwise as out-of-canon (see `CANONICAL_POSITION.md` and the
  forbidden-phrase list in `tools/audit/claim_overclaim_gate.py`).
- The CNS-AI-loop substrate is **historical-exploratory only**; the
  underlying corpus is non-reproducible. See
  `docs/CLAIM_BOUNDARY_CNS_AI.md`.
- Lemma 1 (Kuramoto, dense graphs) is the only proved row. It is a
  reformulation of Restrepo–Ott–Hunt (2005) and validity depends on the
  RoH spectral assumptions; non-trivial spectral topologies remain open.
- Pareidolia, mystification and "γ defines intelligence" framings are
  explicitly forbidden and gated mechanically.

## License

AGPL-3.0-or-later. See `LICENSE` and `LICENSE_BOUNDARIES.md`.
