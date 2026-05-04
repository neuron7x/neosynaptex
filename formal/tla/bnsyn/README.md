# TLA+ specification for BN-Syn

## What is here

A TLA+ model of the BN-Syn temperature-gated plasticity loop. The model
is intentionally a bounded abstraction of the full Python implementation
under `substrates/bn_syn/src/bnsyn/`.

## Contents

- `BNsyn.tla` — TLA+ specification (state, actions, invariants,
  temporal properties).
- `BNsyn.cfg` — TLC configuration with constants matching the Python
  side (`T0=1.0`, `Tmin=0.001`, `Alpha=0.95`, `Tc=0.1`,
  `GateTau=0.02`, `GainMin=0.2`, `GainMax=5.0`, `MaxSteps=100`).
- This README — code-to-spec mapping and scope notes.

## Verified invariants and properties

State invariants (model-checked under TLC for the configured bound):

- `INV-1 GainClamp` — `gain ∈ [GainMin, GainMax]`.
- `INV-2 TemperatureBounds` — `temperature ∈ [Tmin, T0]`.
- `INV-3 GateBounds` — `gate ∈ [0, 1]`.
- `INV-4 PhaseValid` — phase ∈ `{active, consolidating, cooled}`.

Temporal properties:

- `PROP-1 TemperatureMonotone`.
- `PROP-2 EventuallyCooled`.
- `PROP-3 GateCorrelation`.

## Requirements

- TLA+ tools (`tla2tools.jar`); CI uses a pinned release with SHA-256
  verification (see the upstream BN-Syn workflow
  `.github/workflows/formal-tla.yml`).
- Java for `tlc2.TLC`.

## Usage

```bash
java -cp tla2tools.jar tlc2.TLC -config BNsyn.cfg BNsyn.tla
```

## Tests

The model checker run is the sole check.

## Output

`tlc2.TLC` produces a model-checking report. No γ-program evidence
row depends on this artefact at this commit.

## Notes

- The model checks a **bounded** state space (`MaxSteps = 100`); it
  is not a proof for arbitrary-length runs.
- The gate sigmoid is approximated; numerical-precision phenomena in
  the Python implementation are not modelled here.
