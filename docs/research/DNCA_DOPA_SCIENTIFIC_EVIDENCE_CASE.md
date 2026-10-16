# DNCA × DOPA-CLOSURE: Scientific and Engineering Evidence Case

**Document ID:** NEUROMOD-EVIDENCE-CASE-2026-10-16  
**Class:** theoretical rationale + static implementation audit + preregistration blueprint  
**Repository:** `neuron7x/neosynaptex`  
**Code boundary:** `core/eai/dnca_modulated_router.py`  
**State:** **EXPERIMENTAL / NOT EMPIRICALLY VALIDATED**  
**Normative verdict:** implementation is *structurally motivated*, not *experimentally proved*.  
**CI:** unverified for this change. Local pytest/ruff/mypy have not been run by the author of this document.

> Research question: can dynamic control of claim-verification priority by bounded,
> neuromodulator-inspired prediction-error, salience and inhibition signals improve
> independently **verified** outcomes per unit of **total** computational cost,
> without increasing erroneous closure, compared with strong non-neuromodulatory
> policies? The null hypothesis is that it cannot.

## 0. Epistemic classification and non-goals

Four different kinds of statements must never be conflated:

| Label | Permitted assertion | Does not establish |
|---|---|---|
| **LITERATURE** | A cited article reports a biological observation or computational model | Validity of this software mapping |
| **SOURCE-OBSERVED** | A precisely identified routine or test exists in the reviewed repository | Its execution, correctness or empirical advantage |
| **DERIVED** | A conditional mathematical implication follows from declared definitions | Satisfaction of its assumptions in deployment |
| **HYPOTHESIS** | A falsifiable quantitative expectation with a measurement protocol | A positive experimental finding |

No claim of biological reproduction, general intelligence, drug action in digital systems,
clinical relevance, calibrated dopamine levels, productivity gain, or discovery of a
novel law is licensed. The psilocybin-related part of the previous conceptual proposal
is **not implemented** by the present routing bridge.

The authoritative historical result is `evidence/dopa_closure/RETRACTION.md`:
a previous proxy-based DOPA-CLOSURE experiment had inadequate construct validity.
The *theory remains UNTESTED*. No historical `KILLED` or `PASSED` proxy artifact
is promoted as evidence for this runtime.

## 1. Justification chain: biology → model → software → testable consequence

### J1 — Reward prediction error, not a truth oracle

**Biological evidence:** Schultz, Dayan & Montague (1997) reported a relationship
between dopaminergic activity and discrepancies between expected and received reward
[1]. The established RL mathematical construct is a TD error,
`δ_t = r_t + γ V(s_{t+1}) - V(s_t)` [2].

**Transfer:** the DNCA `DopamineOperator` produces a signed value-like error
and a separately asymmetrically-gained dopamine-like signal. Using a signed signal
to perturb verification *priority* is an implementable analogue of adaptive
salience allocation, **not** an estimate of whether a text claim is true.
For a reward-prediction interpretation, the value function must have meaningful
training and reward semantics. The existing value net is not demonstrated to
predict downstream verification utility.

**Falsifier:** after fixing equal total compute and independently testing verifier
reliability, a held-out evaluation finds no positive gain over uncertainty-only
and other competitive baseline allocators.

**Boundary:** reward prediction, discrepancy of sensory states, and truthfulness
verification are three *different* constructs. Never use their numerical similarity
to substitute one for another.

### J2 — Meta-learning controls, not one-transmitter/one-function identity

**Computational theory:** Doya (2002) proposed roles for dopamine, serotonin,
noradrenaline and acetylcholine as regulators of learning-related meta-parameters
[3]. Daw, Kakade & Dayan (2002) investigated possible opponent DA/5-HT
computational interactions; crucially, several interpretations were explicitly
theoretical or speculative [4].

**Transfer:** DNCA exposes DA-like value signaling and 5-HT-inspired inhibition.
The bridge enforces `inhibition_signal >= threshold` before considering priority
or risk pathways, producing `QUARANTINE` and not an evidence verdict. This is a
design decision representing a brake, **not** a complete biological model of
serotonin; real 5-HT functions are receptor-, circuit- and context-dependent.

