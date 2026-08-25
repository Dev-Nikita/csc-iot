# RESEARCH_SPEC.md — Counterfactual Shadow Control (CSC)

Target venue: **IEEE Internet of Things Journal**, regular paper.
Page target: **6.0 published pages including references** (hard ceiling 8 — beyond that IEEE overlength charges apply; the 2-page headroom is reserved for revision, not for the first submission).
Status: specification frozen for implementation start, 2026-08-25. Amendments require a dated entry in §12.

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
- **RQ2** Does calibrated uncertainty gating reduce harmful interventions under scenario-level distribution shift?
- **RQ3** Does minimum-necessary intervention lower intervention cost without a statistically significant loss of availability?
- **RQ4** What runtime overhead does shadow evaluation add as the device count grows?

## 4. Hypotheses (registered before any comparative result is examined)

- **H1** CSC achieves a higher Prevented Failure Ratio than B1–B5.
- **H2** The uncertainty gate lowers Wrong Intervention Rate on OOD scenarios (F5, F7, combined) relative to CSC without the gate (ablation A1).
- **H3** Minimum-necessary intervention lowers mean intervention cost relative to risk-argmin selection (ablation A2) with no significant availability regression (equivalence margin declared in EXPERIMENT_PROTOCOL.md).
- **H4** Median decision overhead stays within the budget declared in EXPERIMENT_PROTOCOL.md up to 10,000 virtual devices.

**A hypothesis that fails is reported as failed.** H1–H4 are predictions, not targets. No experiment is re-run, re-tuned, or re-seeded because its outcome was unwelcome.

## 5. System model

Devices `D = {d_1..d_N}`, edge nodes `E = {e_1..e_M}`, services `V = {v_1..v_K}`.
State `S_t = (G_t, X_t)` where `G_t` is the dependency graph (device → gateway → link → edge node → broker → service) and `X_t` the windowed telemetry tensor over node features.

Candidate actions, deliberately five:
`a0` no-op · `a1` reroute · `a2` migrate workload · `a3` throttle source rate · `a4` activate replica.

## 6. Method

1. **Temporal predictor.** GRU or TCN over graph-aggregated node features → `P(F_{t+Δ})`. Horizon Δ selected on the validation split before any test evaluation; the choice and its justification are recorded. Architecture is deliberately unremarkable — it is not the contribution.
2. **Topology-informed SCM.** Structure fixed by system semantics, parameters learned:
   `Mobility → LinkQuality → PacketLoss → RetryRate → QueueDepth → Latency → TimeoutRate → ServiceFailure`, with `EventRate → QueueDepth` and `Load → ProcessingTime → QueueDepth`.
   Unrestricted causal discovery is not used and not claimed. Identification assumptions are stated explicitly in the paper.
3. **Counterfactual evaluation.** For each `a ∈ A`, estimate `R_a = P(F_{t+Δ} = 1 | S_t, do(A = a))`. The implementation must keep `P(F|S)` and `P(F|S, do(a))` as distinct code paths and distinct log fields — a reviewer will look for exactly this.
4. **Cost model.** `C(a) = w_L·L_a + w_R·E_a + w_B·B_a + w_D·D_a`, each term normalized to [0,1]. **Weights are fixed in version control before the main experiments and are never tuned against results.**
5. **Calibration.** Conformal / adaptive-conformal upper risk bound `R⁺(a)`. Empirical coverage is measured and reported, including where it degrades.
6. **Minimum-necessary intervention.**
   `a* = argmin_a C(a)` subject to `R⁺(a) ≤ R_safe` and `U(a) ≤ U_max`.
   If the feasible set is empty → `a_fallback` (safe abstention).
   The controller must **never** silently fall back to `argmin_a R_a`; that path is ablation A2, not the method.
7. **Closed-loop verification.** After executing `a*`, observe `S_{t+Δ}`, record `e = |Ŷ^{a*} − Y|`, feed it to calibration and drift monitoring.

## 7. The methodological contribution: deterministic fork-and-replay

At selected decision states `S_t`, the environment is reconstructed deterministically (same seed, same workload trace, same fault schedule, same network and service state) and **each** candidate action is executed in its own branch. The observed branch outcomes are the experimental counterfactual ground truth against which the predicted ranking is scored.

This answers the question that sinks most counterfactual systems papers — *how do you know the unchosen futures?* — and it enables two metrics no prediction-quality metric can substitute for:
- **Counterfactual Ranking Accuracy** (CRA, and CRA@2): how often the model's best action is the actually-best action.
- **Action regret**: `J(a_selected) − J(a_optimal)`, with `J(a) = α·R(a) + β·L(a) + γ·C(a)` and α, β, γ fixed in advance.

Determinism will be imperfect. The paper must quantify residual nondeterminism (branch-to-branch outcome variance under the *same* action and seed) and report it as a limitation, not hide it. Implementation is by deterministic environment reconstruction from logged state and configuration — **not** by pretending to snapshot container memory.

## 8. Contributions (as they will appear in the Introduction)

1. Counterfactual Shadow Control: online comparison of multiple intervention-conditioned futures before modifying a running mobile-edge IoT system.
2. Minimum-necessary intervention as constrained selection over calibrated counterfactual risk and intervention cost, with safe abstention when no action is reliably sufficient.
3. A deterministic fork-and-replay methodology yielding experimental ground truth for alternative recovery actions, and the ranking/regret metrics it makes possible.
4. A distributed Go/Python prototype and a systematic evaluation against reactive, predictive, graph-based, and RL controllers under degradation, mobility, overload, node failure, cascading faults, and scenario shift.

## 9. Evaluation design (summary; authoritative version in EXPERIMENT_PROTOCOL.md)

- Scenarios F1–F7 (degradation, latency, overload, congestion, mobility/handover, node failure, cascade).
- Controllers B1 threshold · B2 GRU+heuristic · B3 graph predictor · B4 PPO · B5 CSC-Predict (CSC minus counterfactual reasoning) · B6 CSC.
- Ablations A1 no uncertainty gate · A2 no MNI (risk-argmin) · A3 no causal intervention layer.
- ≥20 paired seeds per configuration (30 preferred); every controller sees the identical seed-specific realization.
- Primary metrics: PFR, WIR, FLT, availability, SLA violation rate, intervention cost, p50/p95/p99 latency, decision overhead, CRA, CRA@2, regret. AUPRC and calibration error are secondary.
- 95% bootstrap CIs, paired Wilcoxon, effect sizes, Holm correction.

## 10. Definition of done

Submission is not considered until all of: real distributed Go prototype; kernel-level network emulation (with the fallback path clearly labelled where unprivileged); fork-and-replay counterfactual ground truth; ≥4 fair baselines; ≥20 paired seeds; CIs and effect sizes; scenario-shift evaluation; three ablations; runtime overhead table; scalability curve; public code and configs; zero unverified references; zero manually typed numbers in the Results section.

## 11. Explicit non-goals

No blockchain, no LLM component, no federated learning, no 6G branding, no quantum, no digital twin, no separate "explainable AI" module, and exactly one network emulation stack. Each of these would dilute the contribution and none of them answers RQ1–RQ4.

## 12. Amendment log

| Date | Change | Reason |
|---|---|---|
| 2026-08-25 | Initial freeze. Novelty reframed away from "causal self-healing" toward MNI + fork-and-replay after AURORA (arXiv:2605.10718) was found. | NOVELTY_AUDIT.md §3.1 |
