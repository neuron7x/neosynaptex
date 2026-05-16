# DOPA-CLOSURE — Global Gap Audit (cognitive · critical · logical · physical · informatic · auditor)

Adversarial self-audit with computation. Scope: #198, #199, RETRACTION.md, and
the retraction itself. Severity: **BLOCKER** (voids any conclusion) /
**MAJOR** (confound or process defect) / **MINOR**.

## Overall verdict

**INADMISSIBLE INSTRUMENT.** ≥3 independent BLOCKER-class defects. DOPA-CLOSURE
remains **UNTESTED**. The retraction was correct in direction but itself
contained an error (G-08). This audit corrects the correction.

## A. Gaps the user already named — all upheld

Construct substitutions (DNCA→sklearn, Verified Closure→accuracy,
hallucination→binary cls, sign-flip→|vRPE|-complement, vRPE not truth-correlated,
no real dopamine infra), verifier below majority baseline mislabelled
"limitation", no significance test, full run not CI-reproducible, SSOT drift,
oversold "closure complete", theory buried by testing a doll. Confirmed, not
re-litigated.

## B. New gaps found by this audit (beyond the user's list)

**G-01 BLOCKER · logical — the negative control is mathematically unconstructable.**
The gate is `|vRPE| ≥ τ`. A genuine sign-flip control feeds `−vRPE`; but
`|−vRPE| ≡ |vRPE|`, so a true sign-flipped control is the *identity* of `dopa`
(a no-op). Predicate condition 4 ("advantage gone under inverted vRPE") tests a
property the design cannot express. The implemented `|vRPE| < τ` is a different
operator (low-surprise routing), not a negative control. The control leg was
void from the contract, independent of construct validity.

**G-02 BLOCKER · critical — the substrate is at chance.**
Measured (seed 42, N=188): `cheap_wrong = 0.505`. The base predictor is a coin
flip; all policies live at 0.49–0.53 vs the 0.66 majority baseline. No routing
policy is evaluable on a chance-level substrate — the dynamic range *is* noise.

**G-03 BLOCKER · construct — proxy carries no theory content** (user's core point,
quantified): even granting the proxy, the gated verification action's *total*
net effect = +6/188 ≈ 3.2% (ensemble fixes 9, breaks 3), while the instrument
sits ~16 points below majority. A 3% lever under a 16-point deficit cannot
adjudicate the theory.

**G-04 MAJOR · physical/accounting — "equal budget" is not conserved.**
`dopa` pays an unconditional +1 probe per item (188 calls) that buys its routing
signal; budget-matched baselines pay no probe and convert the same cap into pure
extra K-verifies (≈ more verified items than `dopa`). The probe is an unmodelled
tax. The comparison is confounded **bidirectionally** — it does not cleanly
favour or disfavour `dopa`; "dopa spends ≥ and still loses" was a false comfort.

**G-05 MAJOR · informatic/process — the config file is theatre.**
`death_test.yaml` is never read by the module; constants are hardcoded
duplicates. `config_hash` hashes the module's own dict, not the yaml. "Frozen
by config / pinned by hash" is partially decorative; yaml can silently diverge.

**G-06 MAJOR · auditor — reproducibility scope is narrower than presented.**
The only CI-reproducible artifact is the 50-row smoke fixture, derived from
git-ignored data. CI proves *determinism of a toy*, not the conclusion.
`repro_hash` protects a number; nothing protects the inference.

**G-07 MINOR · informatic — vRPE is weakly, not null, truth-associated.**
Measured: point-biserial `|vRPE|` vs cheap-wrong = 0.183; vs ensemble-fixable =
0.307. So "vRPE not truth-correlated" is too strong: it is *weakly* correlated.
Precondition must be restated as a **quantified** bar (e.g. routed-action net
gain must exceed the majority-baseline deficit), not a binary "correlated?".

**G-08 BLOCKER · cognitive — the retraction mislocated its own error.**
RETRACTION.md said Δ was "within noise, no significance test". Computed:
Wilcoxon signed-rank p = 0.0156, paired-t p = 0.0063, 0/10 seeds dopa>unc — the
proxy result is **statistically significant** that `dopa < uncertainty_only`.
The failure was never "noise"; it was a *confident, significant, epistemically
void* number from an invalid instrument — a worse failure mode than noise,
because significance launders construct-invalidity into false authority. My
correction under-described the disease.

## C. Cross-axis meta-finding

The recurring generator across #198, #199 and the retraction: under completion
pressure a tractable proxy was substituted for the intractable named object,
then green CI / significance / hashes were used as authority transfer. The
instrument's confidence is inversely related to its validity. Any future
DOPA-CLOSURE work must gate on **construct validity before any number is
computed**, and must treat a significant result from an unvalidated instrument
as a red flag, not evidence.

## D. Preconditions for an admissible test (supersedes RETRACTION §"valid test")

Unchanged 1–7 of RETRACTION.md, plus:
8. The negative control must be a *constructable* operator under the actual gate
   (an absolute-value gate cannot host a sign-flip control — redesign the gate
   or the control).
9. The base verifier must clear the majority-class baseline *before* any routing
   policy is compared (G-02).
10. Budget must be a conserved quantity with the probe tax modelled on all arms
    (G-04).
11. The run config must be single-source and actually read at runtime (G-05).
12. Reproducibility must cover data ingestion → conclusion, not a toy fixture
    (G-06).
