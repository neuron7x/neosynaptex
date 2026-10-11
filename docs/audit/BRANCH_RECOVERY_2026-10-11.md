# NeoSynaptex — 81-branch recovery ledger

**Audit snapshot:** 2026-10-11 · repo `neuron7x/neosynaptex` · `main` SHA `181353a73ab6c24deeb4d1ec6137683ae33d038c`.
**Initial 81-branch Git comparison:** 1 base, 14 ahead with zero behind, 66 diverged. Every non-main ref was checked with GitHub compare endpoint. Snapshot inventory below excludes the audit branch created to host this file.
**Review status:** Triage recorded, **NOT** release approval. Git graph comparison does not establish patch equivalence or run tests.

## Prohibitions and acceptance criteria
1. Do not mass-merge legacy, scientific, archive, or WIP branches. No deletion/force-push before verifying recoverable references and unique artifacts.
2. For each candidate: freeze SHAs, read changes relative to merge-base, compare content against current main, check sibling overlap, and execute test/CI + relevant security/scientific validation.
3. Enforce claim-boundary: `CANONICAL_POSITION.md`, `docs/CLAIM_BOUNDARY.md`; no silent reintroduction of `topo/thermo_cost` as a canonical Kuramoto γ-claim after Phase 4b.
4. No observed CI runs or commit status checks via current GitHub API queries; CI configured is not CI verified.

## Proven conflicts and priority issues
- **Scientific:** `README.md` presents strong criticality/thermodynamic assertions while `CANONICAL_POSITION.md` and `docs/CLAIM_BOUNDARY.md` classify cross-substrate universality as conjectural; `REPO_TOPOLOGY.md` labels older entries VALIDATED. Public claims need reconciliation before new measurements.
- **Scientific measurement:** `docs/audit/PHASE_4B_CANONICAL_KURAMOTO_OBSERVABLES.md` states legacy `topo`/`thermo_cost` γ pathway produced estimator/sweep-sensitive results (~1.0677, 0.7403, 0.0661). Canonical observables and coordinates are different; old γ must not be resurrected.
- **Duplicate Git identity:** `pr149-head` and `integrate-bnsyn-local-structural-evidence` share tip SHA `bf7091eb6d9e5647895c5578b4ee743c07af931c`.
- **Sibling collision:** `feat/m2-1-*` through `feat/m2-5-*` are diverged siblings, not fast-forward sequence. They may contain different one-commit scientific deltas atop common foundations.
- **Metadata:** `pyproject.toml` project URL and README asset paths mention `neuron7xLab/neosynaptex`, not `neuron7x/neosynaptex`. Audit links and publication provenance.
- **Security:** ahead branches contain older CodeQL fixes and PyO3/PostCSS dependency updates; review on current toolchains and advisory state before merge.

