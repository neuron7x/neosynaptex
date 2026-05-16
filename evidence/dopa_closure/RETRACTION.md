# RETRACTION — DOPA-CLOSURE death-test (#198, #199)

**Authoritative status. Supersedes every other DOPA-CLOSURE artifact in this repo.**

## Verdict

**INVALID INSTRUMENT. The theory DOPA-CLOSURE is UNTESTED.**

`KILL-0979.json`, `kill_artifact.json`, `death_test_result.json`,
`DOPA_CLOSURE_MINIMAL_VERDICT.md`, `audit_verdict.json` and the prior
"two orthogonal benchmarks agree: KILLED" claim are **retracted as
falsifications**. They tested a proxy, not the theory. A KILL produced by an
instrument with no construct validity is itself a false promotion — the exact
failure class DOPA-CLOSURE was meant to prevent.

## Why the instrument is invalid (construct-validity breaks)

| claimed object | what was actually tested |
|---|---|
| DNCA / real dopamine infrastructure | sklearn TF-IDF + logistic regression |
| Verified Closure Rate | plain classification accuracy |
| hallucination / truthfulness | binary SUPPORT/CONTRADICT classification |
| inverted-sign vRPE negative control | complement of `|vRPE|` threshold (different function) |
| informative vRPE signal | vRPE never shown truth-correlated |

Additional invalidators:

- The verifier scores **below the 0.66 majority-class baseline** → an
  **admissibility blocker**, not a "limitation". It was knowingly softened in
  prose. That deescalation is itself a flagged failure.
- Δ(dopa − no_vRPE) ≈ −0.007 over 10 seeds: **no significance test**. The
  difference is within noise; it was reported as a verdict.
- The full-data result is **not CI-reproducible**: the dataset is git-ignored;
  only a 50-row fixture is reproducible. The repro hash protects a number, not
  the conclusion.
- config/code SSOT drift: constants duplicated across `death_test.yaml` and the
  module.

## What would make a valid test (preconditions, all required, pre-registered first)

1. Routing driven by the **actual DNCA/dopamine** modulator, not a proxy.
2. A real hallucination/truthfulness task with a **Verified Closure** definition
   distinct from accuracy.
3. A vRPE estimator **independently shown truth-correlated** before any gate.
4. A verification action **independently shown above majority-class** on the
   target benchmark.
5. A true sign-flip negative control (negated vRPE), not a threshold complement.
6. Significance testing on the budget-matched deltas.
7. A fully CI-reproducible end-to-end run (data ingestion included).

No gate rescues an uninformative verifier; no kill counts from an invalid
instrument. Until 1–7 hold, DOPA-CLOSURE remains **UNTESTED**, not killed.
