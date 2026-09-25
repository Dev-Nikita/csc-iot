# Submission plan — IEEE Transactions on Network and Service Management

Decided 2026-09-26. Primary venue **IEEE TNSM**, traditional (non-OA) route.
Working title, final after B5:

> Counterfactual Shadow Control: Risk-Calibrated Minimum-Intervention Recovery
> for Edge Services

TCC was the primary target for one day and is dropped. TNSM is not a fallback
dressed as a choice: the contribution is deciding whether and how to intervene
in a degrading distributed service and measuring whether the intervention
helped, which is network and service management. TCC is a cloud journal and
this is a single-host edge study, so TCC would have been an argument about
scope before anyone read the method.

## 1. Venue facts (checked against the journal's own policy page)

| | TNSM |
|---|---|
| Free pages | 10, two-column, including title, abstract, figures, tables, references, biographies and photographs |
| Overlength charge | US$220 per page beyond 10 |
| Hard maximum | 16 pages |
| Waiver | Academic authors with no funding source may apply, with evidence, within 30 days of acceptance |

Source: IEEE ComSoc, TNSM policies and guidelines.

**The paper is architected for a 10-page core** plus supplementary
reproducibility material. Submitting at 11-12 is allowed if the content earns
it, but no section is planned on the assumption that overlength pages will be
bought.

## 2. Risk, by dimension

Acceptance probabilities are deliberately absent from this file. Neither a
number like 0.57 nor its author can be held to account for a single editorial
decision, and writing one down manufactures precision that does not exist.
What can be assessed is where the work is exposed.

| Dimension | Risk | Why |
|---|---|---|
| Scope fit | **low** | TNSM's subject is reliability, quality assurance and performance evaluation of managed services. This is that. |
| Methodological validity | **low-medium** | The measurement is audited by seven accounting invariants on every branch and by unit tests on the objective. Three superseded runs and their defects are in the amendment log. Remaining exposure: replay is an empirical reference, not ground truth, and is described as such. |
| Reproducibility | **high potential** | Append-only artifacts with run identity, stack identity, git revision and config hash; the runner refuses a non-reportable stack. Needs the artifact packaged and a public URL before submission. |
| Experimental confounding | **high, being fixed** | Through 0.7 every branch carried one fault onset and one severity. Protocol 0.8-0.9 makes the scenario a factor and adds leakage tests. Until the pilot passes, no generalisation claim is available. |
| Implementation completeness | **high** | The controller does not exist yet: `intelligence/` is a CRC calibrator and its tests. Everything the title promises is still to be built. |
| Novelty | **medium** | AURORA already covers causal `do(a)` with an uncertainty gate and abstention. The separation is minimum-necessary intervention, conformal risk control on a set-level loss, and replay-verified post-hoc validation of the executed action. That separation has to be visible in the results, not only in the related-work section. |

## 3. Reduced-but-complete scope

The rule is unchanged: everything the paper claims is implemented, exercised and
measured, and nothing is described as a mechanism unless a run shows it choosing
something.

### In

| Element | Content |
|---|---|
| Actions | `NO_OP`, `REROUTE`, `THROTTLE`, `MIGRATE` — each with real state mutation and an acknowledged effect |
| Fault mechanisms | **D1** edge capacity degradation · **D2** ingress impairment ramp on the device-to-gateway path · **D3** edge stall (service rate to zero for k epochs) |
| Scenario factor | `(fault_type, onset, severity, workload, seed)` — see protocol §11a |
| Predictor | action-conditioned `Ĵ(s,a)`: structural queue model vs learned challenger, compared in three shift regimes |
| Uncertainty | bootstrap ensemble, K = 10, giving a set of plausible `Ĵ` per action, and a disagreement signal used by the gate |
| Safety gate | Conformal Risk Control on the declared set-level monotone loss, `δ` fixed in advance, yielding `τ̂` and `U_max` |
| Selector | Minimum-Necessary Intervention: cheapest admissible action, else guarded abstention outside the guarantee |
| Baselines | **B1** never intervene · **B2** reactive threshold after a violation · **B3** greedy predicted-best, no gate and no cost ordering · **B4** replay oracle, an upper bound labelled as not implementable online · **B5t** time-only predictor `f(t,a)`, kept as a leakage control |
| Ablations | **A1** remove the CRC gate · **A2** remove the cost ordering |
| Determinism audit | D0 on the frozen configuration |

### Out, and said so in the paper

`REPLICATE`; fault mechanisms beyond the three; multi-host, geo-distribution and
multi-tenancy; energy, RF and hardware measurement; mobility, and none is added
to chase a mobility venue; the resource and bandwidth components of the cost
term, which stays reduced and declared.

## 4. B5 is a challenger, not a verdict on the paper

An earlier version of this plan said that if the learned predictor failed to
beat the structural model, the framing would collapse. That was wrong, and it
was wrong in the direction that abandons viable work. All three outcomes are
publishable, and each names the final architecture:

| Outcome | Claim | Architecture |
|---|---|---|
| structural > learned | structural inductive bias improves intervention ranking under shift | predictor → SCM → ensemble → CRC → MNI |
| structural ≈ learned | with dense interventional branch data, explicit causal structure adds little | action-conditioned predictor → ensemble → CRC → MNI |
| learned > structural | the explicit structure introduced misspecification error | action-conditioned predictor → ensemble → CRC → MNI |

