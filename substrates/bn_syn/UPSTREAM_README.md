# BN-Syn Thermostated Bio-AI System

[![canonical-proof-spine](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/actions/workflows/canonical-proof-spine.yml/badge.svg)](https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics/actions/workflows/canonical-proof-spine.yml)
[![neurodrift-cross-commit](https://img.shields.io/badge/neurodrift-cross--commit%20analytics-blue)](./.github/workflows/canonical-proof-spine.yml)
[![oidc-attestation](https://img.shields.io/badge/OIDC-attest--canonical--bundle-darkgreen)](./.github/workflows/canonical-proof-spine.yml)

BN-Syn is a deterministic simulation repository for phase-controlled emergent neural dynamics with AdEx neurons, STDP plasticity, and criticality control.

This repository now uses **one canonical entry surface** for first contact: this `README.md`.
Read this page first, run the one-command smoke path, and then inspect the generated report in the fixed order below.
For project status boundaries, see [docs/STATUS.md](docs/STATUS.md).
For the post-merge baseline procedure, see [docs/GENESIS_RUN_PLAN.md](docs/GENESIS_RUN_PLAN.md).

## Emergent dynamics and orchestration (UA)

Емерджентна динаміка означає, що складна поведінка системи з’являється з взаємодії багатьох простих елементів. У мозку окремі нейрони передають сигнали локально, але через нелінійні зв’язки, синхронізацію ритмів і зворотні зв’язки вони формують великомасштабні мережеві патерни. Ці патерни відповідають за когнітивні стани — увагу, пам’ять, прийняття рішень. У теорії складності це називають самоорганізацією: порядок виникає без центрального диригента.

Термін оркестрація описує умови (зв’язки, часові затримки, баланс збудження й гальмування), які спрямовують цю самоорганізацію. Тобто система не програмується жорстко, а налаштовується так, щоб її компоненти синхронізувалися і породжували нові функції на рівні всієї мережі.

Для формалізованого технічного трактування цієї ідеї див. [docs/EMERGENT_ORCHESTRATION_ATLAS.md](docs/EMERGENT_ORCHESTRATION_ATLAS.md).


## Single canonical entry surface

### One-command first run

For a clean first run, use exactly one command:

```bash
make quickstart-smoke
```

`make quickstart-smoke` is the **deterministic one-command execution contract** for humans evaluating the repository end-to-end from a fresh checkout. It creates the local environment, verifies the CLI, runs the canonical proof pipeline, and checks that the canonical artifact bundle is present and shaped correctly.

### Underlying canonical proof command

The scientific proof contract remains:

```bash
bnsyn run --profile canonical --plot --export-proof
```

Use the raw CLI command when you already have the environment prepared and want the direct proof bundle. Use `make quickstart-smoke` when you want the full first-run path with setup and verification.

### Terminal experience for demos

The canonical CLI now emits a richer terminal presentation on `stderr` during `bnsyn run --profile canonical --plot --export-proof`, `bnsyn demo-product`, and `bnsyn validate-bundle` so local reviewers can immediately see:

- which canonical mode is running;
- where the bundle is being written;
- the primary visual and manifest paths;
- the next proof or product command to execute.

Color is enabled automatically for interactive terminals, respects the community-standard `NO_COLOR` opt-out, and can be forced locally with:

```bash
BNSYN_CLI_THEME=neon bnsyn run --profile canonical --plot --export-proof
```

Use `BNSYN_CLI_THEME=plain` when recording plain-text CI logs or minimal shell sessions.

The export-proof canonical run now emits the product review surface as part of the same local output directory, so after `bnsyn run --profile canonical --plot --export-proof` you can immediately:

```bash
bnsyn validate-bundle artifacts/canonical_run
```

For proof-only contract checks, `bnsyn proof-validate-bundle <artifact_dir>` remains available as the narrower validator.

## Canonical Project Vectors (Permanent)

- **V1 — Result:** [NORMATIVE][CLM-0001] one canonical proof command, `bnsyn run --profile canonical --plot --export-proof`, must generate visual and metrics evidence of emergent network dynamics.
- **V2 — Narrative:** [NORMATIVE][CLM-0002] repository documentation must explain mechanism, measurements, and reproducibility for technical research readers.
- **V3 — Audience:** [NORMATIVE][CLM-0003] repository surfaces must stay runnable and inspectable for AI lab, neuroscience grant, and technical investor diligence.

All contributor work is expected to strengthen these vectors and avoid drift.

## What the one-command path does

`make quickstart-smoke` executes this fixed user journey:

1. prepare `.venv` and install the package in editable mode;
2. verify `bnsyn --help` and `bnsyn run --help`;
3. run `bnsyn run --profile canonical --plot --export-proof --output artifacts/canonical_run`;
4. assert the canonical artifact contract is complete.

That means the first human-facing answer is deterministic: run one command, then inspect one report.

## Inspect results in this order

After either `make quickstart-smoke` or the raw canonical proof command, inspect artifacts in this exact sequence:

1. `artifacts/canonical_run/index.html` — the primary human-readable report.
2. `artifacts/canonical_run/product_summary.json` — machine-readable executive summary.
3. `artifacts/canonical_run/proof_report.json` — gate verdict for the canonical proof bundle.
4. `artifacts/canonical_run/summary_metrics.json` — headline run metrics.
5. `artifacts/canonical_run/criticality_report.json` — criticality evidence and band behavior.
6. `artifacts/canonical_run/avalanche_report.json` — avalanche structure evidence.
7. `artifacts/canonical_run/phase_space_report.json` — state-space trajectory evidence.
8. `artifacts/canonical_run/emergence_plot.png` and phase-space PNGs — visual confirmation.
9. `artifacts/canonical_run/population_rate_trace.npy`, `sigma_trace.npy`, `coherence_trace.npy` — raw trace evidence.
10. `artifacts/canonical_run/run_manifest.json` — reproducibility metadata and artifact hashes.

## Canonical artifact guide

| Artifact | Read it as | Why it matters |
|---|---|---|
| `index.html` | final report | default entrypoint for a human reviewer |
| `product_summary.json` | compact verdict payload | fastest machine-readable summary |
| `proof_report.json` | proof gate decision | tells you PASS/FAIL for the bundle |
| `summary_metrics.json` | headline measurements | gives the top-level run numbers |
| `criticality_report.json` | criticality interpretation | shows sigma / branching admissibility evidence |
| `avalanche_report.json` | avalanche interpretation | shows event-structure evidence |
| `phase_space_report.json` | dynamical interpretation | shows trajectory and occupancy evidence |
| `emergence_plot.png` | primary visual | quickest visual confirmation of emergent activity |
| `phase_space_rate_sigma.png` | rate-vs-sigma visual | visualizes one phase-space projection |
| `phase_space_rate_coherence.png` | rate-vs-coherence visual | visualizes complementary phase-space projection |
| `phase_space_activity_map.png` | occupancy visual | shows where the system spends time |
| `population_rate_trace.npy` | raw rate trace | source data for phase-space evidence |
| `sigma_trace.npy` | raw sigma trace | source data for criticality evidence |
| `coherence_trace.npy` | raw coherence trace | source data for synchrony evidence |
| `run_manifest.json` | reproducibility ledger | binds command, hashes, and bundle contract |
| `robustness_report.json` | repeat-run admissibility | summarizes the fixed 10-seed robustness sweep |
| `envelope_report.json` | admissibility envelope | captures allowed operating band behavior |
| `avalanche_fit_report.json` | fit validity evidence | validates avalanche fit quality |

## Canonical proof path (single command)

```bash
bnsyn run --profile canonical --plot --export-proof
```

Base canonical artifact contract (`bnsyn run --profile canonical --plot`):
- `emergence_plot.png`
- `summary_metrics.json`
- `run_manifest.json`
- `criticality_report.json`
- `avalanche_report.json`
- `phase_space_report.json`
- `population_rate_trace.npy`
- `sigma_trace.npy`
- `coherence_trace.npy`
- `phase_space_rate_sigma.png`
- `phase_space_rate_coherence.png`
- `phase_space_activity_map.png`
- `avalanche_fit_report.json`
- `robustness_report.json`
- `envelope_report.json`

Export-proof augmented artifact contract (`bnsyn run --profile canonical --plot --export-proof`):
- all base artifacts
- `proof_report.json`

This is the primary buyer/reviewer command path.

## Interpretation and claim boundaries

Supported from the canonical proof bundle:
- direct measured traces from one run: spike raster events, sigma trace, active-fraction coherence trace, spike-rate trace
- derived summary statistics in `summary_metrics.json`
- reproducibility metadata and artifact hashes in `run_manifest.json`
- `criticality_report.json`
- `avalanche_report.json`
- `phase_space_report.json`

Not supported from this proof command alone:
- biological equivalence to in vivo neural tissue
- claims about cognition, consciousness, or AGI-level capability
- generalization claims beyond tested parameter settings and implemented model scope

## Canonical user path (clone -> install -> run -> inspect)

```bash
git clone https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics.git
cd bnsyn-phase-controlled-emergent-dynamics
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
./.venv/bin/python -m bnsyn run --profile canonical --plot --export-proof
```

## Quickstart

```bash
make quickstart-smoke
```

## Canonical test gate command

```bash
make test-gate
```

## FAQ

### Which command should a new user run first?

Run `make quickstart-smoke`. It is the first-run path that performs setup, CLI verification, canonical execution, and artifact-contract checks in one deterministic flow.

### Which file should I open first after execution?

Open `artifacts/canonical_run/index.html` first. Treat it as the permanent primary interface for human review, then follow the ordered inspection list above.

### I only want the raw proof bundle without setup. What should I run?

Run `bnsyn run --profile canonical --plot --export-proof`. That is the canonical proof contract and the direct CLI path.

### How do I confirm the generated bundle is valid?

Run:

```bash
bnsyn validate-bundle artifacts/canonical_run
```

### Where is repository status tracked?

See [docs/STATUS.md](docs/STATUS.md).

## Canonical links

- Proof contract reference: [docs/CANONICAL_PROOF.md](docs/CANONICAL_PROOF.md)
- Emergence interpretation atlas: [docs/EMERGENT_ORCHESTRATION_ATLAS.md](docs/EMERGENT_ORCHESTRATION_ATLAS.md)
- Validation gap remediation playbook: [docs/VALIDATION_GAP_REMEDIATION.md](docs/VALIDATION_GAP_REMEDIATION.md)
- Demo review and merge-readiness priorities: [docs/DEMO_REVIEW.md](docs/DEMO_REVIEW.md)
- Reproduce proof details: [docs/proof/REPRODUCE.md](docs/proof/REPRODUCE.md)
- System architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Project status and boundaries: [docs/STATUS.md](docs/STATUS.md)
- Redirect surfaces: [docs/START_HERE.md](docs/START_HERE.md), [docs/QUICKSTART.md](docs/QUICKSTART.md), [docs/LEGENDARY_QUICKSTART.md](docs/LEGENDARY_QUICKSTART.md)
