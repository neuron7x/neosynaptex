# README Audit Report — 2026-05-04

Branch: `feat/phase-4-substrate-resolution`
HEAD prior to audit: `c7f86f95`

## Summary

- README files reviewed: **117** (all in-scope discovered files plus
  newly-preserved `UPSTREAM_README.md` siblings).
- README files rewritten in full: **15** (root, agents, experiments,
  core/rust/geosync-accel, data/golden/kuramoto, formal/coq/bnsyn,
  formal/tla/bnsyn, six substrate roots).
- README files edited (targeted overclaim trim, content otherwise
  preserved): **7** (kuramoto sub-READMEs and one MLSDM deploy doc).
- README files left unchanged because already aligned with the canon:
  ~95 (mostly small placeholder READMEs and TradePulse / MLSDM
  internal infrastructure docs that did not overclaim).
- README files excluded by policy (vendored cloudposse Terraform
  modules and venv/cache placeholders): **3 module families** plus
  cache directories.
- Upstream-attribution preservation files added: **6**
  (`UPSTREAM_README.md` per each substrate that previously held
  upstream-vendored content as its primary README — bn_syn,
  hippocampal_ca1, kuramoto, mfn, mlsdm, zebrafish).
- Broken / stale references removed or reduced: most notable —
  unverifiable global "1666 tests, 16 CI workflows" badge in the root
  README replaced with verified file counts (136 `test_*.py`, 21
  workflow files); removed reference to a non-existent
  `data/golden/...csv` shipped sample; removed
  unverified PGO/BOLT performance numbers from
  `core/rust/geosync-accel/README.md`.
- Unsupported / overclaim phrases removed across the rewrite: γ ≈ 1
  framed as a confirmed law, "Production-Ready/Grade",
  "Enterprise-Grade", "Cutting-edge", "Three stars. p = 0.005",
  "production-grade", "fully formalized, validated", "world-class",
  "Equivalent to DeepMind/OpenAI/xAI", "X-Form Thesis" prose, and
  the badge wall asserting "γ C-001 proved" without the C-001 row's
  scope qualification. The CNS-AI loop substrate is now explicitly
  described as historical-exploratory only.
- Unverified items remaining (intentional, marked in target READMEs):
  test counts inside vendored substrate trees (BN-Syn, MFN,
  Hippocampal-CA1, MLSDM, TradePulse) are **not** aggregated into the
  parent neosynaptex test runner; their upstream README badges
  describe upstream repos, not the parent count.

## Changes by File

### `README.md` (root)

- Changed: full rewrite. Now opens with the canon-position quote, a
  "What it is" paragraph, an explicit "Current evidence state"
  section that lists falsifying records (BTC/USDT 1h, FRED INDPRO,
  PhysioNet NSR2DB n=5 multifractal, EEG eegbci pilot) and the one
  within-substrate positive (CHF vs NSR n=5/5, Cohen d = 2.56). Net
  position is stated explicitly: γ ≈ 1 has no surviving cross-
  substrate convergence claim at this commit.
- Removed: "1 proved / 5 empirical" banner, "tests-1666" badge,
  "p-value 0.005" badge, the "Six substrates" pareidolic ASCII table
  including Zebrafish/Reaction-Diff/Spiking-Net/Market/Neosynaptex
  with stand-alone γ values presented as evidence, the
  "PRODUCTIVE n=6873 / NON-PRODUCTIVE n=1400" "p=0.005 ***" claim
  block, the "X-Form Thesis" prose ("Singularity is not an event of
  the future"), and the historical CNS-AI corpus γ ≈ 1.059 figure
  reused as a substrate row.
- Fixed: file-tree references (replaced "8 substrate adapters" with
  the verified set discovered under `substrates/`); replaced
  "1666 tests" with the verified `136 test_*.py` count; replaced
  "16 CI workflows" with `21 workflow files`.
- Unverified: none — every retained statement either points to a
  verifiable file in the tree or to `evidence/replications/registry.yaml`.

### `agents/README.md`

- Changed: full rewrite as a vendored-library-under-neosynaptex doc.
- Removed: "Hybrid Cognitive Functions for Intelligent Systems"
  banner; the badge wall claiming "tests-76-passed" (actual:
  9 test files, 141 test functions by static count; pass count not
  aggregated by parent runner); the marketing tagline "engineered
  for the next generation of intelligent systems"; the
  "γ_DNCA ~ +1.0 (consistent with γ_WT = +1.043 zebrafish McGuirl
  2020)" cross-substrate claim — that is a forbidden cross-substrate
  convergence assertion under the canon.
- Fixed: file-tree references against `src/neuron7x_agents/`.
- Unverified: parent-aggregated pass/fail count for the 141 agent
  tests.

### `experiments/README.md`

