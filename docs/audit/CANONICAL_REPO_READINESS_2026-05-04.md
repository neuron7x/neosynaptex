# Canonical Repository Readiness Report

## Status

**PASS_DOCS_READY_BUT_MAIN_BLOCKED_BY_PHASE4_HASH_GATE**

README-audit scope is canonical and ready for operator review / push.
Full `main` readiness is **not** PASS at this branch state because
runtime hash-binding refuses to load (Phase 4 work-in-progress on
`substrates/serotonergic_kuramoto/adapter.py`). One additional
non-README finding (`pyproject.toml` description string) is recorded
below for operator decision.

## Repository

- Path: `/home/neuro7/neuron7xLab/neosynaptex`
- Branch: `feat/phase-4-substrate-resolution`
- Base: `c7f86f95` (`docs(phase_4): substrate resolution protocol`)
- Head: `63c54083` (`docs(readme): red-team pass — 2 surviving overclaim fixes`)
- Target branch: `main` (operator-confirmed); `git remote show origin`
  was not contacted (offline / not authenticated this session) so the
  default-branch claim is not verified through the remote.

## Verification Scope

**Included**: every `README.md` under the repository root, the
`docs/audit/README_TRUTH_AUDIT_2026-05-04.md` report, and
`pyproject.toml` (read-only check for forbidden-phrase contamination).

**Excluded** (by policy):
- `substrates/kuramoto/infra/terraform/modules/terraform-aws-eks/**`
- `substrates/kuramoto/infra/terraform/modules/terraform-aws-vpc/**`
- `substrates/kuramoto/infra/terraform/modules/terraform-aws-kms/**`
  (cloudposse upstream Terraform modules — vendored, not ours).
- `_static/`, `_templates/` Sphinx placeholder dirs.
- `.git/`, `.venv/`, `.mypy_cache/`, `.pytest_cache/`, `.hypothesis/`,
  `__pycache__/`, `node_modules/`, `*.egg-info/`,
  `site-packages/`.

## OpenAI-Style Anchor Stack Applied

- **Spec**: README claims as written at `c7f86f95..63c54083` plus the
  declared canon in `CANONICAL_POSITION.md` and `docs/CLAIM_BOUNDARY.md`.
- **Eval**: `git diff` per-file, `find`-based path verification,
  recursive `grep` over `--include="README.md"` for forbidden phrases
  and stale metric tokens, `python -m pytest --collect-only` for the
  test surface (blocked by hash gate, intentionally), direct
  inspection of evidence artefacts (`evidence/lemma_1_numerical.json`,
  `evidence/replications/registry.yaml`, `evidence/replications/*/result.json`).
- **Trace**: every command and outcome of this audit is in the
  shell session preceding this file; the README truth-pass commit
  set (5 commits) plus the red-team fix commit (1 commit) is the
  durable record on `feat/phase-4-substrate-resolution`.
- **Guardrail**: `tools/audit/claim_overclaim_gate.py` and the
  forbidden-phrase regex from this protocol's Phase 4 caught two
  surviving overclaims after the initial pass.
- **Red-team**: explicit grep gates re-run against all README files
  (changed and unchanged) with broader regexes than the audit agent
  used; the "Coq formally proven" claim was not on the audit's
  changed-file list and was caught only by the red-team sweep.
- **Report**: this file plus the updated audit report at
  `docs/audit/README_TRUTH_AUDIT_2026-05-04.md`.
- **Regression**: each surviving overclaim was converted into a
  documented commit (`63c54083`).

## README Audit Readiness

**Status: PASS.**

Evidence:
- 6 commits on `c7f86f95..63c54083`. All file changes are documentation
  (`*.md`); no source code, tests, configs, lockfiles, or ledgers
  modified.
- 26 README files changed, 6 `UPSTREAM_README.md` attribution files
  added, 1 audit report added, 1 readiness report added (this one).
- All known root-README aspirational badges and false-positive-rate
  claims (e.g. "1666 tests", "16 workflows", "PRODUCTIVE n=6873 vs
  NON-PRODUCTIVE n=1400 p=0.005***") are gone; root README cites
  verified file counts only.
- Root README aligns with `CANONICAL_POSITION.md`: γ ≈ 1 framed as
  "candidate cross-substrate regime marker under active falsification";
  the four falsifying records and the one within-substrate positive
  (CHF vs NSR `n=5/5`, Cohen `d = -2.56`) are listed explicitly.
- No occurrences of `1666 tests | 16 workflows | n=6873 | n=1400 |
  p=0.005 | PRODUCTIVE | NON-PRODUCTIVE` survive in any `README.md`.
- All "production-grade" / "enterprise-grade" / "world-class" hits
  in current README files are inside *removal-note* contexts (i.e.
  the rewritten substrate READMEs explicitly describe the framing
  *as something that was removed*).
- The "Coq formally proven" claim was downgraded to "specification
  only" because no `.v` source files exist under
  `substrates/bn_syn/specs/coq/` at HEAD.

## Main Full Readiness

**Status: PARTIAL / BLOCKED by Phase 4 hash gate.**

Evidence:
- `python -m pytest --collect-only` aborts at module import:
  ```
  core.gamma_registry.GammaRegistryError:
    ledger fails binding validation; runtime refuses to load.
    violations=['serotonergic_kuramoto: adapter_code_hash DRIFT —
      stored df55071e0dc8c2f1... vs actual ce453b1f81120b62...
      (source=substrates/serotonergic_kuramoto/adapter.py)']
  ```
  This failure is **class C** in this protocol's taxonomy (known
  Phase 4 hash-drift, by design on this branch). It is **not** a
  README-audit-introduced failure (class A).

