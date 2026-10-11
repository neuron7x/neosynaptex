# Mycelium Gamma Definition Audit

> **Substrate.** `SUBSTRATE_006_MYCELIAL_ELECTROPHYSIOLOGY` (candidate, not in
> `docs/SUBSTRATE_MEASUREMENT_TABLE.yaml` as of 2026-04-21).
> **Authority.** Method Gate 0 — definition audit only. No data analysis.
> **Pair documents.** `docs/CLAIM_BOUNDARY.md`,
> `docs/MEASUREMENT_METHOD_HIERARCHY.md`,
> `docs/NULL_MODEL_HIERARCHY.md`,
> `docs/SUBSTRATE_MEASUREMENT_TABLE.yaml`,
> `docs/PREREG_TEMPLATE_GAMMA.md`.
> **Rule.** Freeze the γ definition before touching fungal data. Do not let
> a wrong method falsify a wrong hypothesis.

## Verdict

**`BLOCKED_BY_METHOD_DEFINITION`**

NeoSynaptex canon (as of 2026-04-21) does not provide an unambiguous
electrophysiological γ definition for *fungal* signals satisfying all four
gates jointly: (i) primary measurement method per
`MEASUREMENT_METHOD_HIERARCHY.md §2.1`, (ii) substrate-specific K and C
operationalisations per `CLAIM_BOUNDARY.md §4.3`, (iii) full five-family
null requirement per `NULL_MODEL_HIERARCHY.md §2`, (iv) public-bundle plus
preregistered acceptance window for the candidate exponent. Each
candidate definition fails on at least one of these four gates today,
and several fail on multiple. The fail-closed protocol therefore blocks
biological-pipeline work on this substrate until a follow-up canon PR
amends the measurement / null tables to cover fungal electrophysiology.

## Scope

This document audits **method definition only**. In particular:

- **No fungal data was analyzed.** No Adamatzky lab recordings, no
  Zenodo pleurotus / schizophyllum / cordyceps datasets, no biological
  signal of any kind was loaded, processed, or read into memory by the
  code that accompanies this audit.
- **No γ was computed on biological data.** No DFA, no spectral
  exponent estimation, no avalanche pipeline, no K(C) regression was
  executed against any fungal signal.
- **No biological dataset adapter was built.** The companion module
  `substrates/mycelium/method_gate.py` is a definition gate only;
  it loads a deterministic JSON contract and exposes pure validators.
- **No claim is made about whether mycelium is critical, conscious, or
  cognitive.** This audit is upstream of any such question.

This boundary is enforced by `substrates/mycelium/method_gate.py`:
`can_run_biological_pipeline()` returns `False` whenever
`status == "BLOCKED_BY_METHOD_DEFINITION"`, and
`can_promote_to_evidence_admissible()` returns `False` for the same
status — so even a downstream consumer that ignores this document
cannot quietly upgrade the substrate.

## Existing NeoSynaptex Canon

This section quotes the relevant canon verbatim (with file references)
so the audit verdict cannot be revised by paraphrase drift.

### γ-claim taxonomy and barrier discipline

`docs/CLAIM_BOUNDARY.md §1` (the single admissible working claim):

> "γ ≈ 1.0 is a candidate cross-substrate regime marker for a
> metastable critical state, tested through an open, falsifiable
> pipeline across neural, market, and morphogenetic substrates."

`docs/CLAIM_BOUNDARY.md §4` requires every γ-statement to name all
of: substrate identifier, unit of analysis, K and C operationalisations,
measurement method per `MEASUREMENT_METHOD_HIERARCHY.md`, null families
tested per `NULL_MODEL_HIERARCHY.md`, prereg pointer, public data
pointer, interpretation boundary. Statements missing any of 1–8 are
incomplete and "cannot rise above `hypothesized`" per the same section.

`docs/CLAIM_BOUNDARY.md §6` defines the claim-status taxonomy
(`measured`, `derived`, `hypothesized`, `unverified analogy`,
`falsified`).

### Frozen measurement-method hierarchy

`docs/MEASUREMENT_METHOD_HIERARCHY.md §2.1` (Primary, MUST run for every
neural EEG / LFP / spike substrate and for every market-spectrum
substrate):

> "specparam / FOOOF (Donoghue, Voytek et al.) — separates oscillatory
> peaks from the aperiodic 1/f component; returns the exponent as a
> direct parameter."
>
> "IRASA (Wen & Liu 2016) — frequency-irregular-resampling aperiodic
> separation. Runs as cross-check on specparam. Disagreement > 0.1 in
> exponent between the two flags a substrate for manual review."

