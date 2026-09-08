# CLAIM_EVIDENCE.md

Every substantive claim in the manuscript, and what backs it. Rebuilt whenever
the manuscript changes; a claim with no evidence column is a claim to delete or
soften, not a claim to defend.

Status legend: **held** = supported now · **pending** = will be supported by a
named experiment · **cited** = rests on a verified reference.

---

## Introduction

| Claim | Evidence | Status |
|---|---|---|
| Mobile-edge failures develop as a chain rather than an instant | F1/F7 scenario design; retry-amplification path in `internal/sim` | held (design), pending (data) |
| Reactive recovery acts only after the agreement is broken | definitional; B1 is the instance | held |
| A failure probability does not say which intervention helps | §III-B separates `P(F\|S)` from `P(F\|S,do(a))`; distinct code paths and log fields | held |
| Recent causal pipelines diagnose but do not price actions | `ye2026nesyedge`, `desilva2026aurora`; per-cell audit in `docs/table1_evidence.csv` | cited |
| RL controllers price actions inside a fixed reward | `siew2022fire` | cited |
| Validation in nondeterministic runtimes is an open problem | `bonilla2026slr` (99 studies) | cited — **abstract wording read by a co-author, not from the build environment; re-check once before submission** |
| The same action helps in one state and harms in another | M2: anchor 60 no-op fails and REROUTE saves it; anchors 70–150 no-op is safe and REROUTE causes failure | held (development core) |

## Method

| Claim | Evidence | Status |
|---|---|---|
| The SCM is dynamic, not a static DAG | eq. (3); rollout over `H = Δ/tick` | held (formulation), pending (implementation) |
| REROUTE is a compute-path intervention and does not alter loss or retries | M2 branch table: retries identical for NO_OP and REROUTE at every anchor (1364/1364, 1704/1704, …) | **held — measured** |
| `Û` filters and is not itself calibrated | §III-D; bootstrap quantile width; `U_max` chosen on validation only | held |
| The set-level loss is monotone in τ | `crc.py::calibrate` rejects non-monotone input; unit test | **held — enforced in code** |
| The guarantee survives adaptive selection among five actions | pointwise domination of the selected action's failure indicator by the set-level loss when the set is non-empty | held (argument) |
| The finite-sample correction matters at n=20 | `test_correction_is_material_at_realistic_n` pins ≈0.048 | **held — tested** |
| The guarantee holds on held-out runs | `test_guarantee_holds_on_held_out_runs`, 200 synthetic trials | held (synthetic) |
| CRC says nothing about the fallback | loss is 0 when the admissible set is empty, by construction; fallback rates reported separately | held |
| τ̂ cannot be updated online in deployment | the loss needs `Y^a` for actions not taken | held (argument) |

## Replay

| Claim | Evidence | Status |
|---|---|---|
| Reconstruction, not snapshotting | `internal/replay`; no process state is captured | held |
| Anchors are reproducible from their own inputs | `TestBranchesShareTheirPrefix` | **held — tested** |
| A branch re-executes identically | `TestBranchIsReproducible` | held (single-process core) |
| Actions reach real system state | `TestActionsReachSystemState`; topology smoke: REROUTE moves traffic edge01 0 → 1279 across processes | **held — measured** |
| A dispatched action that changes nothing is excluded | `state_mutated` per branch; runner fails on inert non-NO_OP branches | **held — enforced** |
| Local ACK is insufficient on an async bus | `TestUndrainedTransportBlocksTheAnchor` (97 of 100 consumed → anchor refused) | **held — tested** |
| Equal queue depth is insufficient | `TestSameDepthDifferentContentsIsCaught` | **held — tested** |
| Every future-relevant field is in the fingerprint | `TestLatentStateIsCovered` walks retry, backoff, tokens, timeouts, placement, replicas, migration, capacity, transport | **held — tested** |
| `η_J` belongs to one runtime stack | `RuntimeStack.ID()`; `TestRuntimeStackIDChangesWithTransport` | **held — tested** |
| Branch divergence is real | M2: 10/10 anchors action-dependent | held (development core) |

## Results

Every row here is **pending**. No experiment has been run; `analysis/` generates
each number from `results_long.csv` and the manuscript uses `\input`. The
scaffold names what each subsection must report, including where a hypothesis
fails.

| Claim | Experiment that will settle it |
|---|---|
| H1 CSC prevents more failures | common-anchor PFR across B1–B6 |
| H2 the gate lowers WIR under shift | A1 ablation on F5–F7 common anchors |
| H3 MNI lowers cost, non-inferior availability | A2 ablation, one-sided test at `Δ_A=0.005` |
| H4 tail latency within budget | scale runs, `p95(T_dec)` and deadline-miss rate |
| Replay resolves action differences | D0-lite, `SNR_J ≥ 3` |
| The causal layer earns its place | B5, the action-conditioned supervised predictor |

## Claims deliberately NOT made

- Not "the first causal self-healing framework" — false; `desilva2026aurora`.
- Not "we introduce abstention" — false; same.
- Not "counterfactual ground truth" — replay-based empirical reference outcomes,
  at resolution `η_J`.
- Not "safe abstention" — guarded abstention; the fallback is outside the guarantee.
- Not "gRPC" or "NATS" — the manuscript says typed RPC boundary and message bus;
  concrete implementations live in the manifest, and neither has passed local
  validation yet.
- Not "Prometheus metrics" — removed; `grep -ri prometheus --include='*.go'`
  returns nothing.
- Not a measured RF SINR — `link_quality` is an abstract [0,1] score.
- No `η_J` from the in-process core or the stdlib broker will be reported.
