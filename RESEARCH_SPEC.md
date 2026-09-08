# RESEARCH_SPEC.md — Counterfactual Shadow Control (CSC)

Target venue: **IEEE Internet of Things Journal**, regular paper.
Page target: **6.0 published pages including references** (hard ceiling 8 — beyond that IEEE overlength charges apply; the 2-page headroom is reserved for revision, not for the first submission).
Status: **v2**, frozen for implementation start after the methodology correction pass, 2026-08-25. Amendments require a dated entry in §12.

---

## 1. One-sentence claim

Instead of predicting whether a mobile-edge IoT system will fail, CSC estimates what the system's near future looks like *under each available intervention*, executes the **cheapest** action whose **conservative** risk estimate clears a safety threshold, **abstains** when none does, and then checks the executed action against what actually happened.

## 2. What this work is NOT

This section exists because reviewers will pattern-match the paper to five adjacent literatures. Every one of these must be explicitly disowned in the Introduction and Related Work.

| Adjacent area | Why CSC is not that |
|---|---|
| **Failure prediction** | A failure probability is not a decision. `P(F \| S)` says a bad thing is likely; it does not say which of five interventions makes it less likely, nor whether any of them is worth its disruption cost. CSC's output is an action (possibly the null action), not a score. |
| **Reactive self-healing** | Reactive controllers act after the SLA is already violated. CSC acts before, and — equally important — declines to act when acting is not justified. |
| **Root-cause diagnosis / recovery recommendation** | Diagnosis answers "why did this happen". Recommendation answers "what usually fixes this". Neither estimates the effect of a *specific* candidate action on *this* system state, and neither pays the cost of being wrong. See NeSy-Edge, which stops exactly at recommendation. |
| **RL-based control policies** | A learned policy maps state to action through an opaque learned reward. It cannot expose the counterfactual comparison it implicitly made, cannot express "none of my options is reliable enough", and degrades unpredictably under distribution shift. CSC keeps the comparison explicit and auditable, and can refuse. |
| **Digital twins** | A digital twin is a persistent synchronized model of a system. CSC builds transient, action-conditioned forecasts at decision time only. The word "twin" is banned from the manuscript. |

**Also not novel, and must not be claimed** (see NOVELTY_AUDIT.md §5): causal graphs for self-healing; uncertainty gating; abstention; conformal prediction at the edge; GNNs for failure prediction.

## 3. Research questions

- **RQ1** Does action-conditioned counterfactual inference prevent more failures than reactive, prediction-only, graph-based, and RL controllers under matched conditions?
- **RQ2** Does the uncertainty-filtered, risk-calibrated admissible set reduce harmful interventions under scenario-level distribution shift? (`Û` filters and is not itself calibrated; CRC calibrates `τ̂`.)
- **RQ3** Does minimum-necessary intervention lower intervention cost while remaining **non-inferior** in availability within a pre-declared operational margin?
- **RQ4** What runtime overhead does shadow evaluation add as the device count grows?

## 4. Hypotheses (registered before any comparative result is examined)

- **H1** CSC achieves a higher Prevented Failure Ratio than B1–B5, with PFR defined on replayed alternatives (§9).
- **H2** The calibrated gate lowers Wrong Intervention Rate on shift scenarios relative to CSC without the gate (ablation A1).
- **H3** Minimum-necessary intervention lowers mean intervention cost relative to risk-argmin selection (ablation A2) and is **non-inferior** on availability against the pre-declared margin `Δ_A = 0.005`. This is a one-sided non-inferiority claim, not "no significant difference" — the latter is not evidence of equivalence and will not be written as if it were.
- **H4** `p95(T_dec) < 100 ms` at up to 10,000 devices with a deadline-miss rate below 1%. Median latency is not the criterion.

**A hypothesis that fails is reported as failed.** H1–H4 are predictions, not targets. No experiment is re-run, re-tuned, or re-seeded because its outcome was unwelcome.

## 5. System model