- 22 untracked Phase 4 WIP files are present and untouched:
  - `.github/workflows/estimator_admissibility.yml`
  - `core/exponent_measurement.py`
  - `docs/audit/ESTIMATOR_ADMISSIBILITY_PROTOCOL.md`
  - `docs/audit/INDEPENDENT_FRONTIER_LAB_DISCIPLINE_REPORT.md`
  - `docs/audit/PHASE_4A_HORIZON_TRACE_PROTOCOL.md`
  - `docs/audit/PHASE_4B_CANONICAL_KURAMOTO_OBSERVABLES.md`
  - `evidence/claim_surface_reconciliation.json`
  - `evidence/estimator_admissibility/`
  - `substrates/serotonergic_kuramoto/horizon_trace_contract.yaml`
  - `substrates/serotonergic_kuramoto/observables.py`
  - `tests/test_estimator_admissibility.py`
  - `tests/test_horizon_trace_lint.py`
  - `tests/test_kuramoto_canonical.py`
  - `tests/test_phase_4a_horizon_trace_contract.py`
  - `tools/audit/horizon_trace_lint.py`
  - `tools/phase_3/admissibility/{estimators,metrics,run_admissibility_trial,synthetic_data,trial,verdict}.py`
  - `.hypothesis/`

  These are operator's WIP; not staged, not committed, not modified
  by this audit.

Blocking issue (full main): hash drift between
`substrates/serotonergic_kuramoto/adapter.py` and
`evidence/gamma_ledger.json`. Resolution requires either (a) a
ledger update commit by the operator landing the Phase 4 adapter
hash into `evidence/gamma_ledger.json`, or (b) operator's explicit
acceptance of Phase 4 branch state. Neither was attempted by this
audit.

## Commands Run

Phase 0 freeze:
```
git status --short
git branch --show-current
git log --oneline --decorate -n 30
git remote -v
git rev-parse HEAD
git rev-parse --verify c7f86f95
```

Phase 1 commit scope:
```
git log --oneline c7f86f95..HEAD
git diff --name-status c7f86f95..HEAD
git diff --stat c7f86f95..HEAD
```

Phase 2 inventory:
```
find . -path './.git' -prune -o -path './.venv' -prune -o \
  -path './node_modules' -prune -o -name 'README.md' -print | sort
git diff --name-only c7f86f95..HEAD | grep README
```

Phase 4 overclaim:
```
grep -RniE "<forbidden-phrases>" --include=README.md .
grep -RniE "1666 tests|16 workflows|6873|1400|p=0.005|PRODUCTIVE|NON-PRODUCTIVE" \
  --include=README.md .
```

Phase 5 paths:
```
grep -Rni "data_sanity.py" --include=README.md .
grep -RniE "PGO|BOLT|cross-language-LTO" --include=README.md .
grep -RniE "CLAIM_BOUNDARY|hash-binding|gamma_ledger|adapter\.py" --include=README.md .
find . -iname '*lemma_1*' -o -iname 'lemma1*'
ls substrates/kuramoto/scripts/data_sanity.py
```

Phase 6 deep sample heads on root, agents, kuramoto, hippocampal_ca1,
mfn, data/golden/kuramoto, core/rust/geosync-accel.

Phase 8 safe checks:
```
python -m pytest --collect-only -q   # blocked by hash gate (class C)
.venv/bin/pre-commit run --files <changed READMEs>   # not installed
```

## Results

