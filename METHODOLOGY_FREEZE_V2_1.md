# METHODOLOGY_FREEZE_V2_1.md

**Frozen 2026-08-25.** No further methodology edits before pilot results. The
largest remaining risk in this project is no longer a formula — it is whether
`η_J` turns out small enough for replay to resolve action differences at all.
That is answered by running the thing, not by another revision.

Supersedes the v2 state described in `METHODOLOGY_CORRECTION_REPORT.md`.

---

## 1. Objects and symbols

| Symbol | Meaning | Fixed by |
|---|---|---|
| `S_t = (G_t, X_t)` | state: dependency graph + windowed telemetry | — |
| `A = {a₀…a₄}` | no-op, reroute, migrate, throttle, replicate | — |
| `R̂(a\|S_t)` | predicted interventional risk, from the SCM rollout | model |
| `Û(a\|S_t)` | epistemic disagreement, eq. (U) below | model ensemble |
| `Ĉ(a)` | normalised intervention cost | `configs/cost.yaml` |
| `τ̂` | admissibility threshold — **CRC-calibrated, then frozen** | calibration |
| `U_max` | uncertainty filter bound — **validation only** | validation |
| `δ` | CRC risk level = 0.10 | `configs/calibration.yaml` |
| `η_J` | replay dispersion band | D0 audit — **TBD** |
| `λ_F, λ_L, λ_C` | objective weights = 0.6, 0.2, 0.2 | `configs/objective.yaml` |
| `Δ_A` | availability non-inferiority margin = 0.005 | `configs/objective.yaml` |
| `Δ`, `H` | horizon, rollout steps `Δ/tick` | validation — **TBD** |
| `B` | bootstrap replicas = 20 | validation, pilot-checked |

`α`, `β`, `γ` and `R_safe` are retired and must not reappear.

## 2. Final equations

**Dynamic SCM.**  `X_{j,t+1} = g_j(Pa_j(X_t), A_t, u_{j,t})`

**Interventional risk.**  `R(a|S_t) = Pr_{M_a}[ ∪_{h≤H} {F^a_{t+h}=1} | do(A_t=a), S_t ]`, by rollout with sampled noise.

**Uncertainty (U).**  With `B` bootstrap replicas of the structural model,

```
Û(a|S_t) = Q_0.95{ R̂_b(a|S_t) } − Q_0.05{ R̂_b(a|S_t) }
```

A quantile width, not a standard deviation: a few divergent replicas should not dominate the filter.

**Admissible set.**  `A_safe(τ) = { a : R̂(a|S_t) ≤ τ ∧ Û(a|S_t) ≤ U_max }`

Two distinct operations. `Û` **filters**; it is not itself calibrated. `τ` is **calibrated**. The correct phrase is *uncertainty-filtered, risk-calibrated admissible set*; "calibrated uncertainty gating" would be false.

**Within-run set-level loss.**  For calibration run `i` with pre-declared anchors `T_i`:

```
L_i(τ) = (1/|T_i|) · Σ_{t∈T_i} 1[ ∃ a ∈ A_safe_it(τ) : Y^a_it = 1 ]
```

`L_i ∈ [0,1]`, non-decreasing in `τ`. `Y^a_it` comes from the replay branch.

**Selection.**  `a* = argmin_{a∈A_safe(τ̂)} Ĉ(a)`, else `a_fb`.

**Objectives.**  `Ĵ(a) = λ_F R̂(a) + λ_L L̂(a) + λ_C Ĉ(a)` (model) and `J_obs(a) = λ_F Y^a + λ_L L̃^a + λ_C C_obs^a` (replay only — no model output, ever).

**Metrics.**  `CRA_η`, `Reg_η`, `PFR = N_prev/N_pre`, `WIR = N_harm/N_int`, all tie-resolved at `η_J`; `T_dec` reported at p95 with deadline-miss rate.

## 3. Exact CRC procedure

Implemented in `intelligence/conformal/crc.py`, tested in `intelligence/tests/test_crc.py` (6 tests, including an empirical check that the guarantee holds on held-out runs).

```
Input: calibration runs i = 1..n, threshold grid τ₁ < … < τ_m, level δ, B_loss = 1
1. for each i, τ_j:  L_i(τ_j)  = within-run set-level loss
2. for each τ_j:     R̂_n(τ_j) = (1/n) Σ_i L_i(τ_j)
3. for each τ_j:     corrected(τ_j) = (n·R̂_n(τ_j) + B_loss) / (n + 1)
4. τ̂ = max { τ_j : corrected(τ_j) ≤ δ }        ← LARGEST, not smallest
5. if no τ_j qualifies: τ̂ = None → abstain everywhere, and report that
```