`docs/MEASUREMENT_METHOD_HIERARCHY.md §2.2` (Primary for
avalanche-shaped substrates): Clauset–Shalizi–Newman framework with
`powerlaw` package; MLE α + x_min + KS-p ≥ 0.1 + LRT vs lognormal /
exponential / stretched-exp / truncated power-law.

`docs/MEASUREMENT_METHOD_HIERARCHY.md §2.3` (Secondary cross-checks,
MAY run, never primary):

> "DFA (detrended fluctuation analysis). α exponent cross-validates
> the spectral slope. Touboul & Destexhe 2021 warnings apply: DFA
> can pass crackling-noise-type tests on non-critical systems. Use
> DFA as confirmation, never as primary."

`docs/MEASUREMENT_METHOD_HIERARCHY.md §2.4` (Forbidden as primary):
simple log-log regression, Hurst via R/S, visual inspection of a
log-log plot, "it looks power-law" without x_min / LRT / KS-p.

### Frozen null-model hierarchy

`docs/NULL_MODEL_HIERARCHY.md §1`:

> "A γ-value is admissible only if it is statistically separable from
> every null-model family listed below at the preregistered
> significance threshold. If any null family reproduces γ, the γ-claim
> collapses under `CLAIM_BOUNDARY.md §5.3`."

`docs/NULL_MODEL_HIERARCHY.md §2` lists the five required null
families: shuffled, IAAFT, OU (or AR(1) analogue), Poisson
(point-process substrates), latent-variable (Morrell, Nemenman &
Sederberg 2024 — primary threat model).

### Frozen substrate measurement table

`docs/SUBSTRATE_MEASUREMENT_TABLE.yaml` (lines 24–303 inspected
verbatim) lists every canonical substrate with K_definition,
C_definition, signal, measurement_method, fit_window, controls,
allowed_claim, claim_status. **Mycelial electrophysiology is
absent from this table.** The only "mycelium" reference in canon is
`substrates/mfn/` (Mycelium Fractal Net — a Gray-Scott
reaction-diffusion morphogenesis simulator), which is a synthetic
non-electrophysiological substrate and explicitly not the candidate
under audit here.

### Substrates deliberately NOT in canon

`docs/SUBSTRATE_MEASUREMENT_TABLE.yaml` lines 305–316:

> "The following are named in repo context but are NOT current
> γ-claim substrates; listing them here is premature: hippocampal_ca1,
> geosync_market, mlsdm, lotka_volterra, cfp_diy. Inclusion requires
> landing a PR that populates all nine required fields above AND
> satisfies CLAIM_BOUNDARY.md §4."

`SUBSTRATE_006_MYCELIAL_ELECTROPHYSIOLOGY` is in the same status as
that list: named only in candidate-substrate planning, not yet
provisioned with the required nine fields.

### Summary of what canon does NOT yet specify for mycelium

1. There is no row for fungal electrophysiology in
   `SUBSTRATE_MEASUREMENT_TABLE.yaml`.
2. There is no fungal-specific entry in
   `MEASUREMENT_METHOD_HIERARCHY.md §5` (the substrate-method matrix).
3. There is no fungal-specific calibration of any null family in
   `NULL_MODEL_HIERARCHY.md` (in particular: τ for OU, latent-variable
   model class, point-process applicability for spike-like fungal
   bursts).
4. There is no preregistered γ-acceptance window for fungal
   electrophysiology in `PREREG_TEMPLATE_GAMMA.md`.

## Candidate Definitions

Five candidate γ definitions are evaluated against the canon above.
For each: formula, mathematical meaning, biological interpretation,
data requirements, null requirements, failure mode, and acceptance /
rejection reason.

### 1. `DFA_2H_PLUS_1` — γ = 2H + 1 from DFA Hurst exponent

- **Formula.** `γ = 2 H + 1`, where `H` is the Hurst exponent estimated
  by detrended fluctuation analysis on the raw electrophysiological
  trace; `γ ≈ 1.0` requires `H ≈ 0`.
- **Mathematical meaning.** Relates the temporal long-range
  autocorrelation exponent (DFA) to a power-law exponent in the
  cumulative-fluctuation domain. The conversion `γ = 2H + 1` is one
  among several conventions (alternative: `β = 2H − 1` for the PSD
  slope of a process whose increments have Hurst H), so the mapping
  to "the" γ-program exponent is not unique.