- README files found in scope: **133**.
- README files changed across the 6 commits: **26 modified** + **6 added** as `UPSTREAM_README.md`.
- Audit report files: 2 (`README_TRUTH_AUDIT_2026-05-04.md`, this readiness report).
- Unsupported claims removed: ≥ 11 distinct overclaim categories
  (production-grade, enterprise-grade, "100% reproducible",
  world-class, "only open-source framework that…", fake test counts,
  fake workflow counts, "γ C-001 proved" without scope, pareidolic
  ASCII tables presented as evidence, "X-Form Thesis" prose, "Coq
  formally proven" without `.v` files).
- Broken references removed: 1 (`scripts/data_sanity.py` from the
  root `data/golden/kuramoto/README.md` — the script does not exist
  there; the homonymous script `substrates/kuramoto/scripts/data_sanity.py`
  is unrelated and remains correctly referenced from the substrate's
  own READMEs).
- Unverified items remaining: see `Manual Verification Needed` below.
- Automated checks executed: README grep gates, path-existence checks,
  pyproject.toml read.
- Known failures: pytest collection blocked by Phase 4 hash gate
  (class C, by design); pre-commit not installed in `.venv`.

## Hash / Ledger / Drift State

- **Hash-binding gate**: ACTIVE. `core/gamma_registry.py` refuses
  runtime load when adapter SHA-256 deviates from the pinned ledger
  value. This is a fail-closed feature, not a bug.
- **`substrates/serotonergic_kuramoto/adapter.py` drift**: present
  by design. Stored hash in ledger `df55071e0dc8c2f1…`; on-disk hash
  `ce453b1f81120b62…`. The Phase 4 work-in-progress is the cause.
- **Bypass attempted by this audit**: no.
- **Operator action needed**: yes — either land the new adapter hash
  into `evidence/gamma_ledger.json` (proper Phase 4 closure) or
  document explicit acceptance of the drift on this branch and gate
  the merge accordingly. This is **not** a README issue.

## Untracked WIP State

22 untracked Phase 4 WIP files (listed under "Main Full Readiness"
above) confirmed untouched. `git status --short` shows all 22 with
`??` markers and no `M`/`A`/`D` against the tracked tree. The audit
made zero edits, deletes, moves, or stages of any Phase 4 WIP file.

## Critical Findings

1. **`pyproject.toml` description string contains a phrase
   forbidden by `CANONICAL_POSITION.md`.**
   File: `pyproject.toml:8`
   Current value:
   `description = "NFI — Neuromodulatory Field Intelligence. γ ≈ 1.0 across independent substrates. Intelligence as regime property."`
   The phrase **"γ ≈ 1.0 across independent substrates"** equates to
   the forbidden rewording "γ ≈ 1 [proves anything] across substrates",
   which `CANONICAL_POSITION.md` explicitly bans, and contradicts the
   net position stated in the rewritten root README ("γ ≈ 1 has no
   surviving cross-substrate convergence claim at this commit").
   **This is a source-code change** (TOML metadata, not Markdown),
   so per non-negotiable rule 3 of this protocol, the audit did
   **not** modify it. Operator decision required: either rewrite the
   description to canon-compliant form (e.g. "Cross-substrate
   γ-scaling diagnostics, γ ≈ 1 as candidate marker under active
   falsification"), or explicitly grant the audit code-edit
   permission and re-run.

2. **No `.v` files anywhere under `substrates/bn_syn/`** despite the
   `formal-coq.yml` cron workflow targeting `specs/coq`. The README
   was downgraded to specification-only by this audit. The workflow
   itself was **not** modified. Operator decision: leave as-is
   (cron will fail nightly with "no inputs") or remove / pause the
   workflow.

3. **No `feat/phase-3-null-screen` cleanup.** `git log` shows the
   parallel branch reference `7bea0fec (feat/phase-3-null-screen)`;
   not in scope of this audit but worth surfacing.

## Manual Verification Needed

- **Default branch via `origin`** — `git remote show origin` was not
  executed because no network call was made; the operator's claim
  of "main" was accepted without remote confirmation.
- **CI status on GitHub** for the 6 README-audit commits is unknown
  (no push performed).
- **`pyproject.toml` description fix decision** (see Critical
  Findings #1).
- **Lemma 1 numerical artefact reproducibility** — the
  `evidence/lemma_1_numerical.json` cites
  `experiments/lemma_1_verification/verify_kuramoto_gamma_unity.py`
  with `script_sha256: f17866…` and `random_seed: 7`. The script
  was not executed by this audit; the README citation of "γ̂ =
  0.9923 numerically" is consistent with the artefact's structure
  but not re-derived here.
- **Twenty-one CI workflows** cited by the rewritten root README —
  the count was the directory listing under `.github/workflows/`;
  whether all 21 are active on this branch was not separately
  re-checked.
- **`docs/CLAIM_BOUNDARY.md` rows beyond C-001..C-004** were not
  cross-checked against the rewritten root README; if the boundary
  doc has additional rows, the root README would need a follow-up.

## Merge Decision

- merged locally: **no**
- pushed: **no**
- reason: README audit is `PASS`, but `MAIN_FULL_READINESS` is
  `PARTIAL/BLOCKED` because of the Phase 4 hash gate (class-C, known
  by design) and the `pyproject.toml` description finding. Per
  protocol Phase 10, do not auto-merge into `main` while
  `MAIN_FULL_READINESS` is partial. The 6 README-audit commits remain
  on `feat/phase-4-substrate-resolution` for operator review.

## Final Statement

> This repository state is verified against current local evidence
> only. No universal or absolute truth claim is made.

All defined local README-audit gates passed. Full main readiness
gates are not all green at this branch state, by design.