**Falsifier:** inhibition gating increases erroneous closure, fails to prevent
unwarranted routing under perturbations, or adds prohibitive opportunity cost
at equal risk. In the present bridge, where no closure occurs at all, correctness
can only be evaluated as *routing behavior*, not protective effect on truth.

### J3 — Plasticity and exploration are separable hypotheses

**Theory:** Carhart-Harris & Friston's REBUS (2019) hypothesizes relaxation of
high-level prior precision under psychedelics [5]. Gerstner et al. (2018)
review experimental support for eligibility traces and a third factor in
synaptic learning [6].

**Transfer:** these motivate *future* adjustable prior precision, exploration
breadth and learning gates, but **no verified REBUS operator is included** in
`dnca_modulated_router.py`. BN-Syn offers candidate lower-level plasticity
machinery in a separate substrate. It is not evidence that a digital drug-like
mode has been simulated.

**Falsifier:** exploration control fails to increase verified *novel* solutions
at matched cost or systematically worsens calibration and false acceptance.

### J4 — Resource rationality independently motivates verification budgeting

**Decision-theoretic foundation:** Horvitz (1987) analyzed reasoning under
hard computational-resource constraints [7]. Sutton & Barto (2018) provide
the standard formal basis for reward-based adaptive policies [2].

**Transfer:** choosing which claim to verify is a metareasoning/resource-allocation
decision. The real purpose of the priority function is to allocate a scarce
verification budget; a neural interpretation is *optional*. This yields a
strong test: does it beat well-designed **non-neural** uncertainty/expected-value
allocators?

**Falsifier:** an uncertainty-only, expected-benefit-per-cost or random baseline
achieves at least the same independent verified closure for no more total cost.

### J5 — Assurance and claim boundaries

NIST AI RMF 1.0 provides a risk-management rationale for validity, reliability
and rigorous measurement [8]; NIST SSDF 1.1 provides secure-development process
guidance [9]. Neither document certifies this implementation. Claim status,
reproducible evidence, signed/verifiable artifacts, independent tests and
explicit residual-risk recording are local requirements, not badges acquired
merely by citing a standard.

## 2. Exact current computational semantics (implementation, not metaphor)

For each claim `i` and DNCA observation at time `t` define:

- `e_t = ||SPS.prediction_error||_2 >= 0`; normalized
  `x_t = e_t/(1 + e_t) ∈ [0,1)` for finite `e_t`.
  This is *state-prediction residual magnitude*, **not** a calibrated RPE
  or probability of claim falsehood.
- `v_t ∈ [-1,1]`: detached signed DNCA `valence`. Untrained-value risk applies.
- `h_t ∈ [0,1]`: detached `inhibition_signal`.
- `z_i = (x_t, u_i, n_i, r_i, 1-a_i)`, where `u` is uncertainty,
  `n` novelty, `r` evidence risk, `a` action reversibility; each is in `[0,1]`.
- `ℓ_i ∈ [0,1]`: declared load and `ρ_t = remaining/envelope` if envelope positive,
  otherwise zero.
- `w_j`: immutable-for-the-run weights from
  `configs/dopa_closure_v2/allocator.yaml`.
- `c` and `s`: load center and spread from the same config, with `s>0`.
- `g ∈ [0,0.25]`: bounded **experimental** signed-valence gain; `g=0`
  is its ablation, not an ablation of *all* neural factors.
- `θ_h ∈ [0,1]`: inhibition threshold.

The actual code calculates the baseline as

`k(ℓ) = max(0, 1 - ((ℓ-c)/(s+10^-9))²)`,

`b_i = max(0, [w·z_i + 0.35(1-ρ_t)x_t] k(ℓ_i))`,

and then the perturbed routing priority

`q_i(g) = max(0, b_i + g v_t)`.

**Important:** `q_i` is a ranking score, **not** a probability.
There is no general code-level upper clamp `q_i <= 1`.
Do not report `q_i` as calibrated confidence.