## Complete branch-by-branch disposition (81/81)
| # | Branch | Tip SHA | Compared with main | Next action |
|---:|---|---|---|---|
| 1 | `archive/desktop-stash-0-drift-rescue-2026-05-01` | `af810b7a39e9` | DIVERGED | PRESERVE stash; no direct merge |
| 2 | `archive/desktop-stash-1-fred-indpro-replication` | `cfa9b9afc443` | DIVERGED | PRESERVE stash; no direct merge |
| 3 | `archive/desktop-stash-2-clean-ledger-pre-session` | `0ecb8f6d0b76` | DIVERGED | PRESERVE stash; no direct merge |
| 4 | `archive/desktop-stash-3-immaculate-report` | `c9e44881e6f9` | DIVERGED | PRESERVE stash; no direct merge |
| 5 | `archive/local-stash-0-On-feat-phase-4-substrate-resolution--phase4-wip-s` | `cf8d7aa99ccf` | DIVERGED | PRESERVE stash; no direct merge |
| 6 | `archive/local-stash-1-WIP-on-main--15daf317-feat-audit---Phase-1-—-Cla` | `c7523641207b` | DIVERGED | PRESERVE stash; no direct merge |
| 7 | `archive/local-stash-2-WIP-on-main--15daf317-feat-audit---Phase-1-—-Cla` | `ea4ba596ef4e` | DIVERGED | PRESERVE stash; no direct merge |
| 8 | `archive/local-stash-3-On-integrate-bnsyn-local-structural-evidence--tmp-` | `0e2b88d4cf4f` | DIVERGED | PRESERVE stash; no direct merge |
| 9 | `archive-probe-dialogue-null` | `f286ea323d41` | DIVERGED | PRESERVE null evidence |
| 10 | `ci/canonical-admissibility-split-slow` | `d6a5cf049fb9` | AHEAD (+)/0 behind | P1 CI workload and gate evaluation |
| 11 | `ci/hrv-real-data-scheduled` | `63397c29c12a` | AHEAD (+)/0 behind | P1 CI workload and gate evaluation |
| 12 | `docs/branch-protection-contract` | `a5b98bd96a5d` | DIVERGED | P2 DOC version/claim consistency |
| 13 | `docs/bridge-step2-n3-reconcile` | `18c3315ffcc7` | DIVERGED | P2 DOC version/claim consistency |
| 14 | `docs/cns-ai-archive-location-stub` | `2f74afb6f48b` | DIVERGED | P2 DOC version/claim consistency |
| 15 | `docs/lobster-acquisition-plan` | `5dbab01ca5d4` | DIVERGED | P2 DOC version/claim consistency |
| 16 | `docs/session-close-2026-04-14` | `5d3fd899980b` | DIVERGED | P2 DOC version/claim consistency |
| 17 | `docs/sync-test-counts-20260420` | `f07f284269df` | DIVERGED | P2 DOC version/claim consistency |
| 18 | `feat/adversarial-auditor-orchestrator` | `d2ef9878246f` | DIVERGED | P2 GOVERNANCE selective parity/test |
| 19 | `feat/architecture-aesthetics` | `857a9e0570a8` | DIVERGED | P2 ENGINEERING selective parity/test |
| 20 | `feat/architecture-hardening` | `724abfe0a39a` | DIVERGED | P2 ENGINEERING selective parity/test |
| 21 | `feat/audit-tools-emit-telemetry` | `28e4f2e70b7e` | DIVERGED | P2 GOVERNANCE selective parity/test |
| 22 | `feat/canon-drift-detector` | `989bd550dd45` | DIVERGED | P2 ENGINEERING selective parity/test |
| 23 | `feat/canon-reference-check` | `93193f013864` | DIVERGED | P2 ENGINEERING selective parity/test |
| 24 | `feat/clean-ledger` | `b2ef9938b662` | DIVERGED | P2 ENGINEERING selective parity/test |
| 25 | `feat/evidence-hardening` | `c5eba5384eb3` | DIVERGED | P2 ENGINEERING selective parity/test |
| 26 | `feat/expelliarmus` | `8146d3b85323` | DIVERGED | P2 ENGINEERING selective parity/test |
| 27 | `feat/external-replication-index` | `9bf4389b8227` | DIVERGED | P1 REPLICATION reproducibility review |
| 28 | `feat/gamma-ledger-integrity` | `b9d7a92d87e8` | DIVERGED | P2 ENGINEERING selective parity/test |
| 29 | `feat/gamma-program-analysis-contract` | `0be384affcda` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 30 | `feat/gamma-program-canonical-stack` | `20f24fe2be90` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 31 | `feat/gamma-program-claim-gate` | `7ed377b6193d` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 32 | `feat/gamma-program-cohort-expansion` | `c43c9813f66a` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 33 | `feat/gamma-program-evidence-branches` | `baba35078383` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 34 | `feat/gamma-program-external-validation` | `bf34d709f25c` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 35 | `feat/gamma-program-foundation` | `8aa7b08cecba` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 36 | `feat/gamma-program-hrv-baseline` | `a4cbe1f12cc3` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 37 | `feat/gamma-program-null-suite-v2` | `853959e3048c` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 38 | `feat/gamma-program-outlier-protocol` | `8ff03f26cca7` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 39 | `feat/gamma-program-run-reporting` | `379e16658a83` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 40 | `feat/gamma-program-sampen-null-suite` | `38b18661d158` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 41 | `feat/gamma-program-state-contrast` | `07c0276618a4` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 42 | `feat/gamma-program-toolchain-freeze` | `f15ad6134810` | DIVERGED | P1 SCIENCE gamma family provenance/nulls |
| 43 | `feat/git-sha-consolidation` | `f1e6797f4426` | DIVERGED | P2 ENGINEERING selective parity/test |
| 44 | `feat/intelligence-certificate` | `6630c0962c9e` | DIVERGED | P2 ENGINEERING selective parity/test |
| 45 | `feat/inv-yv1-gradient-ontology` | `e6b4bc1c334a` | DIVERGED | P2 ENGINEERING selective parity/test |
| 46 | `feat/kill-signal-coverage-ratchet` | `d66ac618525b` | DIVERGED | P2 ENGINEERING selective parity/test |
| 47 | `feat/m2-1-status-freeze` | `54dd259bee32` | AHEAD (+)/0 behind | P1 M2 sibling divergence; extract unique artifacts |
| 48 | `feat/m2-2-scale-diagnostics` | `5e3cbdf755aa` | AHEAD (+)/0 behind | P1 M2 sibling divergence; extract unique artifacts |
| 49 | `feat/m2-3-bnsyn-spatial-embedding` | `25cf94e3c977` | AHEAD (+)/0 behind | P1 M2 sibling divergence; extract unique artifacts |
| 50 | `feat/m2-4-scale-invariant-operators` | `84fa031900bf` | AHEAD (+)/0 behind | P1 M2 sibling divergence; extract unique artifacts |
| 51 | `feat/m2-5-pre-registration` | `552ba8419a5c` | AHEAD (+)/0 behind | P1 M2 sibling divergence; extract unique artifacts |
| 52 | `feat/m-invariant-mfn-bnsyn-bridge` | `400604c13832` | AHEAD (+)/0 behind | P1 M2 sibling divergence; extract unique artifacts |
| 53 | `feat/mathematical-precision` | `8989a0ca7702` | DIVERGED | P2 ENGINEERING selective parity/test |
| 54 | `feat/measurement-contract-verifier` | `61b4e36e1815` | DIVERGED | P2 GOVERNANCE selective parity/test |
| 55 | `feat/metadata-sync` | `1c3256286ba3` | DIVERGED | P2 ENGINEERING selective parity/test |
| 56 | `feat/neurophase-run1-pipeline` | `99a4a6705a7f` | AHEAD (+)/0 behind | P1 EEG replication and null audit |
| 57 | `feat/perfection-pass` | `c6251f4d0849` | DIVERGED | P2 ENGINEERING selective parity/test |
| 58 | `feat/phase-3-null-screen` | `7bea0fec9e26` | DIVERGED | P1 SCIENCE reconcile Phase 4b |
| 59 | `feat/phase-4-substrate-resolution` | `6202d64dd44e` | DIVERGED | P1 SCIENCE reconcile Phase 4b |
| 60 | `feat/physionet-nsr2db-hrv` | `fc959cd05c7d` | DIVERGED | P1 REPLICATION reproducibility review |
| 61 | `feat/task-1-2-coherence-state-space-fdt-gamma` | `0ca60bc752d3` | DIVERGED | P2 ENGINEERING selective parity/test |
| 62 | `feat/tasks-3-4-5-6-oeb-benchmark-resonance-ablation` | `6c63ccb469ae` | DIVERGED | P2 ENGINEERING selective parity/test |
| 63 | `feat/telemetry-adoption-bridge-levin-runner` | `cc4f536a0555` | DIVERGED | P2 GOVERNANCE selective parity/test |
| 64 | `feat/telemetry-adoption-manifest` | `47dcba19b044` | DIVERGED | P2 GOVERNANCE selective parity/test |
| 65 | `feat/telemetry-emission-api` | `4f2545b8136d` | DIVERGED | P2 GOVERNANCE selective parity/test |
| 66 | `feat/telemetry-trace-query` | `da3a1b03d56a` | DIVERGED | P2 GOVERNANCE selective parity/test |
| 67 | `feat/unfalsifiable-fortress` | `55e484ad24e0` | DIVERGED | P2 ENGINEERING selective parity/test |
| 68 | `fix/hrv-test-first-principles` | `2a38f4594085` | AHEAD (+)/0 behind | P1 TEST choose one validated fix |
| 69 | `fix/hrv-test-flake-margin` | `ab8b7a7aa2aa` | AHEAD (+)/0 behind | P1 TEST choose one validated fix |
| 70 | `fix/security-pip-bump` | `b381e7d32ce7` | DIVERGED | P0 SECURITY patch/test/advisory check |
| 71 | `integrate-bnsyn-local-structural-evidence` | `bf7091eb6d9e` | DIVERGED | AUDIT BN-Syn evidence; paired identical ref |
| 72 | `main` | `181353a73ab6` | BASE | BASELINE: freeze for review |
| 73 | `method-gate-0-mycelium` | `8b46ced0e4b0` | DIVERGED | P1 SCIENCE methodology review |
| 74 | `pr149-head` | `bf7091eb6d9e` | DIVERGED | DUPLICATE tip; review delete candidate |
| 75 | `sec/codeql-followup-hmac-revert` | `595ab47e4e9f` | AHEAD (+)/0 behind | P0 SECURITY patch/test/advisory check |
| 76 | `sec/dependabot-pyo3-postcss` | `247221da5a83` | AHEAD (+)/0 behind | P0 SECURITY patch/test/advisory check |
| 77 | `security/codeql-debt-resolution` | `58f122fda311` | AHEAD (+)/0 behind | P0 SECURITY patch/test/advisory check |
| 78 | `ship/external-replication-scaffold` | `a0a6772cecb4` | DIVERGED | P1 REPLICATION reproducibility review |
| 79 | `sincerity/pass-1-downgrade-overclaims` | `369d1dadcbd5` | DIVERGED | P0 CLAIM repair; selective port |
| 80 | `sincerity/pass-2-non-canon-overclaims` | `b1a4543a7b15` | DIVERGED | P0 CLAIM repair; selective port |
| 81 | `sincerity/pass-3-substrate-independent-downgrade` | `0f07e33dfb28` | DIVERGED | P0 CLAIM repair; selective port |

## Priority execution sequence
**P0a** Resolve published claim contradiction and immutable baseline/checks; **P0b** validate security fix family and dependencies.
**P1a** Validate isolated CI change; **P1b** reconstruct M-invariant and M2 sibling data; **P1c** inspect Neurophase EEG raw-data provenance and negative controls; **P1d** reconcile γ-family and Phase 3/4 null suites.
**P2** Merge nothing until technical equivalence and tests; port independent telemetry/governance/docs fixes one by one.
**P3** Retain recovery archives and scientific counterexamples. Identify exact-duplicate branch refs for *later* deletion review only.

## Interpretation
`AHEAD (+)/0 behind`: graph fast-forward possible in principle, but change may be stale, unsafe, semantically duplicative or untested.
`DIVERGED`: branch has commits absent in main's ancestry and main has later commits; do **not** infer its code/evidence are missing from main.
**Default disposition for every untested candidate: HOLD.** No PR passes merge-gate from this inventory alone.