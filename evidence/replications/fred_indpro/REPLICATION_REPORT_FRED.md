# FRED INDPRO γ-Replication Report — v1.0

> **Substrate.** `market_fred / fred_indpro` per
> `docs/SUBSTRATE_MEASUREMENT_TABLE.yaml`.
> **Protocol.** γ-program Phase VI §Step 23.
> **Method hierarchy.** `docs/MEASUREMENT_METHOD_HIERARCHY.md §2.3`
> (bounded secondary — Welch-PSD + Theil-Sen).
> **Null hierarchy.** `docs/NULL_MODEL_HIERARCHY.md §2`.
> **Pair.** `docs/CLAIM_BOUNDARY.md`.
> **Date.** 2026-04-14.

## 1. TL;DR

- **γ = 0.9414** on FRED INDPRO monthly log-returns, 1919–2026
  (n = 1285 valid log-returns).
- CI95 = [0.6408, 1.0948]; r² = 0.520; n_frequencies fit = 128.
- **Claim status: `hypothesized`.** Not measured. Not evidential.
- **Reason: γ is NOT separable from AR(1) null** (z = 0.74,
  `separable_at_z3 = False`). IAAFT null also non-separable
  (z = 1.94). Only the shuffled null rejects (z = 17.7), which is
  the weakest family and does not alone license promotion.

Per `NULL_MODEL_HIERARCHY.md §6`, failure on AR(1) / IAAFT is a
direct `claim_status: falsified` trigger for an evidential claim.
Since the claim is still `hypothesized` on this substrate, the
effect of the nulls is to block promotion to `measured`, not to
downgrade from anywhere. This is the protocol's correct outcome
for a bounded-secondary pilot.

## 2. Data provenance

