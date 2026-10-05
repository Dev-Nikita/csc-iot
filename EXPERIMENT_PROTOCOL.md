# EXPERIMENT_PROTOCOL.md

Pre-registered protocol for CSC. **Everything in §2–§9 is frozen before the main experiments are run.** Changing a frozen value after seeing comparative results invalidates the run set; the correct response is a dated amendment in §12 plus a full re-run.

Protocol version: **0.15** (mechanisms D4 and D5, where rerouting is wrong, 2026-10-01). Becomes 1.0 at implementation freeze, after the pilot in §11.

---

## 1. Terminology

- **Failure event `F`**: an SLA violation window — end-to-end p99 latency above the SLA bound, or delivery success below the SLA bound, sustained for ≥ `f_dur`. Exact bounds: `experiments/configs/sla.yaml`.
- **Preventable failure**: a failure that occurred in the no-op replay branch from the same decision state. Only preventable failures enter the PFR denominator.
- **Harmful intervention**: an executed action whose replayed branch objective `J` is worse than the no-op branch objective from the same state, beyond the residual-nondeterminism band measured in §10.
- **Decision state**: a controller tick at which the risk of any candidate exceeds the evaluation trigger.
- **Replay-based empirical reference outcome**: the outcome observed when a candidate action is executed in its own reconstructed branch. **Not** "counterfactual ground truth" — the system is concurrent and residual nondeterminism remains, quantified as `η_J` in §10.
- **`η_J`**: the replay dispersion band. Two actions are distinguishable only if their observed objectives differ by more than `η_J`; otherwise they are **tied**.

### Notation (one symbol, one meaning)

| Symbol | Meaning |
|---|---|
| `δ` | conformal risk-control level (target `E[loss] ≤ δ`) |
| `τ`, `τ̂` | admissibility threshold on predicted risk; `τ̂` is calibrated, not hand-set |
| `U_max` | bound on predicted uncertainty width |
| `η_J` | replay dispersion band |
| `λ_F, λ_L, λ_C` | objective weights in `J` |
| `w_L, w_R, w_B, w_D` | cost-component weights in `C(a)` |

`α`, `β`, `γ` are retired. In protocol 0.1 `α` denoted both the conformal miscoverage level and the failure weight in `J`; that collision is fixed here.

## 2. Frozen constants

| Symbol | Meaning | Value | File |
|---|---|---|---|
| `Δ` | prediction horizon | selected on validation from {2 s, 5 s, 10 s}; frozen thereafter | `configs/model.yaml` |
| `H` | rollout steps | `Δ / tick`, derived | `configs/controller.yaml` |
| `τ̂` | admissibility threshold | **calibrated by CRC**, searched over a fixed grid | `configs/controller.yaml` |
| `δ` | risk-control level | 0.10 | `configs/calibration.yaml` |
| `U_max` | max admissible interval width | 0.25 | `configs/controller.yaml` |
| `w_L,w_R,w_B,w_D` | cost weights | 0.25 each | `configs/cost.yaml` |
| `λ_F,λ_L,λ_C` | objective weights | 0.6, 0.2, 0.2 | `configs/objective.yaml` |
| `η_J` | replay dispersion band | **measured by D0**, then frozen | `configs/runs.yaml` |
| `Δ_A` | availability non-inferiority margin | 0.005 | `configs/objective.yaml` |
| `n_seeds` | paired seeds per configuration | 20 (target 30) | `configs/runs.yaml` |
| run shape | warm-up / measurement / cooldown | 120 s / 300 s / 60 s | `configs/runs.yaml` |
| tick | controller decision period | 500 ms | `configs/controller.yaml` |
| telemetry | sampling period | 100 ms | `configs/telemetry.yaml` |
| `p95` budget | decision latency | 100 ms, miss rate < 1% | `configs/runs.yaml` |

Equal cost weights are fixed a priori as a **neutral default** — no mathematical conservatism follows from `w_i = 0.25`, and claiming it would be rhetoric. Sensitivity to alternative operational preferences (non-uniform weights) and to `δ ∈ {0.05, 0.10, 0.20}` goes in the supplement.

**`Δ_A = 0.005` — operational rationale.** Half a percentage point of availability is the largest reduction treated as practically negligible over the 300 s measurement window: at the declared SLA it corresponds to roughly one and a half seconds of additional unavailability per run, below the granularity at which the agreement is enforced. This is the pre-registered primary margin. A sensitivity analysis over `Δ_A ∈ {0.001, 0.0025, 0.005, 0.01}` is reported in the supplement; the primary claim is made at 0.005 only.

---

## 2a. Frozen testbed configuration

Frozen 2026-09-15 from the pilot series on reportable stack `afbcb298cb97ee18`
(NATS 2.14.6, kernel netem on the device simulator's device-network egress,
loss 5%, delay 20 ms ± 5 ms, seed 424242). Every value below was **derived from
measurement, not chosen**, and the derivation is stated so a reader can check
that it was not fitted to a desired comparison. No controller existed while
these were set: the pilots compared primitive actions only, so this is
instrument calibration and not result selection. **After this freeze none of
these values changes.** A change requires a dated §12 amendment and a full
re-run of everything that depended on it.

| Parameter | Value | How it was derived |
|---|---|---|
| Offered load | 100 events/epoch | Below `edge00` capacity, so the healthy system meets its agreement. At 200 the system was saturated from the first epoch: there was no healthy state and no failure to prevent. |
| Emission shape | paced over 200 ms | A burst gives every event of an epoch the same latency, so the violated fraction moved in steps of one whole batch and that step *was* the measured dispersion. Devices in a deployment do not emit simultaneously either. |
| `edge00 / edge01 / edge02` capacity | 150 / 300 / 200 per epoch | Unequal by construction. With equal capacity `REROUTE` moves work to an identical node and measures exactly zero effect however many branches are run. |
| Fault | `edge00` 150 → 60 at epoch 12 | Late enough that an anchor at `a ≤ 3` and its whole horizon lie in the healthy regime, and late anchors leave the fault up to a dozen epochs to develop. |
| Horizon `H` | 8 epochs | At `H = 3` the degraded state overlapped the healthy one in 66% of branches: the fault had not developed, and no threshold could separate states that had not yet diverged. At `H = 8` the overlap is 5%. |
| Healthy / degraded anchors | healthy `a ≤ 3`; degraded `a ≥ 5` | `a + H < 12` is the arithmetic condition for a branch to lie entirely before the fault. `a = 4` is the transition and is excluded from both. |
| Latency budget (SLA) | **850 ms at L=60, 750 ms at L=100, 750 ms at L=140** (0.14; single value 750 ms in 0.6-0.13, 500 ms in 0.4-0.5) | Healthy `NO_OP` **per-event** p99, rounded up to the next 50 ms. The rule was declared before any per-event latency was observed; 0.4 had compared the budget with branch-MEAN latency, but the agreement is a promise about each event. Measured 2026-09-22 on calibration run `budget-cal`, stack `5bc49e1c2750002a`: 30 healthy `NO_OP` branches, 27 000 events, p50 475, p90 550, p95 600, p99 750, max 825 ms. 0.9% of healthy events still exceed 750 ms, which is what p99 means. At the former 500 ms budget **31% of a healthy system's events counted as failures**, and `eta_J` on those cells was 0.1008 with 96.7% carried by `Y`: the dispersion was events crossing the threshold, not the system. Derived by `analysis/calibrate_budget.py`, which refuses any branch that is not a healthy-anchor `NO_OP`, and applied to a fresh matrix, never to the run it was read from. The same budget applies on every edge. All three levels were re-derived on 2026-09-29 on one stack, `161b4e3893c01695`; see the 0.14 amendment for why and for the non-monotonicity. |
| `Y` denominator | work accepted at the **gateway** ingress, epochs before the one being read | Amended 2026-09-17. The service-opportunity rule of 0.4 is unchanged and now applied at the gateway as well as the edge, so both sides of the objective share one horizon. Work arriving during the epoch being read is served at the next boundary, so it is not charged as unserved. But the denominator is now counted where the system is *offered* work, not where work happens to arrive. Under `THROTTLE` the two differ by construction: refused work never reaches an edge, so an edge-side denominator shrank exactly in proportion to how much the action refused, and the action was scored on the subset it let through. |
| Undelivered work | edge `unserved_eligible` + eligible gateway residual backlog | Work the branch accepted and never delivered counts as failed wherever it was stranded. Before the amendment a gateway backlog left standing at the horizon was invisible. |
| Disruption (cost term) | cumulative eligible deferrals + undelivered, over accepted | Deferral is counted every time work is pushed into the admission backlog, not only where it remains at the end. Work delayed and later drained was still displaced; the earlier residual-only reading charged nothing for it — and, because the gateway reported its backlog into the structural fingerprint rather than into observed outcomes, charged nothing at all. |
| Repeats | 10 per cell | Bootstrap CI half-width of the `NO_OP`–`REROUTE` contrast: 0.041 at N=3, 0.037 at N=5, 0.031 at N=8, 0.030 at N=10. Past 10 the interval stops narrowing, so 30 repeats could not be defended. |

