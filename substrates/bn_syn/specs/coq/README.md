# Coq Formal Proofs for BNsyn

This directory contains Coq proof obligations and formal proofs for the BNsyn thermostated bio-AI system.

## Status

**📄 SPECIFICATION ONLY — no `.v` source files present in this directory at HEAD.**

This directory currently contains this README documenting intended proof obligations.
The `BNsyn_Sigma.v` source file referenced below is **not** present in the repository
at the current commit; treat the "Theorems" / "How Tested" sections as a specification
of what the proof would assert, not as a record of an existing proof artifact.

The scheduled `.github/workflows/formal-coq.yml` workflow (cron, not PR-gating) targets
this directory; with no `.v` files, it cannot execute a real proof check.

## Code Mapping

| Coq Definition | Code Location | Value |
|----------------|---------------|-------|
| `gain_min` | `src/bnsyn/config.py:CriticalityParams.gain_min` | 0.2 |
| `gain_max` | `src/bnsyn/config.py:CriticalityParams.gain_max` | 5.0 |
| `clamp` function | Generic clamping pattern used in criticality control | N/A |

## Implemented Proofs

### BNsyn_Sigma.v - Criticality Gain Bounds Preservation (specification)

**Status**: 📄 Specification only. The `BNsyn_Sigma.v` file is not present at HEAD.
The theorem statements below describe the intended proof contract; no formally
verified Coq artifact backs them in the repository at the current commit.

**Code Contract**: `src/bnsyn/config.py:CriticalityParams` with `gain_min=0.2, gain_max=5.0`

**Theorems**:
1. `clamp_preserves_bounds`: General clamp function preserves min/max bounds for any values
2. `gain_clamp_preserves_bounds`: Gain clamping preserves [0.2, 5.0] bounds (actual code values)
3. `gain_update_bounded`: Any gain update using clamp stays in bounds
4. `clamp_idempotent`: Clamp operation is idempotent (clamp(clamp(x)) = clamp(x))

**How Tested**:
- Coq compilation in CI: `.github/workflows/formal-coq.yml`
- Property tests validate gain bounds: `tests/properties/` and `tests/validation/test_criticality_validation.py`

**Compiling locally**:
```bash
cd specs/coq
coqc BNsyn_Sigma.v
```

**CI Integration**: `.github/workflows/formal-coq.yml` runs on schedule with pinned Coq toolchain

## Purpose

While TLA+ model checking explores a finite state space to find invariant violations, Coq provides:
- **Theorem proving**: Mechanically verified proofs that hold for all possible inputs
- **Functional correctness**: Prove that implementations match specifications
- **Mathematical rigor**: Establish properties through constructive proofs

## Proof Obligations (Future Work)

The following properties should be formally proven in Coq:

### PO-1: Temperature Schedule Correctness

**Theorem**: The geometric temperature schedule converges to Tmin and is monotonically decreasing.

```coq
Theorem temperature_convergence :
  forall (T0 Tmin alpha : R) (n : nat),
    0 < Tmin < T0 ->
    0 < alpha < 1 ->
    exists (N : nat),
      forall (m : nat), m >= N ->
        abs (temperature_at_step T0 alpha m - Tmin) < epsilon.
```

```coq
Theorem temperature_monotone :
  forall (T0 Tmin alpha : R) (n : nat),
    0 < Tmin < T0 ->
    0 < alpha <= 1 ->
    temperature_at_step T0 alpha n > Tmin ->
    temperature_at_step T0 alpha (S n) <= temperature_at_step T0 alpha n.
```

**Code mapping**: `src/bnsyn/temperature/schedule.py:TemperatureSchedule.step()`

### PO-2: Plasticity Gate Bounds

**Theorem**: The plasticity gate function always produces values in [0, 1].

```coq
Theorem gate_sigmoid_bounds :
  forall (T Tc tau : R),
    tau > 0 ->
    0 <= gate_sigmoid T Tc tau <= 1.
```