Priority classification follows the existing config thresholds, *except*
that `h_t >= θ_h` immediately forces `QUARANTINE`; otherwise high evidence
risk may select `REJECT`, then priority selects `ESCALATE`, `VERIFY`,
`CHEAP_TRIAGE` or `QUARANTINE`. The return value is a reservation/queue only.
The local verifier is **not executed** by this integration module.

The budget snapshot is produced by `BudgetLedger`: it records a reserved cost
for each proposed action, including the configured probe tax and retry penalty.
`ledger.apply()` limits withdrawal to available funds on an overspend,
then selects the quarantine mode. This is a *resource-accounting contract*,
not a measurement of actual CPU, token, memory, human or network cost.

## 3. Conditional propositions and narrow proofs

**P1: No self-certified truth promotion (bridge boundary only).**
Assume execution enters `route_observation` and returns `Ok`.
Every route dictionary constructed within its loop fixes
`verification_result = "not_run"`. Its top-level result fixes
`closure_count = 0` and status `ROUTING_ONLY` (or an inadmissible
zero-route record). No assignment path emits `CLOSED` or `VERIFIED`.
Therefore **the new bridge cannot report verified closure on its own**.

**Scope limitation:** this proposition does **not** apply to the separate,
older `run_allocator_full_path` method, which currently derives a
`"pass"` and `FinalStatus.CLOSED` from an `evidence_risk` threshold without
calling an independent verifier. That is an **unresolved critical semantic
hazard**, not evidence of real closure. Do not deploy the legacy pathway as
an external truth verifier.

**P2: Nonnegative budget under specified preconditions.**
Assume `B_0>=0`; all configured action costs and probe taxes nonnegative;
`lambda_penalty` finite; no concurrent unmediated mutation of
`BudgetLedger.remaining`. At each `apply`, requested debit is
nonnegative. If it exceeds remaining, the alternative debit is
`min(remaining, quarantine_cost + probe_tax)`, bounded above by
`remaining`. Thus `0 <= B_{t+1} <= B_t`.
`spent = B_0 - B_t` implies `spent + remaining = B_0` by definition,
subject to numerical quantization. The implementation's Boolean
`conserved` is an *accounting invariant check*, not proof that
verification computation actually consumed exactly those resources.

**P3: Signed modulation is meaningful but clipped.**
For fixed `b_i >=0` and positive `g`, compare
`q_i(g,v) = max(0,b_i+gv)` and `q_i(g,-v)`.
Their difference is nonzero for many nonzero `v`, but it *may vanish*
if both values clip to zero or if `v=0`. Hence the true sign-flip control
is mathematically expressible, **not guaranteed** to change every route.
A gate defined solely on `|v|` would not support this control, since
`|-v|=|v|`. Random and permuted controls are additional, not equivalent.

**P4: Suppression dominates motivation at the implemented boundary.**
Given admissible input and `h_t >= θ_h`, the control-flow first branch
assigns `QUARANTINE` independently of `q_i`. This proves an explicit
precedence relation in code; it does **not** prove the threshold is
biologically or economically optimal. Note: this precedence also overrides
the separate evidence-risk `REJECT` path, producing a quarantined instead
of rejected reservation. Treat this as a policy choice requiring audit.

**P5: Live-instance type checking is not cryptographic provenance.**
`route_live_dnca` checks an instance of `DNCA` and its positive SPS step,
whereas `route_observation` labels a detached snapshot projection untrusted.
Neither binds observations to input hashes, model weights or immutable
telemetry; a mutable DNCA instance can be altered upstream. Thus the current
implementation guarantees *interface shape*, not tamper-proof experimental
provenance.

## 4. Static code-to-claim traceability matrix