- Changed: full rewrite, structured against the actual subdirectories
  (`lemma_1_verification`, `lm_substrate`, `probe_dialogue_null`,
  `scaffolding_trap`, `causal_topology`, `spectral_coherence{,_v3}`).
- Removed: stale 2-row "Index" table missing 5 of the 7 actual
  experiment subdirectories.
- Fixed: explicit pointer that `evidence/replications/registry.yaml`
  is the source of truth for any verdict referenced from these
  experiments.
- Unverified: nothing claimed beyond presence/role of files.

### `core/rust/geosync-accel/README.md`

- Changed: full rewrite, content list now matches `src/` exactly.
- Removed: PGO/BOLT/cross-language-LTO step-by-step procedure
  presented as an established build path (no benchmark artefact
  pinned in repo); marketing framing of "2026 Standard".
- Fixed: build commands match the present `Cargo.toml` /
  `pyproject.toml`; clarified that io_uring features depend on
  Linux kernel support.
- Unverified: speed-up numbers (explicitly flagged as build-time
  targets, not measured).

### `data/golden/kuramoto/README.md`

- Changed: full rewrite as a small placeholder.
- Removed: instruction to run `python scripts/data_sanity.py
  data/golden` — no such script exists in `scripts/`. Reference to
  a shipped CSV file that is not in the directory (only the
  `.meta.json` sidecar is present).
- Fixed: directory contents now reflect what is actually committed.

### `formal/coq/bnsyn/README.md`

- Changed: full rewrite to make the verified scope explicit.
- Removed: aspirational "Production-Grade" / "neosynaptex-equivalence"
  framing; emoji status decorations; "Phase 1/2/3" roadmap
  presented as an active, dated plan.
- Fixed: explicit list of which theorems are proven vs which are
  proof obligations only.

### `formal/tla/bnsyn/README.md`

- Changed: full rewrite to make scope explicit (bounded
  `MaxSteps = 100` model, simplified gate sigmoid). Removed
  redundant boilerplate.

### `substrates/zebrafish/README.md`

- Changed: full rewrite as a canon-facing substrate doc; the
  upstream McGuirl/Volkening/Sandstede README is preserved verbatim
  at `UPSTREAM_README.md` for attribution.
- Removed: the practice of presenting an upstream pattern-
  quantification README as the primary substrate page (which
  caused the substrate to silently inherit the original PNAS
  framing).
- Fixed: explicit verdict statement (no registry entry filed; γ
  values referenced from `gamma_ledger.json` are not licensed for
  cross-substrate convergence).

### `substrates/bn_syn/README.md`

- Changed: full rewrite. Upstream BN-Syn README preserved at
  `UPSTREAM_README.md` for tooling reference.
- Removed: top-level usage of the upstream "canonical proof spine"
  badge wall as the substrate's own evidence claim;
  "Production-grade" / "single canonical entry surface" framing
  that conflated standalone-tool usability with γ-program evidence.
- Fixed: explicit substrate class, verdict, and pointer to
  registry / claim-boundary canon.

### `substrates/hippocampal_ca1/README.md`

- Changed: full rewrite. Upstream README preserved at
  `UPSTREAM_README.md`.
- Removed: "Production-Grade", "100% reproducible", "8-phase
  evolution plan" framings, automation-script badge wall,
  "13 DOI references" presented as substrate-level evidence.
- Fixed: explicit substrate class and verdict; pointer to canon.

### `substrates/kuramoto/README.md`

- Changed: full rewrite. Upstream TradePulse README preserved at
  `UPSTREAM_README.md`.
- Removed: "Enterprise-Grade Algorithmic Trading Platform" banner;
  "production-grade", "advanced", "comprehensive" superlatives
  treated as canon-level statements; full feature inventory
  inherited as substrate evidence.
- Fixed: explicit verdict (closely related to the falsifying record
  `binance_btcusdt_1h_pilot_2026_04_14`); pointer to canon.

### `substrates/mfn/README.md`

- Changed: full rewrite. Upstream MFN README preserved at
  `UPSTREAM_README.md`.
- Removed: "The only open-source framework that …" comparison
  table treated as canon framing; tests-2428 / coverage-82 % badges
  presented as parent-level metrics.
- Fixed: substrate class, verdict, pointer to canon.

### `substrates/mlsdm/README.md`

- Changed: full rewrite. Upstream MLSDM README preserved at
  `UPSTREAM_README.md`.
- Removed: "production-ready, neurobiologically-grounded cognitive
  architecture with moral governance" framing presented as
  substrate-level evidence.
- Fixed: substrate class, verdict, pointer to canon.

### `substrates/kuramoto/legacy/README.md`

- Changed: targeted edit — added an audit-time verification line
  confirming zero `from kuramoto.legacy` imports across the tree at
  this commit.

### `substrates/kuramoto/cortex_service/README.md`

- Changed: targeted edit — replaced "Enterprise-grade cognitive
  signal orchestration microservice" with the un-modified
  "Cognitive signal orchestration microservice".