**Code mapping**: `src/bnsyn/temperature/schedule.py:gate_sigmoid()`

### PO-3: Determinism

**Theorem**: Given the same initial state and random seed, the system produces identical outputs.

```coq
Theorem simulation_deterministic :
  forall (state1 state2 : SystemState) (seed : nat) (steps : nat),
    state1 = state2 ->
    run_simulation state1 seed steps = run_simulation state2 seed steps.
```

**Code mapping**: Core simulation loop, tested extensively in `tests/test_determinism.py`

## Implementation Roadmap

### Phase 1: Setup ✅
- [x] Define Coq environment and dependencies
- [x] Create base type definitions (clamp function)
- [x] Prove gain bounds preservation (aligned with actual code)

### Phase 2: Core Proofs (PLANNED)
- [ ] Prove PO-1 (Temperature schedule correctness) - map to `TemperatureParams`
- [ ] Prove PO-2 (Gate bounds) - map to `gate_sigmoid`
- [ ] Update constants to match code exactly

### Phase 3: System Properties (PLANNED)
- [ ] Prove PO-3 (Determinism)
- [ ] Link proofs to validation test results

## Development Environment

### Using Pinned Container (Recommended for CI)

The CI workflow uses a pinned Coq container to ensure reproducibility:

```yaml
container:
  image: coqorg/coq:8.15-ocaml-4.14-flambda@sha256:<digest>
```

### Installing Coq Locally

```bash
# Using opam (OCaml package manager)
opam install coq coq-ide

# Or using system package manager
sudo apt-get install coq coqide  # Debian/Ubuntu
brew install coq                  # macOS
```

### Recommended Coq Version

- Coq 8.15 or later (CI uses 8.15 with pinned container)
- CoqIDE or Proof General for interactive development

### Required Libraries

```bash
opam install coq-mathcomp-ssreflect
opam install coq-mathcomp-algebra
opam install coq-coquelicot  # Real analysis
```

## Resources

### Coq Documentation
- **Official Coq Manual**: https://coq.inria.fr/refman/
- **Software Foundations**: https://softwarefoundations.cis.upenn.edu/
- **Programs and Proofs**: https://ilyasergey.net/pnp/

### Relevant Coq Projects
- **CompCert**: Verified C compiler
- **Flocq**: Floating-point arithmetic formalization
- **Coquelicot**: Real analysis library

### BNsyn Context
- See `docs/SPEC.md` for system specification
- See `specs/tla/BNsyn.tla` for TLA+ model
- See `src/bnsyn/` for Python reference implementation

## Contributing

When implementing proofs:

1. Start with the simplest properties (bounds preservation)
2. **Always align constants with actual code** - check `src/bnsyn/config.py`
3. Use Coq's standard library and mathcomp when possible
4. Document code mapping in proof comments
5. Update this README with mappings

## Claims and Verification Status

**Current Status**:
- 📄 No `.v` source files present in this directory; nothing is currently proven in Coq.
- ⚠️ All theorems documented here (gain bounds, temperature, gates, phase transitions, numerical stability) are **proof obligations only**.

**What is Verified**: nothing in Coq at this commit. Property tests in
`tests/properties/` and `tests/validation/test_criticality_validation.py` exercise
the same invariants at the Python level.

**What is NOT Verified**: any property listed in this README, in the Coq sense.

## Integration with CI/CD

The `.github/workflows/formal-coq.yml` workflow:
- Uses pinned Coq container for reproducibility
- Compiles all `.v` files
- Fails on compilation errors
- Uploads compilation logs as artifacts

## Future Work

- Formalize the complete AdEx neuron dynamics with actual parameters
- Prove temperature schedule convergence with `TemperatureParams` values
- Establish gate bounds theorem for `gate_sigmoid` function
- Verify error bounds for numerical integration schemes
- Link all proofs to specific code locations