| Claim | Code path | Test/source path | Current license |
|---|---|---|---|
| Signed DA affects priority, never truth | `core/eai/dnca_modulated_router.py::route_observation` | `tests/dopa_closure_v2/test_dnca_modulated_router.py::test_modulation_is_sign_sensitive_and_budget_matched` | Source-observed; runtime unverified |
| Inhibition can force quarantine | `route_observation`, first decision branch | `test_inhibition_forces_hold_without_promoting_truth` | Source-observed; runtime unverified |
| Live DNCA must be executed | `route_live_dnca` + `observe_sps` | `test_executed_dnca_runtime_projects_to_routing_only` | Test exists; execution unverified |
| Negative/NaN/malformed inputs rejected | `_scalar` and `observe_sps` | `test_invalid_gain_fails_closed` and `test_sps_projection_rejects_missing_nonfinite_and_unrun` | Source-observed; runtime unverified |
| Construct gate blocks inadmissible routing | `dopa_construct_gate.py` + `route_observation` | `test_failed_construct_gates_produce_no_routes_or_spend` | Logical guard; attestation not independently proven |
| Budget never goes negative | `core/eai/dopa_budget.py` | `test_budget_conserved_under_scarcity` | Conditional derivation; runtime unverified |
| Independent claim verification | **NO VERIFIER INVOCATION** in this bridge | None | **NOT IMPLEMENTED** |
| Benefit over baseline | No accepted held-out experiment | Historical retraction + construct gap audit | **NOT TESTED** |
| REBUS-like prior relaxation in router | No explicit prior-precision operator | None | **NOT IMPLEMENTED** |

Existing tests are proposed checks, not published result data. This document
was prepared from source inspection, not a successful CI run.

> **Post-hardening amendment (2026-10-16):** The earlier review below records
> vulnerabilities in the *pre-hardening* implementation. H1 removes
> threshold-only `CLOSED`, makes no-verifier instrument results
> `INADMISSIBLE`, guards budget/path/config boundaries, and renames pending
> artifacts. See [H1 Hardening Act](DNCA_DOPA_HARDENING_ACT_2026-10-16.md).
> Historic findings are retained for provenance and must not be interpreted as
> still-active code paths. Remaining blockers: independently validated signal,
> actual external verification, evidence-backed construct attestations, and
> end-to-end metered, reproducible tests.

## 5. Construct-validity blockers and attack surface

**B0 / blocker — weak reward-value semantics.** `DopamineOperator.value_net`
is not shown to generalize from independently identified verification utility.
An untrained prediction-error signal can be numerically nonzero but have
zero useful relation to truth-verification benefit. The older
`docs/experiments/DOPA_VALIDITY_001_REPO_AUDIT.md` already identifies this.

**B1 / blocker — self-attested gate flags.** `ConstructContext` accepts booleans
(or callables) and a caller can pass every expected flag. This validates
*declared premises*, not the underlying presence or quality of a real
verifier, dataset or baseline. Replace booleans with evidenced,
signature/hash-bound, independently executed condition checks before a
real experiment.

**B2 / blocker — legacy false closure.** `core/eai/dopa_closure_v2.py`'s
`run_allocator_full_path` has `evidence_risk <= close_evidence_risk_max` as
a condition that can synthesize `"pass"` and `CLOSED` without independent
verification. Do not use that method as a truth certification endpoint.
The new bridge deliberately avoids it. Remediation is separate and
potentially API-breaking.

**B3 / major — accounting ≠ realized cost.** The current ledger counts nominal
reservations; it omits actual DNCA forward passes, model initialization,
retry overhead, verifier CPU/GPU, network and data preparation costs. Total
budget matching must meter all arms at the same measurement boundary.

**B4 / major — signal calibration.** SPS sensory-error norm, signed valence,
and external evidence-risk proxies differ in statistical meaning. A score
can rank tasks without representing posterior confidence or usefulness.
Predeclare calibration targets and evaluate against withheld labels.

**B5 / major — causality.** Positive observed correlation between gain and VCR
does not establish a causal mechanism without randomization, matching,
negative controls and exclusion of shortcut predictors/data leakage.

**B6 / major — missing generator-level factor.** The present code adjusts
verification routing. It does not implement REBUS-like prior relaxation,
generator exploration breadth or controllable goal persistence. A
four-arm exploration × pursuit experiment requires an additional explicit
generator interface. **Do not mislabel DA gain as the complete 2×2 design.**

**B7 / process — unexecuted tests.** The previous PR was merged while Actions
were failing. There is no successful archived local run proving the bridge.
An approval/merge event is a change-management result, not a validation result.

## 6. Falsifiable empirical plan