Devices `D = {d_1..d_N}`, edge nodes `E = {e_1..e_M}`, services `V = {v_1..v_K}`.
State `S_t = (G_t, X_t)` where `G_t` is the dependency graph (device → gateway → link → edge node → broker → service) and `X_t` the windowed telemetry tensor over node features.

Candidate actions, deliberately five:
`a0` no-op · `a1` reroute · `a2` migrate workload · `a3` throttle source rate · `a4` activate replica.

## 6. Method

1. **Temporal predictor.** GRU or TCN over graph-aggregated node features → `P(F_{t+Δ})`. Horizon Δ selected on validation before any test evaluation. Architecture is deliberately unremarkable — it is not the contribution. A temporal graph model is baseline B3, not the method.
2. **Dynamic topology-informed SCM.** Structure fixed by system semantics, parameters learned, and **temporal**:
   `X_{j,t+1} = g_j(Pa_j(X_t), A_t, u_{j,t})`
   over `Mob → LinkQ → Loss → Retry → Queue → Lat → Timeout → F`, with `EvRate → Queue` and `Load → ProcTime → Queue`. Each `g_j` starts as a GAM or gradient-boosted model, not a large network — interpretability is worth more here than capacity. A static DAG is a picture; the rollout is what produces `P(F | do(a))`.
3. **Counterfactual evaluation.** For each `a`, apply `do(A_t = a)` — replacing exactly the mechanisms that action controls — and roll the SCM forward `H = Δ/tick` steps, averaging over sampled exogenous noise. Which mechanism each action replaces is documented per action, in code and in the paper. `P(F|S)` and `P(F|S, do(a))` stay distinct code paths and distinct log fields.
4. **Cost model.** `C(a) = w_L·L_a + w_R·E_a + w_B·B_a + w_D·D_a`, normalized, weights fixed in version control before the main experiments and never tuned against results.
5. **Risk-calibrated gate — corrected in v2.** CSC does *not* form `R̂(a) + q̂_{1-α}` and does not claim a per-decision bound on the true interventional risk. `R(a|S)` is latent; a replay branch yields a binary outcome, not that probability; and the controller selects adaptively after seeing all five scores, so per-action marginal coverage would not transfer to the selected action anyway. Instead the **gate itself** is calibrated. With
   `A_safe(τ) = { a : R̂(a|S_t) ≤ τ ∧ Û(a) ≤ U_max }`
   and the set-level loss
   `ℓ_t(τ) = 1[ ∃ a ∈ A_safe(τ) : Y^a_t = 1 ]`,
   conformal risk control calibrates `τ̂` such that `E[ℓ(τ̂)] ≤ δ`. The loss is bounded and non-decreasing in `τ` (relaxing the threshold only grows the set), which is what CRC requires; and because it constrains the whole admissible set, it bounds the failure probability of *whatever* rule selects from that set — which is exactly what the adaptive-selection objection demanded.
6. **Minimum-necessary intervention.**
   `a* = argmin_a C(a)` over `A_safe(τ̂)`; if empty → `a_fallback` (guarded abstention; fallback outside the CRC guarantee).
   The controller must **never** silently fall back to `argmin_a R̂(a)`; that is ablation A2.
7. **Closed-loop verification.** After executing `a*`, observe `S_{t+Δ}`, record the error and feed it to drift monitoring. The frozen `τ̂` is not recalibrated online because outcomes of rejected actions are unavailable.

## 7. The methodological contribution: reconstructible fork-and-replay

At selected decision points the run is reconstructed **from its own prefix** — master seed, per-component RNG streams, scenario config, workload and fault schedules, and the action history up to `t` — and re-executed with only the action at `t` replaced. Reconstruction, not snapshotting: congestion windows, goroutine schedules, broker buffers and in-flight packets cannot be captured faithfully, and a claim to have done so would not survive review.

The results are **replay-based empirical reference outcomes**, not counterfactual ground truth. That wording is deliberate and is used consistently in the manuscript.