- **Biological interpretation.** `H ≈ 0` would mean the fungal
  electrical signal is **anti-persistent / white-noise-like** with no
  long-range temporal correlations. This is biologically implausible
  for raw fungal recordings (see `## DFA Tension` below).
- **Data requirements.** Raw, drift-corrected fungal voltage trace;
  scales chosen to avoid both the fast electrode-polarisation regime
  and the slow mycelial-growth regime; minimum length ≥ 10× the
  longest scale fit; stationarity test passed before fitting.
- **Null requirements.** Per `NULL_MODEL_HIERARCHY.md §2`, all five
  families must reject. For DFA specifically, OU-with-matched-τ is
  the strongest test: OU produces an α plateau that fully overlaps
  the typical fungal-recording α range, so OU separation requires
  bootstrap-CI evidence that γ_real lies outside the OU surrogate
  envelope.
- **Failure mode.** DFA is `MEASUREMENT_METHOD_HIERARCHY.md §2.3`
  **secondary**, never primary. Promoting it to primary contradicts
  the frozen hierarchy. Touboul & Destexhe 2021 explicitly show DFA
  passes crackling-noise tests on non-critical systems, so a
  γ-claim resting on DFA alone is the literal definition of "wrong
  method" the protocol is designed to reject.
- **Verdict.** **REJECTED as primary.** Permitted as secondary
  cross-check only, paired with a primary aperiodic-spectral
  estimate.

### 2. `SPECTRAL_APERIODIC` — γ from FOOOF / specparam aperiodic exponent

- **Formula.** `PSD(f) ≈ 10^b · f^(−χ)` over a fit window
  `[f_low, f_high]`; the FOOOF "aperiodic exponent" `χ` is the
  candidate γ proxy. Mapping to the γ-program exponent
  (`γ ≈ 1.0` ↔ `χ ≈ 1`) requires an explicit substrate-specific
  semantic bridge stating what K and C represent in the fungal case.
- **Mathematical meaning.** Separates oscillatory peaks from the 1/f
  background, returns the aperiodic slope as a direct parameter
  (Donoghue, Voytek et al.). IRASA cross-check required at
  `|Δχ| ≤ 0.1`.
- **Biological interpretation.** The aperiodic 1/f exponent on a
  fungal electrical recording would, by analogy with neural data,
  index the balance between fast and slow internal fluctuations. The
  analogy is precisely what is on trial; it is not an established
  fungal physiology concept.
- **Data requirements.** Rejection of electrode-polarisation drift,
  electrode-coupling artefacts, and ambient-temperature 1/f
  contributions; fit window chosen on a fungal-physiology basis,
  not by analogy with EEG; sampling-rate constraints documented
  per `MEASUREMENT_METHOD_HIERARCHY.md §3.2`.
- **Null requirements.** Same five families. OU and latent-variable
  are the binding ones — Morrell, Nemenman & Sederberg 2024 showed
  γ = 1.1–1.3 from latent-variable coupling in non-critical systems,
  and that critique transfers without modification to any
  fungal-electrophysiology γ-claim.
- **Failure mode.** Without a fungal-specific K and C definition in
  `SUBSTRATE_MEASUREMENT_TABLE.yaml`, even a clean χ-estimate is an
  uninterpreted number. Without a fungal-specific OU τ-calibration
  in `NULL_MODEL_HIERARCHY.md`, the OU null is not falsifiable.
- **Verdict.** **CANDIDATE for future acceptance.** Method aligns
  with primary canon, but cannot be accepted today because (a) no
  K / C operationalisation exists for fungal signals, (b) no fungal
  OU calibration exists, (c) no preregistered acceptance interval
  exists. These are addressable by a follow-up canon PR; they are
  not addressable from inside this audit.

### 3. `EVENT_AVALANCHE` — γ from Clauset–Shalizi–Newman event-size law

- **Formula.** `P(s) ∝ s^(−α)` for event sizes above x_min; γ-program
  reads `γ` from the family of avalanche exponents (α, τ, 1/(σνz))
  that share the crackling-noise relation `α = 1 + (β − 1)τ` (Sethna
  et al. 2001).
- **Mathematical meaning.** Power-law size distribution of discrete
  events with MLE α, x_min KS-minimised, KS-p ≥ 0.1, LRT vs
  lognormal / exp / stretched / truncated.
- **Biological interpretation.** Treats fungal "spikes" (the
  literature term for the 0.5–10 mV transients reported by Adamatzky
  and others) as discrete events; tests whether their amplitude or
  inter-spike-interval distribution is power-law.