**Primary hypothesis H1:** given the same fixed claim set, independently
qualified verifier, hidden ground truth, replayed DNCA state, total
end-to-end measured compute budget and frozen acceptance gates, signed
neuromodulator-informed allocation produces higher *verified closure per
total cost* than the strongest of
`uncertainty_only`, `random_cost_matched` and
`expected_verification_gain_per_cost`.

**Null H0:** there is no practically meaningful improvement.

### Outcome and costs

For `N` preregistered distinct claims, define

`VCR = (# of claims independently verified with evidence-bound audit artifacts)/N`.

This is not ordinary classifier accuracy. Define

`FCR = (# of accepted claims independently shown false)/(# of accepted claims)`,
with `FCR` undefined rather than silently zero if no claims are accepted.

Let `C_total` be metered actual inference tokens/compute, probes, verification,
preparation and retries at the same boundary across arms. Define

`U = verified_true_closures / max(C_total, ε)`,

where `ε>0` is a declared numerical guard. Report `VCR`, `FCR`,
latency, abstention rate and `C_total` separately; `U` alone can hide errors.

### Pre-registered protocol

1. Freeze one benchmark with an independent, auditable oracle (held-out
   claims and immutable answer evidence); split development from final test.
2. Establish the actual verifier's reliability against majority/random and
   strong learned baselines **before** studying routing.
3. Establish whether signed DNCA valence forecasts *incremental independent
   verification benefit* across seeds, rather than merely claim classes.
4. Freeze DNCA checkpoints, pretrained/fitted value model, seeds, config,
   source SHA, data manifest SHA-256, allowed tools and verifier version.
5. Run randomized paired task blocks for `g=0`, positive `g`, sign-flipped
   `v`, permutation control, random and utility/cost comparator. Measure
   signal-generation cost in every relevant arm; exclude no overhead.
6. Produce per-claim provenance: input hash, DNCA snapshot hash, queue
   decision, actual verification action, verifier independent output,
   timestamps, cost and evidence hash. Only a separate verifier may close.
7. Specify beforehand a minimum practically meaningful improvement
   `Δ_min`, maximum acceptable `FCR`, effect-size statistic, confidence
   interval and family-wise multiple-comparison control if testing many arms.
8. Use paired confidence intervals across tasks with a hierarchical treatment
   of seeds/task clusters. Do not treat multiple runs of the same claim as
   independent observations. Include negative/null findings.
9. Reject a positive claim if signal-validity, verifier-validity, equal-budget,
   reproducibility or false-closure gates fail, **even if a p-value is small**.
10. Evaluate REBUS-like exploration/pursuit as a **separate future 2×2 factor**
    only after the missing generator-level control is implemented and ablated.

A default sample size cannot be asserted without an effect-size and
power/precision analysis. Fix it in the preregistration *before* accessing
held-out outcomes, not by retrofitting thresholds after inspection.

### Explicit negative controls

- **DA ablation:** gain `g=0`.
- **Signed inversion:** `v -> -v`; retain signed operator and check actual
  separation, avoiding an absolute-value no-op.
- **Permutation:** shuffle routing signal between claims within cost-matched
  blocks; ensure no label leakage.
- **Spurious-confidence stress:** perturb confidence/novelty while holding
  truth and verifier results constant.
- **Resource pressure:** test low budgets, high inhibition, saturation and
  malformed SPS inputs; verify no false closure or overspend.
- **No-neural comparator:** expected verification benefit per cost, with the
  same verifier, data and execution accounting.

### Promotion criteria

- **STRUCTURAL_READY:** source and boundary invariants reviewed, tests locally
  execute, independent static analysis passes; no empirical performance claim.
- **INSTRUMENT_ADMISSIBLE:** independent verifier qualified; real signal
  semantics calibrated; all costs metered; construct and provenance gates pass.
- **EMPIRICALLY_SUPPORTED (scoped):** held-out paired benefit exceeds
  preregistered practical threshold with appropriate uncertainty and
  `FCR` constraint, robust to the negative controls and external replication.
- **KILLED (scoped):** admissible instrument and sufficiently informative
  experiment falsify the exact prespecified benefit claim.
- **UNTESTED / INADMISSIBLE:** missing any prerequisite; neither support nor kill.