**The predicted and observed objectives are separate quantities**, and conflating them was a real defect in v1:

- predicted: `Ĵ(a) = λ_F·R̂(a) + λ_L·L̂(a) + λ_C·Ĉ(a)`
- observed: `J_obs(a) = λ_F·Y^a + λ_L·L̃^a + λ_C·C_obs^a`

`J_obs` contains no model output. If it did, the reference ranking would contain the very prediction it exists to test, and the ranking metric would be measuring the model against itself.

Metrics, with ties resolved by the measured dispersion band `η_J` (§10 of the protocol):

- **CRA_η**: fraction of decisions where `J_obs(a*) ≤ min_a J_obs(a) + η_J`
- **Regret_η**: `max(0, J_obs(a*) − min_a J_obs(a) − η_J)`

Exact-argmin CRA is not used: under residual nondeterminism it would penalise the controller for picking between two actions the environment cannot distinguish.

## 8. Contributions (as they will appear in the Introduction)

1. Counterfactual Shadow Control: online comparison of multiple intervention-conditioned futures before modifying a running mobile-edge IoT system.
2. Minimum-necessary intervention as cost-minimal selection from an admissible set whose *set-level* risk is calibrated at a declared level — a formulation that is unaffected by the controller choosing adaptively among candidates — with guarded abstention and a predetermined fallback outside the guarantee.
3. A reconstructible fork-and-replay methodology with transport-quiescent exact anchors, yielding empirical reference outcomes for alternative recovery actions, a measured resolution `η_J`, and tie-aware ranking and regret.
4. A distributed Go/Python prototype and a systematic evaluation against reactive, predictive, graph-based, and RL controllers under degradation, mobility, overload, node failure, cascading faults, and scenario shift.

## 9. Evaluation design (summary; authoritative version in EXPERIMENT_PROTOCOL.md)

- Scenarios F1–F7 (degradation, latency, overload, congestion, mobility/handover, node failure, cascade).
- Controllers B1 threshold · B2 GRU+heuristic · B3 graph predictor · B4 PPO · B5 CSC-Predict (CSC minus counterfactual reasoning) · B6 CSC.
- Ablations A1 no uncertainty gate · A2 no MNI (risk-argmin) · A3 no causal intervention layer.
- ≥20 paired seeds per configuration (30 preferred); every controller sees the identical seed-specific realization.
- Primary metrics: PFR, WIR, FLT, availability, SLA violation rate, intervention cost, p50/p95/p99 latency, decision overhead, CRA, CRA@2, regret. AUPRC and calibration error are secondary.
- 95% bootstrap CIs, paired Wilcoxon, effect sizes, Holm correction.

## 10. Definition of done

Submission is not considered until all of: real distributed Go prototype; kernel-level network emulation (with the fallback path clearly labelled where unprivileged); fork-and-replay empirical reference outcomes with a measured resolution `η_J`; ≥4 fair baselines; ≥20 paired seeds; CIs and effect sizes; scenario-shift evaluation; three ablations; runtime overhead table; scalability curve; public code and configs; zero unverified references; zero manually typed numbers in the Results section.

## 11. Explicit non-goals

No blockchain, no LLM component, no federated learning, no 6G branding, no quantum, no digital twin, no separate "explainable AI" module, and exactly one network emulation stack. Each of these would dilute the contribution and none of them answers RQ1–RQ4.

## 12. Amendment log

| Date | Change | Reason |
|---|---|---|
| 2026-08-25 | Initial freeze. Novelty reframed away from "causal self-healing" toward MNI + fork-and-replay after AURORA (arXiv:2605.10718) was found. | NOVELTY_AUDIT.md §3.1 |
| 2026-08-25 | **v2 methodology correction.** Conformal prediction bound → conformal risk control; Proposition 1 removed; SCM made dynamic; `Ĵ`/`J_obs` separated; `η_J` and tie-aware metrics; H3 non-inferiority; H4 tail; B5 redefined. | `METHODOLOGY_CORRECTION_REPORT.md` |
