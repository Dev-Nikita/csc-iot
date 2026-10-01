# Measured results, b5-matrix-v2

Stack `161b4e3893c01695`, scenario set hash `80abe923207bb31c`, 115 design points,
6210 branches, 2026-10-01. Full report: `data/derived/b5-matrix-v2-report.txt`.
Every number here is read from that report, written before the manuscript sections
were rewritten so the interpretation could not drift toward what the paper needs.

## The four gates, in the order the protocol fixes them

**Accounting audit — passed.** 6210 branches, zero violations. The
degradation-effect bound binds on 3672 of them; the rest end before their onset.

**Replay resolution.** 764 of 1380 contrasts clear the preregistered pooled gate
(0.554). Under all four bands 187 survive (0.136), the worst-cell band being the
binding one. Contrasts below the gate are not null effects; they are effects this
design cannot separate from replay dispersion.

**Leakage — both tests passed.** Held out by design point: telemetry kNN 0.0268,
time-only `f(t,a)` 0.1287, predict-the-mean 0.2030, s.d. of `J_obs` 0.2324. The
telemetry cuts the time-only error by 79.1% against a required 20%. Permuting
telemetry across scenarios raises the error to 0.1692. A linear fit is worse than
a constant (0.2933): the relationship is non-linear, not absent.

**Transfer.** On spanning branches: design-point holdout 0.0396, regime holdout
0.0480, strict holdout (no spanning branch, unseen fault setting) 0.0479, against
0.1716 for a constant. Strict is 1.21x the design-point error.

## The structural model

**The preregistered sign test passes: 187 of 187 resolvable contrasts, 1.000** —
137/137 pre-fault, 44/44 spanning, 6/6 post-onset. Windowed observables present in
200 of 200 anchors sampled. MAE 0.0574 overall (pre-fault 0.0891, spanning 0.0631,
post-onset 0.0408), with no fitted parameters.

The before-and-after is the result. On the same test with cumulative counters only,
the model reproduced 190 of 203 signs and failed 13, every one of them the
admission-cap action at the earliest anchor. Adding a windowed arrival rate and a
windowed service rate — protocol 0.10 — takes that to zero failures. Magnitudes
stay biased low, typically about half the observed contrast, which the sign test
does not score and the paper states.

## Conformal risk control

`tau_hat` = 0.0447 from 20 calibration runs. Empirical loss 0.0000, corrected
0.0476, against the declared `delta` = 0.10. The guarantee holds as stated.

## Decision methods — the method does NOT beat the baselines here

| split | method | CRA_eta | acted | CRA given it acted | abst | PFR | WIR |
|---|---|---|---|---|---|---|---|
| ID | B1 threshold | 1.000 | 60/60 | 1.000 | 0.000 | 1.000 | 0.000 |
| ID | B6 CSC | 0.633 | 38/60 | 0.974 | 0.367 | 0.714 | 0.000 |
| param | B1 threshold | 1.000 | 180/180 | 1.000 | 0.000 | 1.000 | 0.000 |
| param | B6 CSC | 0.583 | 111/180 | 0.946 | 0.383 | 0.760 | 0.000 |
| mech | B1 threshold | 0.993 | 138/138 | 0.993 | 0.000 | 1.000 | 0.007 |
| mech | B6 CSC | 0.399 | 61/138 | 0.885 | 0.558 | 0.607 | 0.023 |

The oracle bound is 1.000 on all three splits and **a one-line reactive threshold
reaches it** in-distribution and under parameter shift, 0.993 under mechanism
shift. Four readings follow and all four belong in the paper.

**The decision problem in this testbed is too easy.** Rerouting is almost always
the best action and a threshold on the windowed service deficit finds it. When a
baseline attains the oracle bound the common-anchor layer has no discriminating
power. That is a statement about the testbed, not evidence against the method.

**When CSC acts it is near-oracle: 0.974, 0.946, 0.885.** Its deficit is entirely
abstention, not misprediction, and its wasted-intervention rate is 0.000, 0.000
and 0.023.

**The gate is over-conservative by construction at the declared levels.** At
`theta` = 0.0602, 797 of 1080 calibration branches count as failures. Equation (8)
asks that no admissible action be failure-inducing, so holding that loss at zero
forces `tau` below the risk of any failing action and almost nothing is
admissible. The manuscript already warns the guarantee does not cover abstention,
an empty admissible set having loss zero by construction. This run lands in that
corner. `delta`, `theta` and `tau_hat` were declared before any test split was
examined and are not changed now.

**Guarded abstention assumes the fallback is a safe default, and here it is not.**
The fallback is inaction, inaction is the dominant failure mode in this regime,
and so every abstention pays the full regret. That is a condition on where the
method applies — a result, not an excuse.

## Two ablations, read honestly

**The uncertainty filter is inert on this matrix.** A1a, which removes it and keeps
the calibrated threshold, equals B6 on every split and every metric. Mean ensemble
uncertainty is 0.064-0.096 against `U_max` = 0.15, so the filter never binds. A1a
is reported as uninformative here rather than as agreement.

**Minimum-necessary intervention costs accuracy under mechanism shift.** A2, which
takes the lowest-risk admissible action instead of the cheapest, reaches 0.951
where B6 reaches 0.885, with PFR 0.750 against 0.607. With only disruption
instrumented, rerouting normalises to cost 0.000 — the same as inaction by
definition — so the cost rule cannot separate acting from not acting. That
degeneracy is a property of the measured action set; a third priced action is what
would make the ordering informative.

**A1b, no gate at all, is degenerate by construction** (0.533 / 0.461 / 0.254):
with inaction costing zero the cost rule always chooses it. That is the argument
for the gate, not a competitor performing badly.

## What this supports and what it does not

Not supported on this matrix: that CSC improves decision quality over baselines.
H1 and H2 fail here, for the reason diagnosed above.

Supported: the measurement methodology, with gates that did fail and did stop
results; the identifiability result and the before-and-after that follows from it;
a parameter-free structural predictor passing a preregistered direction test and
generalising to an unseen mechanism (ensemble MAE 0.0502 against 0.2022 for a
constant); a prediction result under three leakage controls including a
permanently retained time-only baseline; and a precise negative result about a
conformal gate at a conventional risk level in a high-failure-base-rate regime.

## What is being done about the decision layer

See `EXPERIMENT_PROTOCOL.md` amendment 0.15. Two fault mechanisms are added in
which rerouting is the wrong action, so that no single threshold can attain the
oracle bound and the common-anchor layer acquires discriminating power. They are
evaluated as a mechanism-shift test set against models trained and calibrated on
this matrix, which tests generalisation to unseen failure physics rather than
interpolation.
