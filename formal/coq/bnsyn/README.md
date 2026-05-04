# Coq formal proofs for BN-Syn

## What is here

Skeleton Coq specifications targeted at BN-Syn (the spiking-neural
substrate under `substrates/bn_syn/`). The current scope is narrow.

## Verified scope (current commit)

`BNsyn_Sigma.v` proves:

- `clamp_preserves_bounds` — generic clamp preserves `[lo, hi]`.
- `gain_clamp_preserves_bounds` — clamping with `[0.2, 5.0]`
  matches the Python constants in `src/bnsyn/config.py:CriticalityParams`.
- `gain_update_bounded` — repeated clamped updates stay in bounds.
- `clamp_idempotent` — `clamp(clamp(x)) = clamp(x)`.

That is the entire current proof obligation set that has been
discharged. Temperature schedule, gate-sigmoid bounds, determinism,
and AdEx neuron dynamics are listed in this file as **proof
obligations only** (`PO-1`, `PO-2`, `PO-3`); they are **not** proven.

## Contents

- `BNsyn_Sigma.v` — gain-bounds proofs (the verified scope above).
- This README — narrative scope, code mapping, and the unverified
  proof-obligation list retained for future work.

## Requirements

- Coq 8.15 or later. Local install via `opam install coq` or system
  package; CI runs against a pinned `coqorg/coq` container (see
  `.github/workflows/formal-coq.yml` in the BN-Syn upstream tree).

## Usage

```bash
coqc BNsyn_Sigma.v
```

## Tests

Compilation under CI is the only check; there is no separate test
runner.

## Output

A successful `coqc` produces `.vo` artefacts. No claim, evidence row,
or γ-program verdict depends on these artefacts at this commit.

## Notes

- "Formal verification" in this directory means **only** the gain
  clamp bounds. Phase, temperature, and gate dynamics are not proven.
- The proof-obligation skeletons in this file (`PO-1`, `PO-2`,
  `PO-3`) are roadmap items, not theorems.