### Calibration is measured on `NO_OP` branches only

`η_J`, the healthy latency distribution and therefore the agreement itself are
estimated from no-action branches alone. This is not a convenience: an action
changes the state, so including it confuses the system's condition with the
consequence of intervening in it. Measured directly — a `THROTTLE` applied at a
pre-fault anchor caps admission below the offered load for the whole horizon and
produced higher latency than the fault did, which made the "healthy" set show a
p95 of 1197 ms against the degraded set's 1057 ms. A healthy system cannot be
slower than a broken one; the comparison was wrong, not the system.

### What the pilot showed, and what it did not

At healthy anchors both interventions make the objective **worse** (`NO_OP`
0.119 against `REROUTE` 0.248 and `THROTTLE` 0.520 at `a01`); at degraded
anchors both make it **better** (`NO_OP` 0.302 against `REROUTE` 0.150 at
`a09`), with the sign reversing between `a05` and `a06`. An action is therefore
not good or bad in itself, and a controller with a fixed response to an alarm is
harmful before the fault and helpful after it. This is the premise the method
rests on, observed rather than assumed.

Measured dispersion at the pilot's 600 ms budget was `η_J = 0.0708`, of which
98.7% came from the failure term. Against effects of 0.15–0.20 at the deepest
anchors this gives `SNR_J ≈ 2.5–2.9`: **below the preregistered gate of 3**, on
29 of 32 contrasts. That is a result, not a failure to be tuned away — at this
impairment a single primitive action is only marginally separable from replay
dispersion, which is precisely why ranking accuracy and regret are defined
tie-aware and why `η_J` is reported before any comparison that depends on it.
Whether the frozen 500 ms budget moves `SNR_J` above the gate is measured by the
next run and reported either way.

Pilot numbers are diagnostics. They are not findings, they are not reported as
results, and no branch produced before this freeze is evidence for any claim.

## 3. Scenarios

| ID | Scenario | Primary driver | Split |
|---|---|---|---|
| F1 | gradual link degradation, loss 0% → 20% | network | train/ID |
| F2 | latency inflation, RTT 10 → 250 ms | network | train/ID |
| F3 | edge compute overload, CPU 30% → 95% | compute | train/ID |
| F4 | queue congestion, λ > μ | compute | train/ID |
| F5 | mobility with gateway handover | mobility | **OOD** |
| F6 | abrupt edge-node failure | availability | **shift** |
| F7 | cascading failure (mobility → loss → retries → queue → latency → timeout → retry storm → SLA failure) | combined | **OOD** |

All parameters in `experiments/scenarios/F*.yaml`. F7 is the showcase experiment and drives Figure 3.

## 4. Controllers

`B1` reactive threshold · `B2` GRU prediction + heuristic recovery rule · `B3` graph-based predictor + same heuristic · `B4` PPO · `B5` CSC-Predict · `B6` CSC.

**B1 fairness.** B1 has the **same action primitives** as CSC — a baseline with a poorer repertoire would let CSC win on options rather than on decision quality. What it lacks is a model, not actions: it maps observable symptoms to responses by fixed priority, with hysteresis on entry and release. It **may not read the scenario label or fault-injector state**; a controller that knows which fault generator is running is not a baseline. Its thresholds are frozen on pilot/validation data before any comparative run.

**B5 is redefined in 0.2.** It estimates `P̂(F_{t+Δ} | S_t, A_t = a)` with the action supplied as an ordinary predictor input, trained on the same records as CSC (including the randomised-action records of §6a), and performs no structural intervention. This is the comparison that decides whether the SCM and `do(a)` earn their place: if an action-conditioned supervised predictor ranks as well, the causal layer is decoration. It is stated here, before the experiments, precisely so that a null result on it must be reported.

Fairness constraints, all enforced in code and asserted in tests:
- identical telemetry features and identical observation window for every learned controller;
- identical action set and identical execution mechanism;
- comparable hyperparameter search budget (fixed trial count, recorded per controller);
- no controller receives future information; B6 receives no privileged signal absent from B5.

## 5. Ablations

`A1` CSC without the uncertainty filter (`U_max = ∞`, τ̂ still CRC-calibrated) · `A2` CSC without MNI (`argmin_a R_a`) · `A3` CSC without the causal layer (observational action scoring) · `A4` (optional) CSC with `τ̂` chosen by uncorrected empirical risk instead of the finite-sample CRC rule — isolates what the correction term buys at `n = 20`–`30` runs.

## 6. Data splitting

Split by **run**, never by row. Telemetry within a run is temporally correlated; row-level shuffling would leak and a reviewer will check for it.

**Corrected in 0.2** — protocol 0.1 contained a contradiction, listing F6 as an ID test scenario in the table while the text drew ID data from F1–F4 *and* F6. The resolved split:

- **train**: F1–F4, seed block A
- **validation**: F1–F4, seed block B (horizon and hyperparameter selection only)
- **calibration**: F1–F4, seed block C (disjoint from train and validation)
- **ID test**: F1–F4, seed block D, **with new parameter values as well as new seeds** — otherwise "ID test" only measures seed variance
- **scenario shift**: F5, F6, F7 and combined faults — never used for training, calibration, or any selection decision

### 6a. The ID run-generating distribution `P_ID`

Independent seeds alone do not make runs exchangeable. Calibration and ID test runs are drawn independently from a declared distribution

```
Z_i = (scenario_i, severity_i, workload_i, seed_i) ~ P_ID
```

with scenario uniform over {F1, F2, F3, F4}, severity sampled from the per-scenario range in `configs/p_id.yaml`, workload parameters from their declared ranges, and disjoint seed blocks between calibration and test. The CRC guarantee is stated with respect to `P_ID` and nothing else; F5–F7 lie outside it by construction and receive no guarantee, only measured empirical risk.

**Anchor selection.** Anchors are drawn after the start-up transient has cleared (the first `warmup_s` plus the first 30 s of measurement), on a pre-declared grid, and never chosen by looking at outcomes. M2 found that early anchors sit in a queue-fill transient where all actions look alike.

### 6b. Interventional training data

At every training anchor **all** candidate actions are executed in their own branches, giving `(S_t, a, S^a_{t+1}, Y^a)` for every `a`. Assignment is forced rather than sampled, so this is a designed experiment on the emulator and no propensity weighting is required. The randomised behaviour policy of v2 is retired as redundant. A branch must record whether its action actually changed system state: M2 found `THROTTLE` branches that were well-formed, reproducible and identical to `NO_OP`, which would have inflated apparent agreement between actions.

**`B` for the uncertainty ensemble.** A 5–95 interval from 20 replicas rests on its extreme order statistics. `B` is selected in the pilot from {20, 30, 50} on the stability of `Û` and of the induced ranking against inference overhead — on validation data only, never on test outcomes.

Replay-branch data is quarantined from all model training. A leakage test in `intelligence/tests/` must fail the build if a replay-derived record appears in a training set.

## 7. Seed pairing

Seed `s` defines the workload trace, the fault schedule, mobility, and all environment randomness. Every controller and every ablation is run at the same `s`. Analysis is paired throughout. Seed sets must be identical across methods; `analysis/validate_results.py` fails the pipeline otherwise.

## 8. Exclusion policy (declared before any results are viewed)

A run is excluded only for a documented **technical** failure: container OOM-kill, orchestration crash before the measurement window ends, fault injector reporting a non-applied schedule, or clock anomaly. Every exclusion is logged in `experiments/manifests/exclusions.csv` with run ID, reason, and evidence. Exclusions are reported as a count in the paper. **No run is ever excluded on the basis of its outcome.** If exclusions exceed 5% of any configuration, the whole configuration is re-run and both attempts are reported.

## 9. Statistics