## 7. Practical offline reproducibility

Run from repository root (external CI failure is not waived as proof):

```bash
python -m pip install -e '.[dev]' -e agents
python -m pytest -q tests/dopa_closure_v2/test_dnca_modulated_router.py
python -m ruff check core/eai/dnca_modulated_router.py tests/dopa_closure_v2/test_dnca_modulated_router.py
python -m mypy core/eai/dnca_modulated_router.py
git rev-parse HEAD
git status --porcelain
```

Minimum evidence packet: exit codes, Python and Torch versions, environment
dependency lock/snapshot, CPU/GPU details, full output logs, exact command
line, SHA-256 for inputs/config/code and the raw non-redacted test report
(with secrets removed). Run under Python 3.10/3.12 compatibility if supported
by declared build requirements. Do not silently skip the real DNCA smoke;
a skip is an unverified dependency boundary, not a pass.

Targeted implementation improvements before any truth-capable deployment:
replace caller-supplied `ConstructContext` booleans with evidence-backed
checks; remove the legacy threshold-only closure path or require an external
verifier receipt; add actual measured cost and a persistent signed event
ledger; freeze datasets and DNCA checkpoints; quantify signal validity.

## 8. References (verified primary literature / authoritative standards)

[1] Schultz W, Dayan P, Montague PR. **A Neural Substrate of Prediction and
Reward.** *Science* 275(5306), 1593–1599 (1997).
DOI: https://doi.org/10.1126/science.275.5306.1593

[2] Sutton RS, Barto AG. **Reinforcement Learning: An Introduction**, 2nd ed.
MIT Press (2018). https://mitpress.mit.edu/9780262352703/reinforcement-learning/

[3] Doya K. **Metalearning and neuromodulation.** *Neural Networks*
15(4–6), 495–506 (2002).
DOI: https://doi.org/10.1016/S0893-6080(02)00044-8

[4] Daw ND, Kakade S, Dayan P. **Opponent interactions between serotonin
and dopamine.** *Neural Networks* 15(4–6), 603–616 (2002).
DOI: https://doi.org/10.1016/S0893-6080(02)00052-7

[5] Carhart-Harris RL, Friston KJ. **REBUS and the Anarchic Brain:
Toward a Unified Model of the Brain Action of Psychedelics.**
*Pharmacological Reviews* 71(3), 316–344 (2019).
DOI: https://doi.org/10.1124/pr.118.017160

[6] Gerstner W, Lehmann M, Liakoni V, Corneil D, Brea J.
**Eligibility Traces and Plasticity on Behavioral Time Scales:
Experimental Support of NeoHebbian Three-Factor Learning Rules.**
*Frontiers in Neural Circuits* 12:53 (2018).
DOI: https://doi.org/10.3389/fncir.2018.00053

[7] Horvitz EJ. **Reasoning about Beliefs and Actions under
Computational Resource Constraints.** Third Workshop on UAI,
429–444 (1987).
https://www.erichorvitz.com/u87.htm

[8] Tabassi E. **Artificial Intelligence Risk Management Framework
(AI RMF 1.0).** NIST AI 100-1 (2023).
DOI: https://doi.org/10.6028/NIST.AI.100-1

[9] Souppaya M, Scarfone K, Dodson D. **Secure Software Development
Framework (SSDF) Version 1.1.** NIST SP 800-218 (2022).
https://csrc.nist.gov/pubs/sp/800/218/final

## 9. Final scientific verdict

The integrated DNCA/DOPA bridge is a **legible and testable computational
instantiation** of neuromodulator-inspired *verification prioritization*.
It has plausible theoretical ancestors, source-visible control flow and
explicit epistemic boundaries. Its effectiveness is **unknown**.
The critical unclosed gaps are **signal construct validity, real independent
verification, truthful closure semantics, total-cost matching, trustworthy
evidence provenance and successful reproducible test execution**.

**Claim permitted:** "An experimental, bounded DNCA → DOPA verification-routing
bridge has been implemented and merged."

**Claim forbidden:** "Neuromodulation has been shown to improve the factual
accuracy, autonomy or verified cognitive intelligence of LLM agents."
