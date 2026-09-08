# EXPERIMENT_PROTOCOL.md

Pre-registered protocol for CSC. **Everything in §2–§9 is frozen before the main experiments are run.** Changing a frozen value after seeing comparative results invalidates the run set; the correct response is a dated amendment in §12 plus a full re-run.

Protocol version: **0.3** (distributed replay repair, 2026-09-05). Becomes 1.0 at implementation freeze, after the pilot in §11.

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

## 12. Amendment log

| Date | Change | Reason |
|---|---|---|
| 2026-08-25 | Draft 0.1 created. | Project start |
| 2026-08-25 | **0.2 methodology correction.** Conformal *prediction* upper bound replaced by conformal *risk control* on a set-level loss; `α` collision removed; `Ĵ` separated from `J_obs`; `η_J`, tie-aware CRA and regret introduced; PFR/WIR given set-theoretic definitions; H3 made a non-inferiority test; H4 moved from median to p95 and deadline-miss rate; F6 split contradiction resolved; B5 redefined as an action-conditioned associative predictor; randomised behaviour policy added on training scenarios; D0 audit replaces per-branch 30× replication. | External review; see `METHODOLOGY_CORRECTION_REPORT.md` |
| 2026-09-05 | **0.3 distributed replay repair.** All expected producers must close an epoch; action application requires a run-scoped acknowledgement; every branch starts from a recreated topology; fingerprint coverage is enumerated; D0-lite fixes `SNR_J ≥ 3` and the `η_J=0` edge case; `J_m2_diag` is quarantined from `J_obs`; netem direction and seed are fixed. | 48-run prefix burn-in and 108-branch mechanics pilot; diagnostics only, never reused as findings. |