The retention rule is fixed **before** the B5 test set is inspected, on a
practically meaningful margin rather than a p-value, and is recorded in the
protocol. A reviewer will respect a reported tie far more than an SCM tuned
until it won.

### Three shift regimes

- **B5-ID** — train and test scenarios from the same declared distribution, new
  seeds, new onsets, new severities. Interpolation.
- **B5-parameter-shift** — train on the lower severity band, test on the upper;
  or train on early onsets, test on late. Extrapolation.
- **B5-mechanism-shift** — train on D1 and D2, test on D3 or a combined
  cascade. This is where a structural prior should pay off if it ever does. If
  it does not pay off here, that is strong evidence it is not needed.

Start the challenger simple: an action-conditioned MLP or gradient-boosted
model on the telemetry window. A temporal model is added only if history
demonstrably helps, because otherwise it is one more source of complexity to
defend.

## 5. Leakage tests are mandatory, not optional

| Test | Passes when |
|---|---|
| Feature schema | the feature set provably excludes `scenario_id`, `fault_type`, `fault_onset`, `fault_severity`, absolute anchor index, and any future schedule. Enforced in the extractor and unit-tested. |
| Permutation | telemetry shuffled between scenarios destroys performance. If it does not, the model is reading something other than telemetry. |
| Time-only baseline | `f(t,a)` is materially worse than the telemetry model. If time alone does nearly as well, the confound is still there. |

The time-only baseline is kept permanently even if it never enters a main
table. It is the cheapest available defence against the first question a
reviewer will ask.

## 6. Abstention must come from a signal, not from our knowledge of the design

In the spanning regime the fault has not happened at decision time. It is
tempting to say the correct behaviour is abstention and call that a result. It
is not, unless the abstention is produced by something the controller can
measure: ensemble disagreement, telemetry outside the calibration distribution,
a conformal set too wide to admit any action. Otherwise the claim reduces to
"the system correctly predicted unpredictability", which is not a claim at all.

The evaluation therefore separates two situations and reports them separately:

- **unknowable future event** — nothing in the observed state carries the
  coming fault. A low predicted risk here is correct, and the system may be
  surprised. CRC gives no protection against an event absent from the
  observations, and the paper says so.
- **uncertain current state** — the observations do carry signal, and the
  ensemble or the conformal width says the evidence is insufficient to justify
  a specific action. Abstention here is the mechanism working.

## 7. The workload factor changes the latency budget

The 750 ms budget was calibrated by the declared per-event rule on healthy
`NO_OP` branches at 100 events per epoch. The healthy per-event latency
distribution depends on offered load, so one budget across workload levels
would make `Y` measure the load rather than the failure — the same class of
error as calibrating on branch means, and as counting the denominator at the
edge. The budget is therefore calibrated **per declared workload level**, by
the same rule, on healthy `NO_OP` branches at that level, before any
comparative result at that level is examined.

## 8. Sequence

1. **Phase 1 — scenario parameterisation.** Fault type, onset, severity,
   workload and seed become scenario-level, recorded per branch as separate
   manifest fields. The scenario is fixed within a cell and across the actions
   compared at an anchor.
2. **Phase 2 — leakage tests**, all three, before any model is trained.
3. **Phase 3 — pilot on two or three scenarios**: early onset with moderate
   severity, late onset with strong severity, and if cheap an unseen workload.
   Checks replay accounting, branch identity, `η_J`, action effects, and that
   the extractor gives the model telemetry rather than timing. The pilot also
   measures per-branch cost, which sets the size of the full design.
4. **Phase 4 — B5** in the three shift regimes.
5. **Phase 5 — decision gate** applied as written.
6. **Phase 6 — controller**: ensemble, CRC, MNI, on whichever architecture
   phase 5 selects; then baselines, ablations and D0.
7. Results, abstract and conclusion written only from validated artifacts.

## 9. What m2prime-903 is, and is not

It is a **single-scenario audited replay study**: 900 branches, zero refusals,
an objective that passes seven accounting invariants on every branch, replay
dispersion `η_J = 0.0164`, and 33 of 60 action contrasts resolvable under every
band tested. It contains two results worth reporting: intervention in a healthy
system has no effect, with a bootstrap CI of [-0.000, +0.005] on the
`NO_OP`-`REROUTE` contrast; and the value of intervening decays with delay,
from 0.264 at anchor 10 to 0.174 at anchor 30 with non-overlapping intervals.

It is **not** evidence of generalisation, and will not be presented as any. One
onset, one severity, one workload.

## 10. What a reviewer will attack, and the answer

| Objection | Answer |
|---|---|
| Single host, so the scale claim is untested | Stated as a limitation, not defended. The claim is about the decision procedure and its measurement; the substrate is declared as containerised emulation with kernel netem. |
| Replay is not counterfactual ground truth | Never called that. Replay gives empirical reference outcomes on a reconstructed prefix, with the reconstruction verified by structural fingerprint and transport quiescence. |
| The predictor is reading the scenario | Three leakage tests, one of which is a permanently retained time-only baseline. |
| The objective is reduced | Declared in the text and in every table caption. |
| Effects are small relative to replay noise | Reported under four bands, with the set surviving all four named separately. |
| Results tuned to the conclusion | Three superseded runs, their defects and dated amendments are in the protocol, which ships with the artifact. Gates and margins are fixed before the data. |
| The SCM was kept because it is the paper's premise | The retention rule and its margin are recorded before the B5 test set is inspected, and a tie is reported as a tie. |