- **Data requirements.** Operational fungal-spike detector with
  sensitivity / specificity benchmarked against a hand-labelled
  subset; per-electrode rate adequate for CSN (Clauset 2009 advises
  N ≥ 50 above x_min, with N ≥ 1000 strongly preferred);
  shape-collapse + branching-ratio + spatial-correlation triple
  convergence per `MEASUREMENT_METHOD_HIERARCHY.md §2.3` (Marshall
  et al. 2016).
- **Null requirements.** Five families plus rate-matched Poisson
  (per `NULL_MODEL_HIERARCHY.md §2.4` — point-process substrates);
  rate-matched Poisson is the canonical sanity floor for any
  event-based γ-claim.
- **Failure mode.** Touboul & Destexhe 2021: scaling relation alone
  passes on non-critical systems, so even a clean CSN fit + scaling
  relation is insufficient. Three independent signatures
  (shape collapse, branching ratio σ ≈ 1, scale-free spatial
  correlations) must converge.
- **Verdict.** **CANDIDATE for future acceptance, conditional on
  detector definition.** Cannot be accepted today because (a) no
  canonical fungal-spike detector exists in the repo, (b) the
  spatial-correlation requirement cannot be met by the typical
  electrode-array geometries used in published Adamatzky-style
  experiments without a substrate-specific spatial-criticality
  amendment to the method hierarchy.

### 4. `SUBSTRATE_KC` — γ from Theil-Sen log-log slope of substrate K vs C

- **Formula.** `K(C) ∝ C^(−γ)` from a Theil-Sen robust regression on
  windowed (K, C) pairs (the canonical NeoSynaptex measurement for
  zebrafish_wt, gray_scott, kuramoto_market, bnsyn).
- **Mathematical meaning.** Substrate-specific operationalisation
  of the cost-complexity reframing; γ is the slope, with bootstrap
  CI95 over windows.
- **Biological interpretation.** Requires a substrate-specific
  definition of K (topological complexity proxy) and C (thermodynamic
  cost proxy) that is biologically defensible for fungal mycelium.
  Candidate K: per-window spike-rate variability over electrodes;
  candidate C: total electrical energy per window. Both are guesses
  pending substrate physiology.
- **Data requirements.** Multi-electrode fungal recording with
  enough simultaneous channels to define a K-vs-C window pair;
  fungal-physiology basis for the K and C choices.
- **Null requirements.** Five families.
- **Failure mode.** No K and C definitions exist in canon for fungal
  electrophysiology. The choice would be ad hoc, and the substrate's
  γ would track that choice — exactly the failure mode
  `CLAIM_BOUNDARY.md §6` calls "data-driven metric switching".
- **Verdict.** **CANDIDATE for future acceptance, conditional on
  K and C freeze.** Cannot be accepted today because no K, C, or
  fit-window definitions are written into
  `SUBSTRATE_MEASUREMENT_TABLE.yaml` for this substrate.

### 5. `NONE` — no γ definition admissible under current canon

- **Formula.** N/A.
- **Mathematical meaning.** N/A.
- **Biological interpretation.** N/A.
- **Data requirements.** N/A.
- **Null requirements.** N/A.
- **Failure mode.** Trivially passes; codifies the fail-closed
  default for the substrate.
- **Verdict.** **SELECTED.** Until a follow-up canon PR amends
  `SUBSTRATE_MEASUREMENT_TABLE.yaml`,
  `MEASUREMENT_METHOD_HIERARCHY.md §5`, and
  `NULL_MODEL_HIERARCHY.md` to cover fungal electrophysiology, the
  honest verdict is that no biological pipeline may run on this
  substrate.

## DFA Tension

The candidate `DFA_2H_PLUS_1` carries a sharp internal tension that
this audit must record explicitly so a future PR cannot quietly use
it as primary.

The conversion `γ = 2 H + 1` with `γ ≈ 1.0` implies `H ≈ 0`. The
Hurst exponent `H ∈ (0, 1)` of a fractional Brownian motion takes
biological / physical meaning as follows:

- `H ≈ 0` — anti-persistent in the limiting sense; cumulative process
  is white-noise-like with no long-range correlations.
- `H = 0.5` — uncorrelated random walk (classical Brownian).
- `H > 0.5` — persistent / long-range correlated.