Step 4 takes the largest because `A_safe` grows with `τ`: among thresholds meeting the risk level, the widest admissible set leaves the cost rule the most room. Step 3 is not optional — at `n = 20` the correction `B/(n+1) ≈ 0.048` is the same order as `δ` itself, and a test asserts it does not silently shrink.

**Calibration unit is an independent run, not a decision point.** Decision points inside a run are temporally dependent. Independent seeds give exchangeable runs.

## 4. What is claimed, and what is not

**Claimed.** `E[L_{n+1}(τ̂)] ≤ δ` over a future exchangeable run: the expected within-run rate of admissible sets containing a failure-inducing action. Because it constrains the whole set, it bounds the failure probability of *any* rule selecting from it — which is what makes it survive the controller choosing adaptively among five scored candidates.

**Not claimed.**

- No per-decision or conditional statement, and nothing about the latent `R(a|S_t)`.
- **Nothing about the fallback.** When `A_safe(τ̂) = ∅` the loss is zero by construction whatever the fallback then does. Fallback rate, fallback failure rate and fallback SLA-violation rate are measured and reported separately. The sentence "CRC controls overall system failure probability" is false and must not appear.
- **No online recalibration in the deployed loop.** Updating the set-level loss needs `Y^a` for actions the system did not take. A production edge system cannot observe those. `τ̂` is calibrated offline and frozen; under shift it is carried over and realised empirical risk is reported instead of a guarantee. A replay-assisted recalibration experiment may be added, labelled as requiring a reconstructible environment.
- Post-execution error `ε_t` drives drift detection and is reported as calibration decay. It does not move `τ̂`.

## 5. Splits and training data

- train / validation / calibration: F1–F4, disjoint seed blocks
- ID test: F1–F4, new seeds **and** new parameter values
- scenario shift: F5, F6, F7, combined — no selection decision of any kind
- `U_max` and `B`: validation only. `τ̂`: calibration only. Neither touches test.

**Interventional training data comes from exhaustive replay, not a behaviour policy.** At training anchors every action is executed in its own branch, giving `(S_t, a, S^a_{t+1}, Y^a)` for all `a` — assignment forced rather than sampled. This is a designed experiment on the emulator and removes the need for propensity weighting; the randomised behaviour policy of v2 is retired as redundant, per "prefer the simpler scientifically justified design". Test branch outcomes are visible to no model, and a leakage test enforces it.

## 6. Two evaluation layers

Controllers that intervene diverge, so their preventable-failure populations diverge too. Comparing them on controller-specific denominators would not be an equal comparison.

| Layer | Question | Metrics |
|---|---|---|
| Common-anchor decision benchmark | Did it choose the right intervention? | `CRA_η`, `Reg_η`, common-anchor PFR/WIR, action cost — shared denominator |
| Closed-loop benchmark | Did those choices improve the system? | availability, SLA violation rate, failure count, p99, cost, resource use, abstention/fallback |
| D0 replay audit | Can the emulator tell the alternatives apart? | `η_J`, between-action spread |
| Shift benchmark | Does calibration degrade safely? | realised set-level risk vs `δ`, abstention |
| Scale benchmark | Is the overhead practical? | p95 `T_dec`, deadline misses, CPU, RAM |

## 7. Hypotheses

- **H1** CSC beats B1–B5 on common-anchor PFR.
- **H2** The calibrated gate lowers WIR on shift relative to A1.
- **H3** MNI lowers intervention cost versus A2 **and is non-inferior** on availability at `Δ_A = 0.005`, by a one-sided paired test. Rationale for 0.005: half a percentage point over a 300 s window is roughly 1.5 s of extra unavailability, below the granularity at which the agreement is enforced. Sensitivity over {0.001, 0.0025, 0.005, 0.01} in the supplement; the primary claim is at 0.005 only.
- **H4** `p95(T_dec) < 100 ms` up to 10,000 devices, deadline-miss rate < 1%.

## 8. Known before Phase A / TBD

Fixed: `δ=0.10`, `λ=(0.6,0.2,0.2)`, `w=0.25` each (neutral default, not "conservative"), `Δ_A=0.005`, tick 500 ms, telemetry 100 ms, 120/300/60 s run shape, ≥20 paired seeds, `B=20`, D0 = 20×5×30.

**TBD, and to be measured rather than guessed:** `η_J`, `τ̂`, `U_max`, `Δ` and `H`, the branch-repeat count for the main experiment, and whether the 100 ms p95 budget is consistent with the tick.