Per-seed observations are stored raw. For each primary comparison: 95% bootstrap CI (10,000 resamples), paired Wilcoxon signed-rank, effect size (Cliff's delta or rank-biserial), Holm correction across the primary pairwise family. p-values are never reported alone.

**H3 is a non-inferiority claim and is tested as one.** "No statistically significant difference in availability" is *not* evidence of equivalence — it is equally consistent with an underpowered comparison, and a reviewer will say so. The margin `Δ_A = 0.005` (0.5 percentage points of availability) is declared in `configs/objective.yaml` before the main runs. The claim tested is

```
H0 : A_MNI − A_riskmin ≤ −Δ_A        (MNI is inferior)
H1 : A_MNI − A_riskmin >  −Δ_A        (MNI is non-inferior)
```

by a one-sided paired test at 5%, equivalently the lower bound of a 90% two-sided CI lying above `−Δ_A`; TOST is reported alongside for the two-sided equivalence reading. Only if H1 is accepted may the paper say that minimum-necessary intervention reduced cost "without a practically meaningful loss of availability". If it is not accepted, the sentence to write is that the availability cost of MNI could not be bounded below the declared margin.

**H4 is a tail claim.** Median decision latency is not the quantity a runtime controller lives or dies by. The registered criterion is `p95(T_dec) < 100 ms` at up to 10,000 devices together with a deadline-miss rate below 1%. The 100 ms figure is checked for consistency against the 500 ms controller tick and the 100 ms telemetry period during the pilot, and frozen there.

## 9a. Two levels of prefix identity

Bit-identical telemetry is the wrong acceptance test once the substrate is distributed: message interleaving and scheduler decisions will differ between runs even when nothing semantically differs. Two hashes are therefore kept, and they are never conflated.

- **StructuralStateFingerprint** — the semantic state a branch must share with its siblings, matched **exactly**: logical tick; ordered queue-content digests with head/tail IDs; retry pending sets, attempts and logical backoff deadlines; configured and live rate-limiter state; timeout deadlines; routing and service placement; replica and pending-migration state; edge capacity; per-producer and processed sequence positions; transport watermarks; fault phase; action history; and configuration hash. Matching queue depths alone is insufficient. A mismatch aborts the branch set.
- **RuntimeObservationFingerprint** — CPU, RSS, wall-clock latency, scheduler and socket timings. Expected to vary; its dispersion is recorded and never used to declare semantic equality.
- **Raw execution hash** — byte-level digest, integrity only. It will differ between distributed runs and that difference is not a defect.

**No tolerance on the structural fingerprint, and this is not fastidiousness.** If two branches may begin from queue depths of 48 and 54, then `η_J` measured afterwards mixes two things: runtime nondeterminism after the action, which is what it must capture, and pre-action state mismatch, which is not. That would make the resolution band partly a measure of its own sloppiness. Tolerance belongs only to the runtime observation fingerprint.

Before branching, the runner recomputes the **observed state fingerprint** from live runtime state and compares it with the anchor's. `state_id = SHA256(config ‖ seed ‖ tick ‖ action history)` names the *expected* anchor; it is not evidence that the actual distributed state matches. A fingerprint mismatch aborts the branch set rather than producing a comparison across states that were never the same.

## 10. Determinism validation — audit D0

Protocol 0.1 asked for ≥30 replays of every state and action. That is unaffordable at experiment scale and was never the right design. **D0** is a separate, one-off audit:

```
20 representative decision anchors  ×  5 actions  ×  30 identical repeats  =  3000 branches
```

From it, over repeat pairs of the *same* anchor and the *same* action,

```
η_J = Q_0.95( | J_obs,ri(a) − J_obs,rj(a) | )
```

`η_J` is frozen at the end of D0 and used everywhere afterwards: to declare ties, to define harmful interventions, and to set how many repeats a main-experiment branch needs (default 3, revised from the measured variance).

**D0-lite first.** 10 anchors × 3 actions × 20 repeats on the distributed substrate, before `MIGRATE` and `REPLICATE` are implemented. Define the signal as the median, over anchors and unordered action pairs, of the absolute difference between their within-cell median `J_obs`; define `SNR_J = signal/η_J`. The preregistered gate is `SNR_J ≥ 3`. If `η_J=0` and the signal is positive, `SNR_J=+∞` and replay is exactly resolving at the observed precision; if both are zero, the ratio is undefined and the design is non-informative. Only after the gate passes is the full 20 × 5 × 30 audit worth running.

`processed − admission_backlog` may be printed as `J_m2_diag` to diagnose branch mechanics, but it is not `J_obs`, is higher-is-better, and cannot pass D0-lite. D0-lite requires the frozen lower-is-better failure/latency/cost objective from §2.

Every reportable branch recreates the complete process topology before replay; `run_id` scopes protocol messages but does not reset counters, queues or routing. The action is applied after the anchor and must be acknowledged by the target with matching `(run_id, action_id)` before the next epoch. Kernel `netem` is placed on the device simulator's device-network egress, the direction of the declared device→gateway flow, with a fixed recorded PRNG seed; control and bus interfaces are verified unshaped.

**Hard gate.** If `η_J` is wide enough to swallow the typical spread between actions, the replay methodology cannot resolve what the paper needs it to resolve. In that case implementation returns to the determinism phase; it does not proceed to machine learning with an unusable reference.

## 11. Pilot before freeze

A reduced pilot (100 devices, F1/F3/F7, 5 seeds, B1/B2/B6) runs before protocol 1.0 in order to expose methodological problems while changing them is still legitimate. Pilot results are **never** reported as findings and never re-used as evidence.

## 11a. The fault is a declared factor

Through protocol 0.7 every branch carried one fault: `edge00` capacity
150 -> 60 at epoch 12, identical in all 900 branches of every matrix. That
makes the anchor index an exact proxy for how long the fault has been running,
and it invalidates two things the paper needs.

A predictor trained across anchors can reach low error by memorising the
schedule. Nothing in such a result says whether it learned the state. And a
controller evaluated at one onset and one severity has no evidence of
generalisation at all -- the strongest reading available would be "it works on
this one scenario", which is not the claim the paper makes.

From 0.8 a **scenario** is a declared factor:

| Factor | Levels | Rule |
|---|---|---|
| Mechanism | `D1` edge capacity degradation · `D2` ingress impairment ramp · `D3` edge stall | declared per scenario |
| Onset `T` | epochs 8-24 | drawn per scenario from the declared range, seeded |
| Severity `S` | serve-per-epoch 40, 60, 90 after onset (from 150); for `D2`, the declared impairment step | drawn per scenario |
| Workload `L` | 60, 100, 140 events per epoch | drawn per scenario |
| Seed | per scenario | fixes emission, netem and every RNG stream |

A branch is `(scenario, anchor, action, repeat)`, named `sNN-aNN-ACTION-rNN`.
The branch manifest records each factor as a **separate field** —
`scenario_id`, `fault_type`, `fault_onset`, `fault_severity`, `workload_level`,
`seed`, `anchor`, `action`, `repeat` — rather than only inside a composite
identifier, so that no analysis has to parse a name to know what it ran. The scenario is fixed within a
cell and across the actions compared at an anchor: repeats are replays of one
prefix, so a scenario that varied by repeat would make the replay band measure
the scenario rather than the replay. Actions must share the prefix to be
comparable at all.

Each branch then falls in one of three regimes, determined by the branch's own
numbers rather than by its anchor index:

- **pre-fault**: `T > anchor + H`. Nothing is wrong and nothing will go wrong
  inside the horizon. The inequality is strict because the branch covers epochs
  `anchor` through `anchor + H` inclusive: written as `anchor + H <= T` it
  labelled a branch whose final epoch carried the fault as fault-free, and the
  accounting audit caught that on ten cells of anchor 4.
- **spanning**: `anchor < T < anchor + H`. The fault arrives during the horizon.
- **post-onset**: `T <= anchor`. The fault is already running at the anchor.

The healthy/degraded partition of 0.4 is replaced by this regime label, which is
a property of the branch.

### What this means for what can be claimed

In the spanning regime the state at the anchor carries no information about a
fault that has not happened. No predictor can know it, and the paper does not
claim otherwise.

It is tempting to add that abstention is therefore the correct behaviour and to
count that as a result. It is not, unless the abstention is produced by
something the controller can measure. Otherwise the claim reduces to "the system
correctly predicted unpredictability", which is not a claim. Two situations are
evaluated and reported **separately**:

- **unknowable future event** — nothing in the observed state carries the coming
  fault. A low predicted risk is correct here and the controller may be
  surprised. Conformal risk control bounds a risk defined over the observed
  distribution; it gives no protection against an event absent from the
  observations, and the paper states this rather than implying otherwise.
- **uncertain current state** — the observations do carry signal and the
  ensemble spread or the conformal width says the evidence does not justify a
  specific action. Abstention here is the mechanism working, and is the only
  case counted as such.

An abstention rate is therefore never reported as a single number. It is
reported per regime, beside the ensemble disagreement and conformal width that
produced it.

Fault onset and severity appear in the node's reported capacity, and therefore
in the structural state. They are **excluded from the predictor's features**: a
controller in a running system does not know when its future fault will arrive,
and a model given the schedule would be reporting the schedule.

Exclusion by intention is not enough, because leakage returns through side
doors. Three tests are required before any model result is reported, and all
three are part of the artifact:

| Test | Passes when |
|---|---|
| Feature schema | the feature set provably excludes `scenario_id`, `fault_type`, `fault_onset`, `fault_severity`, the absolute anchor index, and any future schedule. Enforced in the extractor and unit-tested against the recorded manifests. |
| Permutation | telemetry permuted between scenarios destroys performance. If performance survives, the model is reading something other than telemetry. |
| Time-only baseline | a predictor `f(t, a)` given only elapsed time and the candidate action is materially worse than the telemetry model. If time alone does nearly as well, the confound is not fixed. |

The time-only baseline is retained permanently, whether or not it appears in a
main table.

### The workload factor changes the latency budget

The budget is calibrated by the §2a rule on healthy `NO_OP` branches, and the
healthy per-event latency distribution depends on offered load. A single budget
across workload levels would make `Y` measure the load rather than the failure —
the same error as calibrating on branch means (0.6) and as counting the
denominator at the edge (0.5). The budget is therefore calibrated **per declared
workload level**, by the unchanged rule, on healthy `NO_OP` branches at that
level, before any comparative result at that level is examined. The frozen
As of 0.14 all three levels are calibrated: 850 ms at L=60, 750 ms at L=100 and at L=140.

### Pilot before the full design

Two or three scenarios first: early onset with moderate severity, late onset
with strong severity, and if cheap an unseen workload level. The pilot checks
replay accounting, branch identity, `η_J`, action effects, and that the
extractor hands the model telemetry rather than timing. It also measures
per-branch wall-clock cost, which is what sets the size of the full design
rather than an assumption about it.

### Status of earlier runs

m2prime-903 remains valid and reportable for what it measured: replay
dispersion and action resolvability on one scenario, on an audited objective.
It is superseded only as a basis for the predictor comparison and the
controller evaluation, both of which require the factor.

## 11b. Retaining the explicit structural layer — rule fixed in advance

`B5` is the action-conditioned associative challenger defined in 0.2. This
section fixes what would make the explicit structural layer worth keeping, and
it is written before the `B5` test sets are inspected.

Two tie-aware quantities, both using the measured replay band `η_J` as the tie
width, because a difference smaller than the band is not a difference:

- **`CRA_η`** — correct ranking accuracy. Over decision points, the fraction
  where the action the predictor ranks first has a reference `J_obs` within
  `η_J` of the best action's. Any action inside the band counts as correct.
- **`Reg_η`** — band-adjusted regret, in `J` units:
  `mean( max(0, J_obs(chosen) − min_a J_obs(a) − η_J) )`. Differences inside
  the band are not charged.

**The rule.** The explicit structural layer is retained only if, on the
parameter-shift or the mechanism-shift regime (not on in-distribution, where
dense interventional branch data already suffice), it achieves either

- `CRA_η(structural) − CRA_η(challenger) ≥ 0.05`, with the lower bound of the
  95% bootstrap CI of that difference above zero, **or**
- `Reg_η(structural) ≤ 0.90 · Reg_η(challenger)`, with the upper bound of the
  95% bootstrap CI of the difference below zero.

Anything else is reported as a tie and the architecture drops the explicit
layer. A margin is used rather than a p-value because a statistically
detectable difference of 0.005 in ranking accuracy would not justify the
complexity it buys.

Three outcomes, three honest papers, and the architecture survives all three:

| Outcome | What is claimed | Architecture |
|---|---|---|
| structural passes the margin | structural inductive bias improves intervention ranking under shift | predictor → SCM → ensemble → CRC → MNI |
| tie | with dense interventional branch data, explicit causal structure adds little | predictor → ensemble → CRC → MNI |
| challenger passes it in reverse | the explicit structure introduced misspecification error | predictor → ensemble → CRC → MNI |

`B5` therefore selects the final architecture. It is not a test of whether the
work survives, and an earlier plan of mine that treated it as one was wrong in
the direction that abandons viable work. 0.2 already said a null result must be
reported; this section says what will be done with it.

## 12. Amendment log

| Date | Change | Reason |
|---|---|---|
| 2026-10-04 | **0.26 the measured resource and bandwidth components do not discriminate between actions, which is the third identifiability result and the reframing of the paper.** Measured on `d6-pilot-v2` (108 branches, stack `408a36b2a908cf6d`, all three components present on every branch): `resource` **0.0180 / 0.0181 / 0.0166** for NO_OP / REROUTE / THROTTLE, and `bandwidth` **0.3253 / 0.3253 / 0.2864**. Recruiting a second edge moves the resource component by **0.0001**, because a container's CPU is dominated by its idle loop -- the service tier runs at 1.8% of its own capacity and serving a few thousand JSON messages costs microseconds against 21 epochs x 300 ms across five containers. Bandwidth is identical under NO_OP and REROUTE to four decimals because rerouting changes a message's SUBJECT, not how many are sent; only THROTTLE moves it, by admitting less. So bandwidth measures the volume of work and resource measures the idle baseline, and neither prices the one thing rerouting does. `C(REROUTE)` is no longer 0.000 -- the single claim made in advance holds -- but at 0.1639 against NO_OP's 0.1914 rerouting is still **cheaper than doing nothing**, and `J_obs` still ranks it first. **The resource cost of an action is not identifiable from container accounting**, and unlike the windowed rates of 0.10 no instrumentation removes it: the quantity is not under-sampled, it is dominated by a term independent of the action. `analysis/cost_sensitivity.py` reports the ranking as a function of a **declared** price per edge held open, swept and labelled an assumption with a range. **Measured:** rerouting is preferred while that price stays below **0.67** of the cost scale, inaction above it, and above **0.87** throttling overtakes rerouting too -- the crossing predicted at 0.667 from the arithmetic before the sweep ran and observed between the 0.65 and 0.70 grid points. So rerouting does not win merely because it is unpriced: it wins because a second server's throughput outweighs any moderate price, and overturning it needs one extra node priced at two thirds of the whole scale. The sweep's own first version divided by the recruitable edge count, capping the price's effect at 0.0333 below the 0.0445 gap and making 'no crossing at any price' a property of the normaliser; it prints the reachable ceiling beside its conclusion now, with a fixture asserting the ceiling exceeds the gap. It is it is deliberately kept out of `analysis/jobs.py` so that `J_obs` stays what was measured and nothing downstream inherits a price nobody paid. **No further mechanism will be built.** Three mechanisms were added to make the comparison discriminate and all three degenerated, which is the evidence that the obstacle is the objective's observability rather than the fault model. | The three walls are the result, and they are of different kinds, which is what makes them worth reporting together. Onset and severity are not separable from cumulative counters, and a windowed observable fixes it -- measured, 13 flipped signs to 0. The capacity of an idle alternative is not identifiable from telemetry of the current routing, and nothing fixes it, because the counterfactual asks about a path carrying nothing. The resource cost of an action is not identifiable from the accounting of containers that idle. Each was preregistered and then measured, and together they explain every degeneracy seen -- rerouting wins on D1/D3 and on D6 because it is an unpriced recruitment of capacity, and inaction wins on D4/D5 because no action is priced correctly either. The manuscript's claim therefore changes: the contribution is a measurement methodology for proactive self-healing that detects its own model's failures, with the detections declared in advance, and CSC is one of the methods it evaluates rather than the thing being sold. That is a smaller claim than the one this project started with and it is the one the data supports. |
| 2026-10-04 | **0.25 the resource and bandwidth components of C(a) are measured, because the objective had been declaring rerouting free.** The D6 pilot refuted all three preregistered expectations: REROUTE was best in **12 of 12 cells** and THROTTLE worst in 12 of 12, at severities 40, 60 and 90 alike. The cause is not the mechanism. Rerouting does not move work between nodes, it **recruits a second server** -- the queue on the loaded edge keeps draining while new work goes to the other, so aggregate service becomes 2x the degraded rate -- and the component that would charge for recruiting a container was reported as zero. The calibration split had printed it plainly: `C(NO_OP) 0.000, C(REROUTE) 0.000, C(THROTTLE) 1.000`. Of the four declared components only disruption was instrumented, and it is the one that charges THROTTLE heavily and REROUTE not at all. Now measured: **resource** as cumulative CPU microseconds from each container's own cgroup (v2 `cpu.stat`, v1 `cpuacct.usage`, unit difference handled, source recorded), normalised by the declared service-tier size x branch wall time; **bandwidth** as encoded envelope bytes published, counted in one wrapper so the two adapters cannot disagree, normalised by a declared reference. `added_latency` is **excluded by argument and named as excluded**: the latency an action imposes is already the L~ term, and charging it again counts one effect twice. C(a) is the mean of the components measured, which leaves every pre-0.25 figure numerically unchanged -- with disruption alone the mean is disruption. Absence is never a zero: a node silent about its own CPU makes the component unmeasured for that branch. Nine fixtures, 136 guards. **Preregistration: I do not predict which action wins.** That is now the measurement, and the one claim I will make in advance is that `C(REROUTE)` stops being 0.000. | Two mispredictions in a row, both mine and both the same error: I designed D4 and then D6 around where work goes, while the testbed's actual degree of freedom is how many servers are working. The second failure is what forced the right question -- not which fault to build next, but why one action is free -- and no further mechanism would have fixed it, because the bias was in the objective's instrumentation rather than in any fault. The first version of the new normaliser reproduced the bias one floor down: dividing by the nodes that ANSWERED made it a mean utilisation, so recruiting an edge diluted the cost instead of charging it, and a fixture written to assert the component's whole purpose caught it before any run. Every matrix must be re-run: the old branches cannot report observables that did not exist, and the stack changes with the rebuild, so the budget is re-derived first. |
| 2026-10-04 | **0.24 mechanism D6 and a balanced matrix, with the correct action per severity PREREGISTERED below before the mechanism was ever run.** Measured defect: on the D4/D5 transfer set (200 decision points, unseen mechanisms) the degenerate ablation `A1b_no_gate`, which removes the gate and therefore always takes the cheapest action -- `NO_OP`, cost 0 by definition -- scored `CRA_eta` **0.955** and regret **0.0009**, against CSC's 0.900 / 0.0047, B1's 0.890 / 0.0075 and the oracle's 1.000. Doing nothing is near-optimal there. On the earlier D1/D3 matrix the same ablation scored **0.254** while a one-line reactive threshold attained the oracle. **The two sets are degenerate in opposite directions and neither poses the problem of choosing among actions.** What is absent from both is any regime in which `THROTTLE` is correct, so the one action carrying a non-zero cost is never worth paying for and no method is ever tested on the decision it exists to make. D6 degrades BOTH routable edges to the same surviving capacity -- a shared-resource event, one character of arithmetic from D4, which puts the relief path strictly below -- so rerouting is pointless rather than harmful and admission control is the only remaining lever. It needs no change to the node and no image rebuild, so the stack and the 750 ms budget are unchanged. **Preregistered, at load 100 with the throttle cap 50:** severity 40 (deficit 60/epoch) THROTTLE best, expected dJ ~ -0.21; severity 60 (deficit 40) THROTTLE best, ~ -0.11; severity 90 (deficit 10) NO_OP best, THROTTLE worse by ~ +0.26; REROUTE best nowhere. The correct action therefore varies WITHIN one mechanism, so no fixed-action policy can win on D6 alone. The balanced matrix is D1 + D4 + D5 + D6. | Fixing a benchmark that cannot discriminate is not tuning toward a conclusion, and the argument is the same one that justified D4: a comparison in which some fixed action attains the oracle measures nothing about a decision method, whichever direction it degenerates in. What makes this preregistration a real risk rather than a tautology is that the objective charges shed work TWICE -- once in Y as undelivered and once in the cost term as displaced -- so with weights 0.6/0.2/0.2 the latency saving must beat 0.2 x the shed fraction, and at severity 90 the arithmetic says plainly that it does not. If THROTTLE fails to win at severities 40 and 60, that is reported, D6 does not deliver what it was built for, and no weight, threshold or band moves in response. The arithmetic above was worked before any run, which is how the first D4 design was caught; a 6-scenario pilot checks it at ~10 minutes before the matrix is paid for. |
| 2026-10-04 | **0.23 the preregistered structural sign test FAILS on D4 and the failure is reported as the result: the capacity of an idle alternative is not identifiable from telemetry of the current routing.** On `d45-matrix-v1` (1800 branches, accounting audit clean) the test reproduces 96 of 101 resolvable signs, 0.950 -- pre-fault 54/54, spanning 40/44, post-onset 2/3. **All five flips are `REROUTE`, and all five are the same mechanism:** the model predicts rerouting will help by about +0.15 while the measurement says it hurts by about -0.14 (`s03-a14`, `s27-a02`, `s27-a08`, `s33-a14`, `s39-a14`). The cause is Assumption 1 as written: capacity is inferred from throughput only where the queue is non-empty, and nominal capacity is used otherwise. The relief edge carries no traffic under the current routing, so its queue is empty and its throughput is zero, and the model therefore credits it with its NOMINAL capacity of 150 while D4 has degraded it to 20 or 45. The model is not being rescued and the test is not being re-run with a changed rule: δ, θ, τ̂ and the §11b retention rule were all fixed before any of these splits were examined, and the protocol says a flipped sign on a resolvable contrast is a modelling failure to be reported. The budget is unaffected: L=100 re-derived on this stack gives **750 ms for the third time** (p99 750 on three independently built stacks, 22 Sep, 27 Sep, 4 Oct), so the substrate is cleared as a confound by measurement rather than by assumption. | This is the strongest result in the project and it is a negative one. A counterfactual evaluation of a rerouting action must know the capacity of a path that is currently carrying nothing, and no amount of telemetry from the path in use supplies it -- the same identifiability wall as `served + q = λk` in 0.10, but one that a windowed observable cannot climb, because the missing quantity is not under-sampled, it is unsampled. The honest consequences: the structural layer predicts the ranking of actions that keep work where it is, and must declare an assumption for any action that moves work somewhere it has not recently been; an operator can supply that assumption (a configured nominal, a probe, a health report from the target) and the paper says so, but the testbed does not pretend to infer it. Reported this way the manuscript's contribution is a measurement methodology that can detect its own model's failure, with the detection preregistered -- which is a stronger claim than 101/101 would have been, and one a reviewer can check. 1800 branches at L=100; the decision layer cannot be scored on this matrix standalone (14 in-distribution design points of 40 against 58 required by equation (9)) and is scored as a transfer set against `b5-matrix-v2`, which is what 0.15 specified. |
| 2026-10-04 | **0.22 the gateway forwarding bound charges the ONSET epoch at the healthy rate, because the gateway's fault acts on the other side of the epoch boundary from the edge's.** The bound refused 228 branches of `d45-matrix-v1` at an overshoot of exactly one cap's worth -- 1840 forwarded against a bound of 1800, with 2100 of 2700 accepted and 260 still in the admission backlog, so the fault was plainly binding. An edge fault limits **serving**, which happens at the epoch boundary with the fault already in force, so `onset - 1` healthy epochs is right there and that bound is unchanged. A gateway fault limits **arrivals**, and an event tagged with epoch T can reach the gateway before the boundary at which the fault for T is applied, because the device simulator emits ahead of the boundary; the onset epoch is therefore a transition epoch admitted partly under the previous cap. The bound is now `offered x min(serving, onset) + cap x (serving - onset)`, extracted as `gateway_forward_bound` with eight fixtures, one of which is the dead fault of 0.20 -- still refused, 2700 against 2220. **The extraction itself introduced a `NameError`:** the variable guarding the comparison was defined in the code the bound replaced, and the fixtures for the bound could not see it, because a test of a helper is not a test of the code path -- `audit()` crashed on the first of 1800 branches. `tests/test_audit_end_to_end.py` now builds synthetic branch directories and runs `audit()` itself, eight cases covering the refused branch, the dead gateway fault, the dead edge fault, a split that does not sum, `NO_OP` charged with displaced work, deferral with no limiter, and invariant 1. 124 repo-audit guards. | This is a correction to a bound, not a tolerance: the 1.02 factor was left exactly as it was. Loosening it until the message went away was the available shortcut and it would have cost the check its purpose, which is to catch a parameter that arrives and does nothing -- the one defect in this whole sequence that was a property of the system. The two bounds now differ, and that asymmetry is the finding: a fault upstream of admission and a fault in service capacity are not interchangeable in the accounting, because one is observed before the boundary that applies it and the other after. Having the arithmetic of both the refused branches and the dead fault written down before anything was re-run is what made the difference visible as mechanism rather than as slack. |
| 2026-10-03 | **0.21 deferral is attributed to the limiter that bound it, so the cost term charges only what the action displaced; and the deferral invariant admits a gateway fault.** Two findings on `d45-pilot-v7`, the first run in which the D5 fault actually binds (860 events deferred under `NO_OP`). **(a)** Invariant 6 read *only a throttled branch defers work* -- true while the action was the sole limiter of admission -- and reported 24 correct D5 branches as instrumentation defects. It now allows deferral where either the action or a declared gateway fault limits admission, and still refuses a branch that defers with neither. **(b)** The substantive one: `disruption` was `(deferred + undelivered) / offered`, so under D5 a `NO_OP` branch was charged the fault's 860 deferrals -- about 0.32, weighted 0.2, **+0.064 on `J_obs` for a branch that intervened in no way** -- while `analysis/policies.py` states `C(NO_OP) = 0 by definition: doing nothing disrupts nothing`. Which cap bound an event is known exactly at the moment of deferral and nowhere afterwards, so the node now reports `admission_deferred_by_action_total` and `admission_deferred_by_fault_total`; on a tie the ACTION is charged, the direction that never flatters the method's own interventions. `analysis/jobs.py` uses the action's share, falls back to the total where the split is absent and flags that per branch, exactly as 0.10 did for the windowed rates. The audit checks that the two sum to the total, that nothing is attributed to a fault a branch does not declare, and that `NO_OP` is charged nothing. Six Go cases, 118 repo-audit guards. **`d45-pilot-v7` must be re-run: its measurement is sound but its cost term is not separable after the fact.** | The contrasts were only mildly affected -- the fault defers under all three actions, so most of it cancels at a common anchor -- which is precisely why this had to be fixed rather than noted. A term that contradicts a definition printed in the manuscript is the first thing a reviewer checks against the table, and 'the error mostly cancels' is not an answer. Found while repairing (a), by asking what the 860 deferred events were being charged to rather than only whether the invariant should fire. The sweep promised in 0.19 missed (a): it grepped the fault fields and the admission limit, not deferral. Three words are not a sweep, and the enumeration that matters is over the INVARIANTS -- each of the nine in `audit_accounting.py` asked, one at a time, whether it survives a fault upstream of every edge -- which is how (b) surfaced at all. |
| 2026-10-03 | **0.20 the D5 gateway fault had no effect, and the invariant that caught it was itself bounding the wrong quantity.** Two defects, found together on `d45-pilot-v6`, whose accounting audit reported *the declared gateway fault had no effect* on all 36 D5 branches. **(a)** The node has two admission paths: the epoch-boundary backlog drain asked `effectiveAdmitCap(action, fault)` for the tighter of the two limiters, while the live ingress path read the action's limiter alone. Under `NO_OP` that limiter is -1, so every arriving event was forwarded and the declared fault changed nothing -- the two paths disagreed about what the gateway's capacity was. Both now ask the same function; eight cases in `cmd/csc-node/admit_test.go`, and a guard requires the call to appear in every admission path. **(b)** The gateway bound added in 0.15 compared the cap against `ingress_accepted`, which counts *arrivals*: deferral is charged cumulatively and a deferred event is still accepted work, which is exactly what makes the denominator action-independent under 0.5. The bound is now on what the gateway **forwarded** -- `accepted - residual_backlog`, every accepted event being either forwarded or still in the admission backlog -- and the message reports all three numbers. `d45-pilot-v6` is void. 111 repo-audit guards. | The audit did its job: this is the first defect in this sequence that was a property of the *system* rather than of a checker, and the one check written to catch a parameter that arrives and does nothing is what caught it. That the same check was also comparing the wrong two quantities is the uncomfortable part -- had the Go defect not existed, (b) alone would have failed every D5 branch for admitting less work than was offered to it, which is the fault working. A wrong check and a wrong system cancelled into a symptom that looked like one problem. Both were found by asking what the recorded numbers *mean* -- 2700 accepted is exactly 100 events/epoch x 27 epochs, the full offered load, which says the cap never bound at all -- rather than by adjusting the threshold until the message went away. |
| 2026-10-03 | **0.19 the THROTTLE check admits that a gateway fault can bind, and `make test` collects every Python test directory.** `analysis/m2prime_report.py` compared the observed admission limit against the action's declared 50 alone and failed all 12 THROTTLE branches of every D5 scenario -- 40 against an expected 50 where the fault admits 40, 27 where it admits 27. Those branches were admitting the tighter of the fault and the action, which is what 0.15 specified the node to do. The expected limit is now `min(action, fault)` where the fault's onset has been reached, the action still binds where it is the tighter one or where there is no fault, a fault before its onset excuses nothing, and the message names both numbers. Ten fixtures in `tests/test_admit_limit.py`. Separately: `make test` collected `intelligence/tests` only, so `analysis/test_features.py` and `analysis/test_objective.py` **have never been run by the test target**, nor had the 0.17 fault fixtures; it now collects `intelligence/tests analysis tests`. 108 repo-audit guards. `d45-pilot-v6` is void. Also recorded: the regime labels of D4/D5 branches are read from each branch's own manifest, so the edge-capacity fallback in `analysis/branches.py` -- which for a gateway-faulted branch would read onset 0 and severity -1 -- applies only to pre-0.9 legacy runs and does not touch them; checked rather than assumed. | Fourth instance in two days of one pattern: an invariant written when the only mechanisms faulted an edge, meeting a mechanism that faults the gateway. 0.17 removed the duplicate copy of one such rule; it did not go looking for the others, which is the error this entry corrects. The remaining assumptions were enumerated by grepping every analysis module for the fault fields and for the admission limit, rather than by running another matrix and reading what broke -- four pilots have now been spent discovering, one at a time, what a sweep would have found at once. The unrun tests are the same failure underneath: every version of these rules was validated by launching a 25-minute run, because the cheap check was wired to a path nothing executed. |
| 2026-10-02 | **0.18 the deployed revision is derived on every deploy; every manifest recorded since 2026-09-25 carries a wrong `git_commit` and is corrected by this entry rather than by editing the files.** `SOURCE_REVISION` was a file kept by hand, last written at `protocol-0.9` on 2026-09-25 and then forgotten. The host has no `.git`, so the runner's `git rev-parse` falls through to that file, and **`b5-matrix-v1`, `b5-matrix-v2`, all three budget calibrations and every `d45` pilot record `git_commit = protocol-0.9`** -- a tag five protocol versions older than the code that produced them. `scripts/deploy_to_host.sh` now writes the file on the host from `git rev-parse --short HEAD` of the tree being sent, refuses a tree whose revision it cannot read, says so when the tree is dirty, and the file is untracked, git-ignored and protected from `rsync --delete`, so it can neither go stale nor be overwritten by an older copy. Four repo-audit guards, 104 in all. **What is recoverable:** the dates and stack ids in every manifest are correct, so each run's code is bounded by the commit history -- `b5-matrix-v2` finished 2026-10-01T13:43Z, after `d031e7c` (2026-09-29) and before `ffa3256` (2026-10-01T17:23Z). The exact deployed tree is not recorded for those runs and is not reconstructed here; the range is what the evidence supports and the range is what the manuscript will say. | Not a measurement defect: nothing computed from these runs depends on the field. It is worse in one specific way, which is why it is an amendment and not a commit message -- `git_commit` exists for exactly one purpose, to let a reader identify the code that produced a number, and a field that is populated, plausible and wrong is less useful than an empty one. The same shape as 0.13: a value supplied by hand, trusted by every script downstream, and never checked against the thing it claimed to describe. Found while verifying that the host was running protocol 0.17 -- `analysis/faultcheck.py` was present and `SOURCE_REVISION` said `protocol-0.9`, so the check that was meant to confirm a deploy instead found the provenance broken. `d45-pilot-v5` was already running under the old behaviour and will carry the wrong label; it is a pilot, and its successor will carry the right one. |
| 2026-10-02 | **0.17 the declared-versus-ran fault rule is one module, `analysis/faultcheck.py`, shared by the runner and the accounting audit.** The rule was written out twice, once in each, and only the runner's copy was corrected by 0.16; the accounting audit then failed `d45-pilot-v4` on all 18 of its D5 branches for the third instance of the same defect -- comparing a gateway mechanism's declared onset and severity against what `edge00` reported, which for D5 is correctly nothing. Both callers now delegate. Thirteen fixtures in `tests/test_faultcheck.py` cover each mechanism as declared, each of the four parameters failing to arrive, each observable missing from the report, the gateway resolved under either node spelling, and a stale edge fault under a gateway mechanism. 100 repo-audit guards, one of which refuses a second copy of the rule in the runner. `d45-pilot-v4` is void as a measurement; its 2 \u00d7 18 completed branches are diagnosis only. | Three instances of one defect in two days, and the cause was not any of the three: it was that one rule existed in two places, so a correction could be complete in one file and absent in the other, and the audit -- the control written precisely to catch an instrumentation defect -- was the copy left behind. The rule had also never been exercised by a test; every version of it was validated by running a matrix, which is why each instance cost a run. The 0.16 entry's claim that the check was verified on eleven fixtures was true of the runner's copy alone. |
| 2026-10-01 | **0.16 the per-branch fault check is mechanism-aware and now also verifies the relief path and the gateway.** The check compared the declared `(onset, severity)` against what `edge00` reported and nothing else. On the first D5 branch it refused the run, because D5 declares a healthy edge and the node correctly reported one. It now verifies, per branch: `edge00` against the declared fault where the mechanism faults an edge and against *healthy* where it does not; `edge01` against `relief_degraded_serve` wherever that is declared; `gateway00` against `degraded_admit`, read from the anchor's `observed` block rather than from `edge_capacity`, an admission cap the operator suffers not being structural service capacity. A branch that declares a fault nowhere is refused outright. The gateway's observable is resolved by key suffix over whatever node reports it, and a declared parameter that no node reports at all is refused with that stated as the reason: the first attempt looked for `gateway00`, the compose *service* name, while the node's id is `gw00`, so both keys read as absent and were compared against a default -- a check that cannot see its subject must fail loudly, never compare against a placeholder. Verified on eleven fixtures covering each mechanism correct, each parameter failing to arrive, and each observable missing from the report. `d45-pilot-v2` and `d45-pilot-v3` are void: each stopped at its second scenario and the 18 completed D4 branches of each are kept only as diagnosis. | The refusal was the guard working on an assumption that had expired, not a bad parameter, and loosening it was the wrong repair: without the edge-healthy direction a stale substitution could leave a previous scenario's edge fault in place and a gateway mechanism would run as an edge mechanism while its manifest claimed the gateway. The two additions close the same hole on the other two parameters introduced by 0.15, neither of which was checked at all: had `relief_degraded_serve` failed to arrive, rerouting would have stayed beneficial and D4 would have silently become D1 -- the precise defect D4 was written to remove, and the second time that same defect has had to be caught by hand. |
| 2026-10-01 | **0.15 two fault mechanisms added in which rerouting is the wrong action, and the decision layer is scored on them as a transfer test.** D4 degrades the loaded edge and the relief path together, the relief path ending strictly below the loaded one, so rerouting moves work to a worse node and is actively harmful. D5 faults the gateway's admission capacity and leaves every edge healthy, so the per-edge service deficit stays near zero, the backlog grows upstream, and no downstream action helps -- inaction is correct, a case the earlier mechanisms never produced. The gateway fault is held apart from the THROTTLE action in the node, the binding limit being whichever is tighter, because a fault the operator suffers and a control the operator chose are different situations calling for different actions. The accounting audit is now mechanism-aware: the edge effect bound is skipped where no edge is faulted and a gateway admission bound is checked instead. `analysis/evaluate.py --transfer-root` scores the decision methods on a second matrix with the predictor, `tau_hat`, `theta`, `C(a)` and the B1 thresholds all taken from the first, its `eta_J` coming from its own replay dispersion. | Measured defect, not coverage. On b5-matrix-v2 a one-line reactive threshold attained the oracle bound -- `CRA_eta` 1.000 in-distribution and under parameter shift, 0.993 under mechanism shift -- because with D1 and D3 only, rerouting is almost always the best action and a threshold on the per-edge deficit finds it. A common-anchor layer in which a baseline reaches the oracle has no discriminating power, and that is the first thing a reviewer sees. In D4 and D5 the correct action depends on WHERE the deficit is rather than on how large it is, which the permitted features expose and a single threshold cannot read. Scoring them as a transfer set rather than folding them into one matrix is both cheaper and stronger: it tests generalisation to unseen failure physics instead of interpolation, and it leaves `delta`, `theta` and `tau_hat` exactly as declared before any test split was examined. A first attempt at D4 scaled the relief path to its own larger nominal, which left rerouting beneficial and would have reproduced the very defect the mechanism exists to remove; caught by working the arithmetic before running anything. |
| 2026-09-29 | **0.14 all three workload budgets calibrated on one stack: 850 ms at L=60, 750 ms at L=100, 750 ms at L=140.** Each comes from a completed dedicated run of 40 healthy pre-fault no-action branches on stack `161b4e3893c01695`, by the unchanged 0.6 rule (per-event p99 rounded up to 50 ms). `analysis/calibrate_budget.py --record` writes each level with its provenance and refuses to overwrite one without `--replace`; the September L=100 entry is retained under `superseded` rather than deleted. **The budgets are not monotone in load** -- the lightest level carries the heaviest tail -- and that is reported rather than smoothed. Two explanations remain open: at L=60 the p99 rests on 14 400 events, so roughly 144 lie above it and the estimate moves by one or two 25 ms bins; or the 200 ms emission spread interacts with epoch-boundary quantisation differently at low event density. The declared rule is applied as written either way. | The L=100 budget had been measured on 2026-09-22 on stack `5bc49e1c2750002a`, before the images were rebuilt, while L=60 and L=140 could only be measured on the current one. The protocol's own argument for a budget per load -- that the healthy distribution depends on offered load, so one budget across levels makes `Y` measure the load -- applies to the substrate as well, and a budget carried across stacks folds a stack difference into a load difference. Re-deriving L=100 on the current stack was therefore necessary, and it returned **exactly 750 ms again, p99 750 in both measurements**. So the substrate is cleared: the non-monotonicity is a property of load or of the tail estimate, not of the rebuild. Had it differed, every result scored at 750 ms would have been superseded, which is why the check could not be skipped. |
| 2026-09-27 | **0.13 `STACK_ID` is derived and an environment value that disagrees is refused; the second `budget-cal-L60` and `budget-cal-L140` attempts are also void.** Every script took `STACK_ID` from the environment on trust. A value set by hand while diagnosing something else stayed in the shell, and the next run was stamped with the id of a stack from five days earlier -- recording the wrong substrate for data produced on the current one. `scripts/run_nightly.sh` and `scripts/m2prime_nats_matrix.sh` now compare any supplied `STACK_ID` against `check_reportable_stack.py` and refuse a mismatch, naming `unset STACK_ID` as the fix. Both guards were verified by running them against a deliberately wrong value and a live pid. The two calibration attempts are discarded: one mislabelled, and both concurrent, which is independently disqualifying under \u00a70.12. | The concurrency prohibition of 0.12 was written but had not reached the host, so nothing stopped the second launch -- a rule that exists only in the repository is not a control. Together with 0.12 this is the same lesson twice: the append-only guard protects output directories, and neither the substrate a run executes on nor the identity it records was checked at all. Both are now. Nothing measured from any `budget-cal-L60` or `budget-cal-L140` attempt to date may be reported, and `configs/budgets.json` remains at the single calibrated level L=100. |
| 2026-09-27 | **0.12 only one matrix may run at a time, and the first `budget-cal-L60` and `budget-cal-L140` attempts are void.** Every branch recreates the whole topology with `--force-recreate`, so two matrices sharing one Docker stack tear each other's containers down mid-branch. `scripts/run_nightly.sh` now refuses to start while any recorded pid is still alive, naming the run that holds the stack. The two calibration runs launched alongside `windowed-pilot-v1` are discarded under the exclusion policy -- documented technical failure, declared before their numbers were examined -- and re-run sequentially. Nothing measured from them may be reported, and `configs/budgets.json` is unchanged. | Found by reading a `--status` listing that showed three runs `running` at once. Nothing in the harness prevented it: the append-only guard protects output *directories*, not the shared substrate they are produced on, and the two concerns had never been distinguished. The windowed-observable gate of 0.10 passed in the same listing -- `WINDOWED OBSERVABLES present in 3/3 anchors sampled` -- so the telemetry change is confirmed independently of the voided calibrations. |
| 2026-09-27 | **0.11 severity and workload de-aliased in the scenario draw; the nightly accounting audit repaired.** `scripts/gen_scenarios.py` advanced severity and workload on the same stride, so of the nine (severity, workload) combinations only three could ever be drawn; the strides now differ and a draw at 36 design points gives all nine cells with two replicates each and both mechanisms balanced 18/18. The generator refuses any draw in which two of severity, workload and onset are perfectly correlated, and that guard fires on the old stride. `scripts/run_nightly.sh` passed `--healthy-anchors` and `--sla-ms` to `analysis/audit_accounting.py`; both are pre-0.8 leftovers, the audit reads them from each branch's manifest now, argparse rejected them, and the `||` reduced a dead guard to one quiet line above the results. The audit now runs, a failure stops the analysis and leaves `logs/<name>.audit-failed`, and `band_sensitivity.py` runs in the nightly as well. `configs/scenarios-b5.json` is superseded by a 36-point set over mechanisms D1 and D3 and workloads 60/100/140, which requires the L=60 and L=140 budgets to be calibrated first. | The aliasing meant a model could not separate severity from workload and a parameter-shift split on either was silently a shift on both. With a single workload level in `scenarios-b5.json` the defect was latent, which is why it survived review; it becomes active the moment workload enters as §0.9 requires. Found while checking that the re-run planned after 0.10 could actually support the three shift regimes the manuscript claims -- it could not: that set holds one workload level and one mechanism, so in-distribution was the only regime reachable. The audit defect was found in the same pass, by running the wrapper's own command by hand. No nightly run has ever been audited by the wrapper; every audit that did pass was run manually afterwards. |
| 2026-09-27 | **0.10 windowed observables added to the decision-time state.** The gateway reports `ingress_accepted_last_epoch` and each edge reports `served_last_epoch`; `analysis/features.py` exposes them, flags their absence per node, and falls back to the cumulative rate so that branches recorded before this date remain readable and are marked as lacking the observable. The structural model reads the windowed values. The preregistered sign test of the structural layer is `analysis/structural_signtest.py`, and the pre-amendment result is retained in full at `data/derived/structural-prefix-v1/` rather than discarded. The B5 matrix must be re-run before the structural and associative layers are compared, because the two must see the same state. | The structural model was written before the challenger was evaluated, as §11b requires, and then failed the preregistered sign test on 13 of 203 resolvable contrasts — every one of them `THROTTLE` at the earliest anchor a02, with the observed contrast near -0.67 and the prediction near zero. Diagnosis: the only rate observables were cumulative, and at epoch 2 the cumulative arrival rate reads 50 while the steady rate is 100, so an admission cap of 50 appeared non-binding when it binds hard. The same absence had already defeated capacity estimation: `served + queued = arrivals × epochs` holds identically, so onset and severity are not separately identifiable from cumulative counters, and a direct test of `q / wait_max_epochs` on 104 post-onset `NO_OP` branches returned medians 103.3 / 100.0 / 83.3 for true severities 40 / 60 / 90 — it recovers the arrival rate, not the capacity. Two independent failures with one cause. The fix is telemetry any real service exposes, not a change to the objective, the bands, the gate or the retention rule, none of which move. Post-onset signs were already 103/103 correct, so the model is not being rescued from a general failure; the pre-amendment record is kept so that the sequence is auditable. |
| 2026-08-25 | Draft 0.1 created. | Project start |
| 2026-08-25 | **0.2 methodology correction.** Conformal *prediction* upper bound replaced by conformal *risk control* on a set-level loss; `α` collision removed; `Ĵ` separated from `J_obs`; `η_J`, tie-aware CRA and regret introduced; PFR/WIR given set-theoretic definitions; H3 made a non-inferiority test; H4 moved from median to p95 and deadline-miss rate; F6 split contradiction resolved; B5 redefined as an action-conditioned associative predictor; randomised behaviour policy added on training scenarios; D0 audit replaces per-branch 30× replication. | External review; see `METHODOLOGY_CORRECTION_REPORT.md` |
| 2026-09-05 | **0.3 distributed replay repair.** All expected producers must close an epoch; action application requires a run-scoped acknowledgement; every branch starts from a recreated topology; fingerprint coverage is enumerated; D0-lite fixes `SNR_J ≥ 3` and the `η_J=0` edge case; `J_m2_diag` is quarantined from `J_obs`; netem direction and seed are fixed. | 48-run prefix burn-in and 108-branch mechanics pilot; diagnostics only, never reused as findings. |
| 2026-09-26 | **0.9 scenario factor completed, leakage tests required, SCM retention rule fixed.** The scenario becomes `(mechanism, onset, severity, workload, seed)` with mechanisms D1-D3 and workload levels 60/100/140; every factor is a separate manifest field, not a substring of a branch name. Three leakage tests are mandatory before any model result: feature schema, permutation across scenarios, and a permanently retained time-only baseline `f(t,a)`. Abstention is split into unknowable future event and uncertain current state and reported per regime beside the ensemble spread that produced it; CRC is stated not to bound events absent from the observations. The budget is calibrated per workload level, so the frozen 750 ms applies to `L=100` only. Section 11b fixes the structural-layer retention rule on a practical margin before the test sets are seen. | External review, accepted on three points. The scenario needed workload and mechanism, not only onset and severity, or leakage returns through load. My own framing of B5 as a verdict on the paper was wrong and pessimistic; 0.2 had it right. And my claim that abstention is correct in the spanning regime was 'the system correctly predicted unpredictability' — abstention counts only when a measurable signal produces it. Added independently: with workload as a factor, one budget across loads makes `Y` measure the load. |
| 2026-09-26 | **0.8 the fault becomes a declared factor.** Onset and severity are drawn per scenario (onset epochs 8-24; post-onset serve 40, 60 or 90 from 150) and held fixed within a cell and across the actions compared at an anchor. Section 11a adds the pre-fault / spanning / post-onset regime labels, which replace the anchor-index healthy/degraded partition. Fault parameters are excluded from predictor features by construction. m2prime-903 stays valid for replay dispersion and resolvability on a single scenario; it is superseded as a basis for B5 and for the controller evaluation. | All 900 branches of every matrix to date carried `degrade_at_epoch = 12` and `150 -> 60`. With one onset the anchor index is an exact proxy for fault age, so a learned predictor can score well by memorising the schedule, and a controller measured at one onset and one severity has no evidence of generalisation -- the first question a reviewer asks. |
| 2026-09-25 | **0.7 the service-opportunity rule is reported, not just computed.** The edge computed its eligible-unserved count and never put it in `observed`, so `analysis/jobs.py` took a silent fallback to the raw inbox length. The numerator then charged the final epoch's arrivals as failures while the gateway excluded those same events from the denominator: a healthy branch with **zero SLA violations scored `Y` = 100/800 = 0.125**, and the whole healthy `J_obs` floor of 0.13 was that artefact. Eligibility is now defined on the event's own epoch on both sides, not on arrival, so a deferred event is scored by the epoch it belongs to. `jobs.py` refuses a branch without `unserved_eligible` instead of substituting, and refuses any branch where served plus undelivered exceeds the work the gateway accepted; the runner checks every observable the objective reads on the first branch. **`J_obs` from m2prime-901 and m2prime-902 is superseded and must not be reported.** Neither can be corrected after the fact: how much work arrived in the final epoch was never recorded, and under `THROTTLE` it is not a constant. What still stands in both: branch admissibility, prefix equivalence, and the per-event latency calibration, which does not depend on the objective. | Found by reading m2prime-902's `jobs.csv` (corrected 2026-09-27: the 0.7 commit message attributed this to m2prime-903, which is wrong -- 903 was built at protocol-0.7, thirty minutes after the fix, and records `unserved_eligible`): `a01-NO_OP-r01` reported offered 800, served 800, unserved 100, violations 0 — served plus unserved exceeded offered, so the two sides of every ratio covered different event sets. `go vet` could not see it: the variable was used by its own increment. |
| 2026-09-22 | **0.6 latency budget calibrated per event and frozen at 750 ms.** Edges report a 25 ms per-event latency histogram as an observed outcome. The budget is derived by a declared rule on a dedicated calibration run of healthy `NO_OP` branches, then frozen and applied to a new confirmatory matrix with the analysis unchanged; `budget-cal` gives 750 ms. `docker-compose.nats.yml` hardcoded 500 ms on `edge01` and `edge02` while only `edge00` read `SLA_MS`, so an action that moves work between edges would have been scored against a stricter budget than its own baseline; all three now read the same variable, and the runner refuses a budget other than the frozen one or a compose file that hardcodes one. **m2prime-901 at 500 ms remains the preregistered result and is reported as run**; it is not re-scored, and it is unaffected by the edge defect because every edge used 500 ms. | m2prime-901: healthy `NO_OP` `J_obs` 0.28-0.32 with no unserved work implied that a large share of a working system's events were over budget; `budget-cal` measured the share at 31%. The 0.4 rule had been applied to the wrong distribution. |
| 2026-09-17 | **0.5 objective denominator corrected.** `Y`, `L̃` and the cost term are computed over work accepted at the gateway ingress, not over work that reached an edge. The gateway now reports `ingress_accepted`, `admission_deferred_total` and `admission_backlog_depth` as observed outcomes; deferral is charged cumulatively; a gateway backlog standing at the horizon counts as undelivered. `analysis/jobs.py` refuses a set that mixes the two denominators. **Every `J_obs` figure produced before this date is superseded and must not be reported**, including the m2prime-900 series; its integrity and dispersion results (branch admissibility, prefix equivalence, `η_J` mechanics) stand, its action comparisons do not. | Defect found in the m2prime-900 analysis: `analysis/jobs.py` read `admission_backlog` from the observed block, but the gateway wrote it to the structural `Queues` map, so the deferred term was identically zero; and `offered` differed per action (a01 `NO_OP` 900 vs `THROTTLE` 500). Both errors flattered `THROTTLE`, the action under test. |
| 2026-09-15 | **0.4 testbed configuration frozen.** §2a added: offered load, emission pacing, edge capacities, fault depth and timing, horizon, healthy/degraded anchor partition, latency budget, `Y` denominator and repeat count, each with its derivation. Calibration restricted to `NO_OP` branches. | Pilot series v1–v5 on stack `afbcb298cb97ee18`; diagnostics only, never reused as findings. |

## Amendment 0.27 (2026-10-05) -- the prediction table was host-dependent

**What happened.** Regenerating the paper's tables on a second machine
reproduced `table_bands_single.tex`, `table_bands_factored.tex` and
`table_spanning.tex` byte for byte, and did *not* reproduce
`table_prediction.tex`: the telemetry kNN MAE read 0.0258 instead of 0.0261 and
the permuted control 0.1610 instead of 0.1607.

**Cause.** `knn_cv` selected neighbours with `np.argpartition`, which leaves the
order among equal distances undefined. Which of several tied neighbours enters
the k-nearest set therefore depended on the numpy build, not on the data. The
harness was already seeded and was deterministic run-to-run on either host; the
instability was only across hosts.

**Fix.** Neighbour selection uses a stable sort, which breaks ties by row index.
Row order is fixed by the recorded branch ordering, so the figure is now a
function of the data alone. `scripts/audit_repo.sh` refuses `argpartition` in
this file.

**What was NOT done.** The number in the manuscript was not replaced with the
one measured on the second host. The reported figures come from the documented
analysis host, and this amendment does not license reporting a figure that the
documented pipeline did not produce. **Action required before submission:** run
`analysis/make_tables.py` once on the analysis host with the fix in place and
take whatever it then emits. Until that is done, `table_prediction.tex` carries
pre-fix figures and is the one table in the paper not yet regenerated under the
current code.

**Does any claim move?** No. The drift is in the fourth decimal. The stated
comparisons are the reduction against a time-only predictor (78 per cent at
either value) and the factor by which permuting the telemetry raises the error
(6.2 at either value). Neither changes, and no conclusion rests on the fourth
decimal of this figure.