Fungal electrophysiological recordings reported in the published
literature (Adamatzky and follow-ups) typically exhibit slow
electrode-polarisation drift, ambient-temperature 1/f, and burst
structure (the 0.5–10 mV "spike" trains). Each of these contributes
to a DFA scaling regime in which `H` is **above** 0.5 over at least
the slow-scale window. `H ≈ 0` is therefore unusual, not impossible,
and would require explicit pre-detrending choices that bias the
estimate downward.

This audit does not adjudicate whether `H ≈ 0` for fungal recordings
is plausible, implausible, or unresolved. It only records that the
γ-program convention `γ = 2H + 1` plus γ ≈ 1.0 forces a
**substantively non-trivial empirical claim** about fungal H, and
that this claim cannot be inherited from neural-substrate experience.
The honest position is: **unresolved without empirical
pre-registration with literature anchors,** and DFA cannot run as
primary anyway per `MEASUREMENT_METHOD_HIERARCHY.md §2.3`. The
tension is recorded in the JSON contract as
`h_tension_if_dfa = true` so the gate validator will reject any
future audit JSON that re-introduces DFA without re-recording it.

## Selected Primary Definition

`primary_gamma_definition = NONE` (status `BLOCKED_BY_METHOD_DEFINITION`).

Per `CLAIM_BOUNDARY.md §5.1` (six-gate evidential lane) and §6
(claim-status taxonomy): no biological pipeline may promote
`SUBSTRATE_006_MYCELIAL_ELECTROPHYSIOLOGY` beyond
`EVIDENCE_CANDIDATE` — i.e., the substrate stays out of the
evidential lane and out of the cross-substrate convergence count
(C-004) until and unless a follow-up canon PR adds:

1. A row in `SUBSTRATE_MEASUREMENT_TABLE.yaml` with K_definition,
   C_definition, signal, measurement_method, fit_window, controls,
   allowed_claim populated.
2. A column / row entry in `MEASUREMENT_METHOD_HIERARCHY.md §5` with
   per-method requirements.
3. A fungal-specific calibration paragraph in
   `NULL_MODEL_HIERARCHY.md §2.3` (OU τ) and §2.5 (latent-variable
   model class).
4. A preregistered γ-acceptance interval in
   `PREREG_TEMPLATE_GAMMA.md`.
5. An external public bundle (Zenodo / institutional archive)
   pointing at a specific fungal recording set with fixed sample
   rate, electrode geometry, and metadata.

`can_run_biological_pipeline()` returns `False` under this verdict.
`can_promote_to_evidence_admissible()` returns `False` under this
verdict.

## Secondary Metrics

If and when a primary definition is accepted by the follow-up canon
PR, the following may run **alongside** as secondary descriptive
cross-checks; none of them, alone or in combination, can promote
the substrate beyond `EVIDENCE_CANDIDATE`:

- DFA α (per `MEASUREMENT_METHOD_HIERARCHY.md §2.3`).
- Multifractal DFA spectrum width (per §2.3, Aguilera 2015 critique).
- Branching ratio σ on detected events (per §2.3, Marshall 2016).
- Avalanche shape collapse on detected events (per §2.3,
  Marshall 2016; only if spatial geometry permits).
- Inter-spike-interval coefficient of variation (descriptive).
- Per-electrode mean rate (descriptive).
- IRASA cross-check on aperiodic spectral fit (mandatory cross-check,
  not an independent metric).

## Forbidden Promotions

- secondary metrics cannot promote the claim
- no data-driven metric switching
- no γ definition changes after seeing fungal results
- no universality claim from this substrate alone

## Non-Claims

- This audit does not claim that mycelium is neural.
- This audit does not claim that mycelium is conscious.
- This audit does not claim that fungal electrical activity proves γ ≈ 1.0.
- This audit does not analyze fungal data.
- This audit does not prove universality.

## Next Step

`block until measurement hierarchy is clarified`

Concretely: open a follow-up canon PR that adds (i) a fungal
electrophysiology row to `SUBSTRATE_MEASUREMENT_TABLE.yaml`, (ii) a
column / row entry to `MEASUREMENT_METHOD_HIERARCHY.md §5`, (iii)
fungal-specific OU and latent-variable calibrations in
`NULL_MODEL_HIERARCHY.md`, (iv) a preregistered γ-acceptance interval
in `PREREG_TEMPLATE_GAMMA.md`, and (v) a public-bundle pointer
satisfying `CLAIM_BOUNDARY.md §5.1` gate (a). Re-run this audit with
those amendments before any biological pipeline work begins. Do not
relax the gate.
