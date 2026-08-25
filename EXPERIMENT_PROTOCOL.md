# EXPERIMENT_PROTOCOL.md

Pre-registered protocol for CSC. **Everything in §2–§9 is frozen before the main experiments are run.** Changing a frozen value after seeing comparative results invalidates the run set; the correct response is a dated amendment in §12 plus a full re-run.

Protocol version: 0.1 (draft — becomes 1.0 at implementation freeze, after the pilot in §11).

---

## 1. Terminology

- **Failure event `F`**: an SLA violation window — end-to-end p99 latency above the SLA bound, or delivery success below the SLA bound, sustained for ≥ `f_dur`. Exact bounds: `experiments/configs/sla.yaml`.
- **Preventable failure**: a failure that occurred in the no-op replay branch from the same decision state. Only preventable failures enter the PFR denominator.
- **Harmful intervention**: an executed action whose replayed branch objective `J` is worse than the no-op branch objective from the same state, beyond the residual-nondeterminism band measured in §10.
- **Decision state**: a controller tick at which the risk of any candidate exceeds the evaluation trigger.

## 2. Frozen constants

| Symbol | Meaning | Value | File |
|---|---|---|---|
| `Δ` | prediction horizon | selected on validation from {2 s, 5 s, 10 s}; frozen thereafter | `configs/model.yaml` |
| `R_safe` | safety threshold on the upper risk bound | 0.20 | `configs/controller.yaml` |
| `U_max` | max admissible interval width | 0.25 | `configs/controller.yaml` |
| `1-α` | conformal target coverage | 0.90 | `configs/calibration.yaml` |
| `w_L,w_R,w_B,w_D` | cost weights | 0.25 each (uniform prior; sensitivity in supplement) | `configs/cost.yaml` |
| `α,β,γ` | objective weights in `J` | 0.6, 0.2, 0.2 | `configs/objective.yaml` |
| `n_seeds` | paired seeds per configuration | 20 (target 30) | `configs/runs.yaml` |
| run shape | warm-up / measurement / cooldown | 120 s / 300 s / 60 s | `configs/runs.yaml` |
| tick | controller decision period | 500 ms | `configs/controller.yaml` |
| telemetry | sampling period | 100 ms | `configs/telemetry.yaml` |

Uniform cost weights are a deliberate choice: any other setting invites the accusation that the weights were chosen to make MNI look good. The sensitivity sweep over `R_safe ∈ {0.1, 0.2, 0.3, 0.4}` and over non-uniform weights goes in the supplement.

## 3. Scenarios

| ID | Scenario | Primary driver | Split |
|---|---|---|---|
| F1 | gradual link degradation, loss 0% → 20% | network | train/ID |
| F2 | latency inflation, RTT 10 → 250 ms | network | train/ID |
| F3 | edge compute overload, CPU 30% → 95% | compute | train/ID |
| F4 | queue congestion, λ > μ | compute | train/ID |
| F5 | mobility with gateway handover | mobility | **OOD** |
| F6 | abrupt edge-node failure | availability | ID (test only) |
| F7 | cascading failure (mobility → loss → retries → queue → latency → timeout → retry storm → SLA failure) | combined | **OOD** |

All parameters in `experiments/scenarios/F*.yaml`. F7 is the showcase experiment and drives Figure 3.

## 4. Controllers

`B1` reactive threshold · `B2` GRU prediction + heuristic recovery rule · `B3` graph-based predictor + same heuristic · `B4` PPO · `B5` CSC-Predict (identical predictor and features, action scored observationally, no `do()`) · `B6` CSC.

Fairness constraints, all enforced in code and asserted in tests:
- identical telemetry features and identical observation window for every learned controller;
- identical action set and identical execution mechanism;
- comparable hyperparameter search budget (fixed trial count, recorded per controller);
- no controller receives future information; B6 receives no privileged signal absent from B5.

## 5. Ablations

`A1` CSC without the uncertainty gate (point risk vs `R_safe`) · `A2` CSC without MNI (`argmin_a R_a`) · `A3` CSC without the causal layer (observational action scoring) · `A4` (optional) CSC without closed-loop recalibration.

## 6. Data splitting

Split by **run**, never by row. Telemetry within a run is temporally correlated; row-level shuffling would leak and a reviewer will check for it.
- train: F1–F4, seed block A
- validation: F1–F4, seed block B (horizon and hyperparameter selection only)
- calibration: F1–F4, seed block C (disjoint from train and validation)
- ID test: F1–F4 and F6, seed block D
- OOD test: F5, F7, combined faults — **never** used for training, calibration, or any selection decision.

Replay-branch data is quarantined from all model training. A leakage test in `intelligence/tests/` must fail the build if a replay-derived record appears in a training set.

## 7. Seed pairing

Seed `s` defines the workload trace, the fault schedule, mobility, and all environment randomness. Every controller and every ablation is run at the same `s`. Analysis is paired throughout. Seed sets must be identical across methods; `analysis/validate_results.py` fails the pipeline otherwise.

## 8. Exclusion policy (declared before any results are viewed)

A run is excluded only for a documented **technical** failure: container OOM-kill, orchestration crash before the measurement window ends, fault injector reporting a non-applied schedule, or clock anomaly. Every exclusion is logged in `experiments/manifests/exclusions.csv` with run ID, reason, and evidence. Exclusions are reported as a count in the paper. **No run is ever excluded on the basis of its outcome.** If exclusions exceed 5% of any configuration, the whole configuration is re-run and both attempts are reported.

## 9. Statistics

Per-seed observations are stored raw. For each primary comparison: 95% bootstrap CI (10,000 resamples), paired Wilcoxon signed-rank, effect size (Cliff's delta or rank-biserial), Holm correction across the primary pairwise family. p-values are never reported alone. The equivalence margin for the H3 availability non-inferiority claim is declared in `configs/objective.yaml` before the main runs.

## 10. Determinism validation

Before any counterfactual claim is made: run the same state and the same action across ≥30 replay branches and measure outcome dispersion. This band defines the resolution of every fork-and-replay result and must be reported in the paper. If the band is wide enough to swallow the differences between actions, the replay methodology is not yet usable and implementation returns to Phase 4 — this is a hard gate.

## 11. Pilot before freeze

A reduced pilot (100 devices, F1/F3/F7, 5 seeds, B1/B2/B6) runs before protocol 1.0 in order to expose methodological problems while changing them is still legitimate. Pilot results are **never** reported as findings and never re-used as evidence.

## 12. Amendment log

| Date | Change | Reason |
|---|---|---|
| 2026-08-25 | Draft 0.1 created. | Project start |
