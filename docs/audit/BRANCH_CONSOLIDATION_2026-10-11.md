# Branch consolidation ledger — 2026-10-11

claim_status: measured

## What was wrong

`github.com/neuron7x/neosynaptex` `main` stood at `181353a7` (PR #163, 2026-04-30).
The actual canonical line (GitLab `neuron7x-group/neosynaptex` `main` = `d34a6ce1`,
PR #258, plus local `0e476f00`) was 62 commits ahead and a strict descendant, so the
GitHub repo was a stale snapshot with 84 side branches. Four draft PRs opened on
2026-10-11 were all measured against that stale base.

## Method

Containment is judged by content, not by ancestry or patch-id:

1. `MERGED` — tip is an ancestor of the integration head.
2. `ABSORBED` — `git merge-tree --write-tree HEAD <tip>` equals `HEAD^{tree}`.
3. `SUPERSEDED` — for every file changed on the branch (merge-base..tip), the tip blob
   equals the head blob or exists among the objects reachable from head.
4. Anything else was read by hand; the reason is in the table.

Known limit of (3): a blob that exists in head history under a different path
(e.g. an empty file) counts as contained.

## Verification

Environment: Python 3.12.3, local `.venv`, `pytest -m "not slow" -n 8`. GitHub Actions
did not execute (jobs fail before runner allocation — account billing block), so
there is **no CI evidence** for this consolidation; the numbers below are local.

| subject | passed | failed | skipped |
|---|---|---|---|
| canon `0e476f00` before | 2340 | 1 | 27 |
| integration head | 2430 | 0 | 14 |

Not run: tests marked `slow`; network lanes (`NEOSYNAPTEX_RUN_NETWORK_TESTS`);
mypy; ruff; `make all`; anything under `substrates/*/tests`.

## Defects found in canon and fixed here

- `contracts/truth_criterion.py` imported `bn_syn.transfer_entropy`, a module removed
  from the tree: `evaluate_truth_criterion` raised `ModuleNotFoundError` on every
  call. The covering tests were `skipif`-guarded on the same dead name, so the suite
  stayed green. The fix had existed since 2026-04-06 only in two stash-archive branches.
- `tests/audit/test_audit_telemetry.py` failed whenever the last 30 days had no
  commits (it rejected the tool's own `no_signal` verdict).
- `tests/test_m_invariant_scale_diagnostics.py` rewrote tracked evidence
  `results/m_invariant_scale_diagnostics/run_v1.json` on every run. It now runs in a
  sandbox and additionally asserts the fresh run reproduces the committed evidence.

## Merged in this consolidation

- `method-gate-0-mycelium` (`8b46ced0`) — merge commit, clean.
- gamma-program chain to `feat/gamma-program-sampen-null-suite` (`38b18661`, 13 commits)
  — merge commit; 74 add/add conflicts resolved to the branch side after checking the
  main side was byte-identical to ancestor `853959e3`. Negative results kept as recorded.
- README truth-pass, 7 commits from `feat/phase-4-substrate-resolution` (cherry-pick -x).
- `fix/legacy-topology-canon-2026-10-11`, 2 commits (cherry-pick -x).

## Open debt

- Adapter v2 for `serotonergic_kuramoto` (Phase 4c/4d) — unmerged, see table.
- Neurophase RUN1 pipeline — unmerged, see table.
- 7 `TestCoherenceBridge` tests in `tests/test_protocol_v2.py` still skip
  (`tradepulse.coherence_bridge` has no in-tree target).
- 34 references in 22 files still point at `neuron7xLab/neosynaptex`; several are
  frozen records (prereg, validation logs), so they were not bulk-rewritten.
- No branch protection on `main`; no executing CI.
- No remote branch was deleted. Every tip SHA is in the table below.

## Disposition of all 84 branches

| disposition | count |
|---|---|
| MERGED | 13 |
| ABSORBED | 25 |
| SUPERSEDED | 38 |
| PORTED | 2 |
| PARTIAL / OPEN | 1 |
| OPEN | 2 |
| REJECTED | 1 |
| NOT MERGED | 1 |
| OWNER DECISION | 1 |

| branch | tip | disposition | basis |
|---|---|---|---|
| `feat/gamma-program-analysis-contract` | `0be384aff` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-canonical-stack` | `20f24fe2b` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-claim-gate` | `7ed377b61` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-cohort-expansion` | `c43c9813f` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-evidence-branches` | `baba35078` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-external-validation` | `bf34d709f` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-hrv-baseline` | `a4cbe1f12` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-null-suite-v2` | `853959e30` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-outlier-protocol` | `8ff03f26c` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-sampen-null-suite` | `38b18661d` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-state-contrast` | `07c027661` | MERGED | tip is an ancestor of the integration head. |
| `feat/gamma-program-toolchain-freeze` | `f15ad6134` | MERGED | tip is an ancestor of the integration head. |
| `method-gate-0-mycelium` | `8b46ced0e` | MERGED | tip is an ancestor of the integration head. |
| `archive/local-stash-3-On-integrate-bnsyn-local-structural-evidence--tmp-` | `0e2b88d4c` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `ci/canonical-admissibility-split-slow` | `d6a5cf049` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `ci/hrv-real-data-scheduled` | `63397c29c` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `docs/branch-protection-contract` | `a5b98bd96` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `docs/bridge-step2-n3-reconcile` | `18c3315ff` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `docs/lobster-acquisition-plan` | `5dbab01ca` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `docs/session-close-2026-04-14` | `5d3fd8999` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/expelliarmus` | `8146d3b85` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/gamma-program-run-reporting` | `379e16658` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/git-sha-consolidation` | `f1e6797f4` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/intelligence-certificate` | `6630c0962` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/m-invariant-mfn-bnsyn-bridge` | `400604c13` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/m2-1-status-freeze` | `54dd259be` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/m2-3-bnsyn-spatial-embedding` | `25cf94e3c` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/m2-4-scale-invariant-operators` | `84fa03190` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/m2-5-pre-registration` | `552ba8419` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/telemetry-emission-api` | `4f2545b81` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `feat/telemetry-trace-query` | `da3a1b03d` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `fix/hrv-test-first-principles` | `2a38f4594` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `fix/legacy-topology-canon-2026-10-11` | `d28a24997` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `integrate-bnsyn-local-structural-evidence` | `bf7091eb6` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `pr149-head` | `bf7091eb6` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `sec/codeql-followup-hmac-revert` | `595ab47e4` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `ship/external-replication-scaffold` | `a0a6772ce` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `sincerity/pass-1-downgrade-overclaims` | `369d1dadc` | ABSORBED | merging the tip into the integration head changes nothing (merge-tree result == head tree). |
| `archive-probe-dialogue-null` | `f286ea323` | SUPERSEDED | main carries the merged revision (#146) of the same three files. |
| `archive/desktop-stash-1-fred-indpro-replication` | `cfa9b9afc` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `archive/local-stash-1-WIP-on-main--15daf317-feat-audit---Phase-1-—-Cla` | `c75236412` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `archive/local-stash-2-WIP-on-main--15daf317-feat-audit---Phase-1-—-Cla` | `ea4ba596e` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `docs/cns-ai-archive-location-stub` | `2f74afb6f` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/adversarial-auditor-orchestrator` | `d2ef98782` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/architecture-aesthetics` | `857a9e057` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/architecture-hardening` | `724abfe0a` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/audit-tools-emit-telemetry` | `28e4f2e70` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/canon-drift-detector` | `989bd550d` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/canon-reference-check` | `93193f013` | SUPERSEDED | all 5 added lines present in docs/protocols/telemetry_spine_spec.md. |
| `feat/clean-ledger` | `b2ef9938b` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/evidence-hardening` | `c5eba5384` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/external-replication-index` | `9bf4389b8` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/gamma-ledger-integrity` | `b9d7a92d8` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/gamma-program-foundation` | `8aa7b08ce` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/inv-yv1-gradient-ontology` | `e6b4bc1c3` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/kill-signal-coverage-ratchet` | `d66ac6185` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/m2-2-scale-diagnostics` | `5e3cbdf75` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/mathematical-precision` | `8989a0ca7` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/measurement-contract-verifier` | `61b4e36e1` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/metadata-sync` | `1c3256286` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/perfection-pass` | `c6251f4d0` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/phase-3-null-screen` | `7bea0fec9` | SUPERSEDED | earlier draft of PR #161; main carries the later revision (+40/-2 on the same two files). |
| `feat/physionet-nsr2db-hrv` | `fc959cd05` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/task-1-2-coherence-state-space-fdt-gamma` | `0ca60bc75` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/tasks-3-4-5-6-oeb-benchmark-resonance-ablation` | `6c63ccb46` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/telemetry-adoption-bridge-levin-runner` | `cc4f536a0` | SUPERSEDED | all 50 added test lines present in tests/levin_bridge/test_levin_runner.py. |
| `feat/telemetry-adoption-manifest` | `47dcba19b` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `feat/unfalsifiable-fortress` | `55e484ad2` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `fix/hrv-test-flake-margin` | `ab8b7a7aa` | SUPERSEDED | main replaced the test with the first-principles version (network lane opt-in). |
| `fix/readme-claim-boundary-2026-10-11` | `44686167d` | SUPERSEDED | README was rewritten by the 2026-05-04 truth-pass (cherry-picked here); none of the phrases this branch downgrades survive in README.md. |
| `fix/security-pip-bump` | `b381e7d32` | SUPERSEDED | the pip>=26.1 step is in .github/workflows/security.yml. |
| `recovery/m2-invariant-consolidation` | `556c55b7e` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `sec/dependabot-pyo3-postcss` | `247221da5` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `security/codeql-debt-resolution` | `58f122fda` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `sincerity/pass-2-non-canon-overclaims` | `b1a4543a7` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `sincerity/pass-3-substrate-independent-downgrade` | `0f07e33df` | SUPERSEDED | every file the branch changed is either identical in head or its blob exists in head's history (merged, then evolved). |
| `archive/desktop-stash-2-clean-ledger-pre-session` | `0ecb8f6d0` | PORTED | its bn_syn import fix was the only live content; ported by hand (see Defects). |
| `archive/desktop-stash-3-immaculate-report` | `c9e44881e` | PORTED | same fix as stash-2. |
| `feat/phase-4-substrate-resolution` | `6202d64dd` | PARTIAL / OPEN | 7 README truth-pass + audit commits cherry-picked. NOT merged: serotonergic_kuramoto adapter v2 (_N_SWEEP=128, geomspace) + its test + protocol doc. It changes the adapter hash bound in evidence/gamma_ledger.json; the branch's own readiness report records the runtime refusing to load. Canon route is Phase 4a→4d; γ must be re-derived and the ledger updated in a reviewed PR. |
| `archive/local-stash-0-On-feat-phase-4-substrate-resolution--phase4-wip-s` | `cf8d7aa99` | OPEN | WIP snapshot of the same adapter-v2 work; same blocker. |
| `feat/neurophase-run1-pipeline` | `99a4a6705` | OPEN | NOT merged. (1) neurophase/results/RUN1_VERDICT.yaml is `verdict_locked: true`, H1 REJECTED, EEG_TRACK_CLOSED — produced from a 4-subject synthetic fixture (/tmp/synth_ds, operator=selftest, AUTO_CONFIRM) against a contract of n=122; it is a selftest output carrying a real-run label. (2) pipeline has no tests and needs mne/eeglabio, absent from the environment: not executed here. (3) results/full_cohort_null: 40 files, summary says n=69, nothing references it. Needed before merge: selftest output root separate from the canonical results path, gate_m3 refusing to lock on synthetic input, tests. |
| `docs/sync-test-counts-20260420` | `f07f28426` | REJECTED | adds evidence/semantic_drift_registry.json entry `gamma-universal-v1` with status=validated, generalization_authorized=true — contradicts canon commit 113caaa1 (claim surface C-001..C-004 closed). README counts are stale. |
| `audit/branch-recovery-2026-10-11` | `2e9973913` | NOT MERGED | ledger measured against stale base 181353a7 (62 commits behind canon); replaced by this document. |
| `archive/desktop-stash-0-drift-rescue-2026-05-01` | `af810b7a3` | OWNER DECISION | replaces author name/location with a role line in banners, README, manuscript. Identity/branding choice, not a correctness change. |