| Field | Value |
|---|---|
| `series_id` | `INDPRO` |
| `source_url` | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDPRO` |
| `license` | Public domain (US government) |
| `fetched_utc` | 2026-04-14 (exact timestamp in `result.json`) |
| `fetch_method` | `curl` (Python `urllib` timed out in sandbox; curl succeeded) |
| `bytes` | see `result.json :: provenance.bytes_count` |
| `sha256` | see `result.json :: provenance.sha256` |
| `raw_csv` | `evidence/replications/fred_indpro/INDPRO.csv` |
| `raw_rows` | 1286 (including header) |
| `observation_range` | 1919-01-01 → 2026-02-01 |
| `frequency` | Monthly |
| `n_valid_log_returns` | 1285 |

The raw CSV is committed alongside this report (small file,
< 50 KB) so the full replication is self-contained in the repo.

## 3. Method

| Component | Choice | Rationale |
|---|---|---|
| Signal | log-returns of INDPRO levels | Standard for macro spectral analysis |
| Sampling fs | 1.0 (cycles/month) | Native monthly frequency |
| PSD | Welch, `nperseg = 256`, detrend=constant | scipy.signal.welch default-pair |
| Exponent fit | Theil-Sen robust regression on log(f)-log(PSD) | robust to outliers (`MEASUREMENT_METHOD_HIERARCHY.md §2.3`) |
| Bootstrap | 500 resamples of frequency-PSD pairs | conservative CI union with Theil-Sen CI |
| Fit range | all f > 0 | no peak exclusion needed for macro monthly data |

**Method label.** `welch_psd_theilsen`. This is explicitly a
**bounded-secondary** method. Upgrade to specparam + IRASA
(§2.1 primary) is a follow-up PR once the substrate has one prereg
filed (Phase III §Step 13).

## 4. Result — point estimate

| Quantity | Value |
|---|---|
| γ | 0.9414 |
| CI95 low | 0.6408 |
| CI95 high | 1.0948 |
| r² | 0.520 |
| n frequencies fit | 128 |
| n samples (log-returns) | 1285 |

γ = 0.94 is within the **prior range 0.5–1.5** for `market_macro`
declared in `docs/DATA_ACQUISITION_AND_REPLICATION_PLAN.md §3`. It
is NOT predicted by any NeoSynaptex theory — the prior is a
literature-sourced posterior from Hengen-Shew / Priesemann /
Bouchaud observations.

## 5. Null comparison

Per `NULL_MODEL_HIERARCHY.md §2` required families (with
applicability notes):

| Null family | Required? | μ_surrogate | σ_surrogate | z-score | real outside null CI95? | separable at |z|≥3? |
|---|---|---|---|---|---|---|
| shuffled | yes | 0.0059 | 0.0529 | 17.676 | YES | **YES** |
| IAAFT | yes | 0.8775 | 0.0330 | 1.938 | NO | **NO** |
| AR(1) | yes (OU substitute for continuous series) | 0.8942 | 0.0638 | 0.740 | NO | **NO** |
| Poisson | N/A | — | — | — | — | — |
| latent-variable | DEFERRED — Phase III §Step 14 follow-up | — | — | — | — | — |

### 5.1 Interpretation of the nulls

- **Shuffled** rejects strongly (z ≈ 18). γ is not a product of the
  marginal distribution alone; temporal structure matters.
- **AR(1)** reproduces γ ≈ 0.89 on surrogates with matched
  autoregressive parameter. Observed γ = 0.94 is within 1σ.
  **A mean-reverting linear AR(1) process matching INDPRO's own
  autocorrelation reproduces the aperiodic slope.** This is the
  expected behaviour per Touboul-Destexhe 2010 (PLOS ONE) and
  exactly why AR(1)/OU is the required null.
- **IAAFT** reproduces γ ≈ 0.88 on surrogates that preserve the
  amplitude spectrum and randomise phases. Observed γ is within
  ~2σ. This indicates γ is primarily encoded in the **linear
  amplitude spectrum**, not in nonlinear phase structure.

### 5.2 Verdict

**Two of three tested null families — AR(1) and IAAFT — reproduce
the observed γ.** Per `NULL_MODEL_HIERARCHY.md §6`, this blocks
promotion to the evidential lane for this substrate under this
method. The claim stays at `hypothesized`. The substrate's entry
in `docs/SUBSTRATE_MEASUREMENT_TABLE.yaml` is unchanged.

## 6. What this result does NOT license

Per `docs/CLAIM_BOUNDARY.md §3.1` scope qualifiers:

- **Does NOT license** any claim that INDPRO exhibits critical
  dynamics — an AR(1) mean-reverting process with matched
  autocorrelation produces the same γ.
- **Does NOT license** any claim about `market_macro` substrate
  class being a cross-substrate γ-convergence contributor.
- **Does NOT license** any statement that γ ≈ 0.94 on INDPRO is
  "near 1.0 as predicted" — the value is indistinguishable from
  a null dynamics, so its proximity to 1.0 is uninformative.
- **Does NOT replace** the primary specparam/IRASA measurement
  scheduled as the follow-up upgrade.
- **Does NOT cover** the other FRED series (T10Y2Y, SP500, VXVCLS,
  ICNSA) — each requires its own replication run. This report is
  about INDPRO only.

## 7. What this result DOES confirm

- The FRED fetch + γ-fit + null-comparison pipeline works
  end-to-end on real public-domain data with no synthetic
  intermediate.
- The AR(1) null can and does catch a bounded-secondary method
  producing a γ value that would otherwise be tempting to
  interpret as evidence. This is the null hierarchy doing its job.
- The infrastructure (fetch, fit, surrogates, report, registry)
  is in place for the remaining Tier-1 FRED series.

## 8. Next steps

1. **Specparam / IRASA upgrade** — re-run INDPRO with the primary
   aperiodic method and compare γ. Is the AR(1)-non-separability
   a method artefact or substrate-genuine?
2. **Remaining FRED series** — T10Y2Y, SP500, VXVCLS, ICNSA. Same
   pipeline. Each an independent replication.
3. **OU surrogate with empirically-matched τ** (§NULL_MODEL_HIERARCHY.md
   §2.3) — tighter than AR(1) for continuous-like series.
4. **Latent-variable surrogate** (§NULL_MODEL_HIERARCHY.md §2.5) —
   the primary threat model. Requires a preregistered latent
   model for FRED, e.g., slow cyclical component via
   Gaussian-process state-space.
5. **File OSF prereg per PREREG_TEMPLATE_GAMMA.md** — this
   retroactively turns the current run into a Phase III §Step 9
   pilot; subsequent runs will be fully prereg'd.

## 9. Replication instructions

To reproduce from a fresh checkout:

```bash
# Fetch (curl works reliably in most sandboxes)
mkdir -p evidence/replications/fred_indpro
curl -sf --max-time 60 \
  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDPRO" \
  -o evidence/replications/fred_indpro/INDPRO.csv

# Fit + null comparison
python run_fred_indpro_replication.py
```

Expected output: `evidence/replications/fred_indpro/result.json`
with `γ ≈ 0.94`, `claim_status = hypothesized`, and the three null
z-scores ≈ {18, 2, 1} (shuffled, IAAFT, AR1).

Determinism: seed = 42. Same seed + same INDPRO bytes → identical
result to within floating-point tolerance.

## 10. Changelog

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-04-14 | Initial FRED INDPRO γ-replication. Claim remains `hypothesized` due to AR(1) and IAAFT non-separability. |

---

**claim_status:** measured (about this replication report; the γ-claim it contains is `hypothesized`)
**result_json:** `evidence/replications/fred_indpro/result.json`
**raw_csv:** `evidence/replications/fred_indpro/INDPRO.csv`
**substrate_table_entry:** `fred_indpro` in `docs/SUBSTRATE_MEASUREMENT_TABLE.yaml`