### `substrates/kuramoto/neurotrade_pro/README.md`

- Changed: targeted edits — replaced "Production-Ready" in the
  title with neutral phrasing; replaced "fully formalized,
  validated, and runnable" with just "runnable".

### `substrates/kuramoto/core/indicators/README.md`

- Changed: targeted edits — replaced "advanced … cutting-edge"
  framing in the purpose paragraph; relabelled the
  `KuramotoIndicator` row from "Production-ready Kuramoto …" to
  the un-modified description.

### `substrates/kuramoto/interfaces/README.md`

- Changed: targeted edit — replaced "production-grade UI" with
  "Next.js UI" in the interfaces list.

### `substrates/kuramoto/infra/terraform/eks/README.md`

- Changed: targeted edit — replaced "production-ready Amazon EKS
  foundation" with "Amazon EKS foundation".

### `substrates/mlsdm/deploy/README.md`

- Changed: targeted edit — clarified that the "production-ready"
  framing is upstream-MLSDM's, not the parent neosynaptex canon's.

## Repository-Wide Issues

- **Vendored upstream subprojects.** Six substrate trees (BN-Syn,
  Hippocampal-CA1, MFN, MLSDM, TradePulse / kuramoto, zebrafish)
  were absorbed wholesale into `substrates/<name>/`, **including
  their original READMEs and badge walls**. Those upstream READMEs
  carry framings ("Production-Grade", "Enterprise-Grade",
  "Cutting-edge", per-project test counts) that are accurate for the
  upstream repository but become overclaims when read as
  neosynaptex substrate-level evidence. This audit standardises the
  pattern: each substrate root README is now a thin canon-facing
  page; the upstream content is preserved verbatim under
  `UPSTREAM_README.md`.

- **Test-count drift.** The parent neosynaptex tree has 136
  `test_*.py` files. Several READMEs (root + agents) advertised
  pre-audit numbers (1666, 76) inherited from earlier commits or
  upstream projects. Root README is now corrected; agents README
  reports the static enumeration of 9 files / 141 functions and
  flags that pass-count is not aggregated.

- **γ ledger binding.** The runtime hash-binding gate currently
  refuses to load the test conftest because the on-disk
  `serotonergic_kuramoto/adapter.py` SHA does not match the value
  pinned in `evidence/gamma_ledger.json`. This is by design and
  expected during Phase 4 substrate-resolution work; it is **not**
  a defect introduced by the audit. Test-count and pass/fail
  numbers in the rewritten READMEs therefore use static file
  enumeration as the verified anchor rather than `pytest --collect-only`
  output.

- **Pareidolic / decorative ASCII art.** The pre-audit root README
  contained six ASCII renderings of substrates (zebrafish stripes,
  reaction-diffusion field, spiking nets, market icons,
  CNS-AI-loop arrows) presented adjacent to γ values, structurally
  inviting a visual evidence interpretation. Per
  `CANONICAL_POSITION.md` "Forbidden rewordings" line 21 ("Any
  visual or pareidolic image treated as evidence"), the entire
  ASCII-art block has been removed.

## Manual Verification Needed

- **TradePulse, MFN, BN-Syn, Hippocampal-CA1, MLSDM standalone test
  totals.** Each upstream tree has its own pytest runner. Their
  badge walls in the now-archived `UPSTREAM_README.md` files
  reference upstream-CI numbers; reproducing them inside the parent
  neosynaptex tree was out of scope for this audit and the
  hash-binding gate currently blocks parent-level collection. A
  follow-up pass after Phase 4 resolution should re-collect these
  totals and update the substrate READMEs.

- **`substrates/zebrafish/UPSTREAM_README.md`.** Contains MATLAB +
  Python pipeline instructions from McGuirl et al. that depend on
  external sample data (`data/sample_inputs/Out_*_default_1.mat`,
  `data/sample_dist_mats/`). Whether those sample files are
  shipped or only fetched on demand from the figshare project
  72689 was not verified at this commit; the substrate's
  neosynaptex adapter does not depend on them.

- **`evidence/replications/registry.yaml` schema vs the canonical
  protocol document.** The registry schema is checked
  programmatically by `tools/audit/replication_index_check.py`. The
  README rewrite assumes the gate is the canonical authority. If a
  subsequent prereg edit fails the gate, the registry — not the
  README — should be the artefact updated.

- **CI workflow file count (21).** The number is the directory
  listing under `.github/workflows/`; whether all 21 are active on
  pushes to this branch was not separately re-checked. The root
  README cites "21 CI workflow files", not "21 active workflows".

- **`docs/CLAIM_BOUNDARY.md` claim row C-005..C-N**, if any, were
  not separately exhibited in the rewritten root README, which
  references C-001..C-004 only via `docs/CLAIM_BOUNDARY.md`. If
  later rows are added, the root README should be re-checked.
