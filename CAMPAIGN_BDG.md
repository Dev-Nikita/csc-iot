# Campaign B+D+G: does verified common-state replay earn its place?

**Status: frozen 2026-10-31, before the testbed is rebuilt and before any run.**
Prospective. Not a retrospective account of anything in Zenodo 0.7, which stays
as it is and is the historical baseline. Every number below that a result could
be tuned against is fixed here; a change after the first run is a dated
amendment at the end of this file, stating what it replaces and why.

## The question that decides whether there is a paper

Executing recovery actions before committing to one is not new; PILOT does it.
What this work claims on top is that the alternatives are executed **from a state
verified equivalent in each respect the recorded state exposes**, so that their
measured outcomes are comparable at all. If a plain reset, or a replay without
the transport-quiescence guard, produces the same comparative conclusions, that
claim is an engineering detail and not a contribution. The campaign is designed
so that a negative answer is a reportable result and not a failure to be
re-analysed away.

## Order, and why it is not the order an external review proposed

The review put strong statistical baselines first (its experiment A) and the
state ablation second. We invert that, deliberately.

Our own four-criterion table already shows what A is likely to find: the
bootstrap criterion classed 119 and 220 anchors unresolved against the pooled
band's 170 and 266. Ordinary paired inference answers the same question, in
places more permissively. If A runs first and returns that answer, the only place
a contribution can live is in whether the executed alternatives were comparable
to begin with --- which is what B tests. **B decides whether there is a paper; A
decides how to word it.** A therefore runs as an analysis of B's own outputs, at
equal execution budget, not as a separate campaign.

## Modes

All modes share the fault plan, action set, objective, container images and
observation horizon. Execution order is randomised within each design point to
keep thermal and load drift from aligning with mode.

| | Mode | What it does |
|---|---|---|
| F | full | common-anchor reconstruction, application-state admission checks, producer/consumer transport watermarks, applied-action acknowledgement |
| Q | quiescence ablated | F without the transport watermarks. In-flight traffic is logged, not suppressed. Isolated harness only |
| S | state guard ablated | same seed, configuration and intended anchor, admission checks disabled. Measured state mismatch is an output, never a reason to drop a sample |
| R | conventional reset | reset to the declared initial state, replay the event prefix, execute the action. No claim of identical decision-time state |
| N | negative control | the **same** action executed twice at the same anchor under F. Costs nothing extra: it is read off F's repeats |

N is the control that matters most and the one this work has never had. The
dispersion band measures variability of one action; it does not establish a
false-resolution rate **between two different actions**. N measures that rate
directly, under a null that is true by construction.

## Design points, fixed here

Chosen by a rule over design variables only. Within each fault family the
candidates are grouped into strata of (workload, severity), the strata visited in
ascending order, and within a stratum ordered by onset then identifier; points
are taken round-robin across strata until the family quota is met. Quotas:
D1 3, D3 2, D4 3, D5 2, D6 2. **No observed outcome enters the selection.**

| matrix | point | fault | onset | severity | load |
|---|---|---|---|---|---|
| b5-matrix-v2 | s91 | D1 | 8 | 40 | 60 |
| b5-matrix-v2 | s38 | D1 | 9 | 60 | 60 |
| b5-matrix-v2 | s102 | D1 | 8 | 90 | 60 |
| b5-matrix-v2 | s30 | D3 | 8 | 0 | 60 |
| b5-matrix-v2 | s15 | D3 | 10 | 0 | 100 |
| d45-matrix-v1 | s19 | D4 | 8 | 40 | 100 |
| d45-matrix-v1 | s05 | D4 | 12 | 60 | 100 |
| d45-matrix-v1 | s27 | D4 | 8 | 90 | 100 |
| d45-matrix-v1 | s28 | D5 | 8 | 40 | 100 |
| d45-matrix-v1 | s20 | D5 | 12 | 60 | 100 |
| d6-pilot-v2 | s04 | D6 | 8 | 40 | 100 |
| d6-pilot-v2 | s05 | D6 | 11 | 60 | 100 |

All five mechanisms, eight (load, severity) strata, 59 decision anchors.

One disagreement with the external protocol, recorded rather than quietly
resolved: it asked for boundary cases near `eta_J` to be included. Choosing
points because their measured gap sat near the band **is** selection on the
outcome, and it would bias the very quantity the campaign measures. Instead
every point is selected on design variables, and the results are additionally
**reported** split by whether the point lay near the band under seed 42 --- a
post-hoc split, labelled as one.

## Seeds

Five per design point, independent of master seed 42 and derived so that anyone
can regenerate them:

    seed(matrix, point, k) = int(sha256(f"csc-iot-BDG-{matrix}-{point}-{k}")
                                 .hexdigest()[:8], 16),  k = 1..5

The pilot measures variance and feasibility. Twelve points with five seeds is
not a confirmatory sample and will not be described as one.

## Budget, split by what each question needs

B does not need multiple seeds: it compares modes at the same point and seed.
D needs multiple seeds but only mode F. Factoring them is the difference between
a feasible campaign and an infeasible one.

| part | design | branches |
|---|---|---|
| B | 12 points x 1 seed x 59 anchors x 3 actions x (F 10 + Q 3 + S 3 + R 3) | 3363 |
| D | 12 points x 5 seeds x 59 anchors x 3 actions x 3 repeats, F only | 2655 |
| total | | **6018** |

That is about three quarters of the entire existing corpus, so it is not a free
afternoon. **Step 0 is therefore one design point, end to end, to measure the
wall-clock rate per branch.** If the measured rate puts the campaign beyond the
declared ceiling of 72 hours of machine time, the pilot drops to eight points by
removing one point per family from the end of the selection order, and that
reduction is recorded here before the rest is run.

## What is measured

**Primary.** The rate at which Q, S and R reach a comparative conclusion that
differs from the one repeated F reaches at the same anchor, reported as two
separate components and never summed into one headline:

1. **reversal** --- the two modes order the same pair of actions differently;
2. **unsupported resolution** --- the weaker mode resolves a contrast that
   repeated F cannot.

**On the magnitude threshold, we deviate from the external protocol and say so.**
It asks for a prespecified epsilon below which a reversal is not material. We
decline to pick one, because any value we chose would decide the headline and we
have no operational basis for it: this work has never measured what difference an
operator would act on. Two things are reported instead. A representability floor,
`eps_floor = 0.6 / 900 = 6.67e-4`, one additional failed request at the smallest
offered load in the design, under the declared weight `W_FAILURE = 0.6`; a
difference below it is not representable in the objective and is not counted.
And above it, the **full distribution** of reversal magnitudes, so that a reader
sets their own threshold and sees what it does.

**The F reference is not truth.** Its own uncertainty over ten repeats is
reported beside every comparison, and a disagreement inside that uncertainty is
counted as undetermined, not as an error by the weaker mode.

**Secondary.** Initial-state mismatch rate; in-flight messages at the anchor;
prefix fingerprint disagreement; false-resolution rate under N; abstention rate;
effect heterogeneity by family and regime; failures to reconstruct or to reach
quiescence, reported as outcomes with their denominators rather than dropped.

**D.** Variance decomposed into design point, seed within point, and repeat
within anchor-action. Intervals computed at the design-point x seed level, never
by resampling branches as independent draws. Cross-seed movement of the
unresolved share and of the false-resolution rate.

**G.** Wall clock and CPU for reconstruction, quiescence wait, invariant
verification, branch execution and analysis, as median and p95 per anchor, plus
bytes retained. This is offline evaluation cost. It is never reported as online
decision latency, and the paper already separates the two.

**A, as analysis not as a campaign.** On F's outputs alone and at equal budget:
paired intervals, a paired permutation test, and a cluster-aware bootstrap, each
against the same anchors the band criterion judged. If they reach the same
conclusions, the contribution is comparability of the executed alternatives, not
the resolvability rule, and the manuscript says that.

## Analysis is frozen with the protocol

The analysis script is written and committed before the first campaign run, run
against synthetic inputs to check it executes, and not modified after outcomes
are opened except by dated amendment.

## What the outcomes mean, decided now

- **Support.** F prevents a reproducible class of reversals or unsupported
  resolutions that at least one weaker mode commits, the class survives the new
  seeds, and the effect is not explained by F's extra repeats --- tested by
  down-sampling F to three repeats and repeating the comparison.
- **Partial.** F measurably improves state equality --- lower mismatch rate,
  fewer in-flight messages --- without changing comparative conclusions. Reported
  as an engineering validation result. The novelty claim narrows to comparability,
  and the paper says the decision-level benefit was looked for and not found.
- **No support.** The modes agree within intervals that are tight enough to make
  the agreement meaningful. The current novelty claim is **NO-GO for TDSC** and
  the work is retargeted. A null is not rewritten as a win.
- **Inconclusive.** Intervals too wide, modes not technically comparable, or
  uncontrolled drift. Reported as inconclusive. Not PASS.

## What this campaign does not settle

The independent CRC audit, which is mathematics and not runs. Closed-loop service
outcomes, which this testbed does not measure. External validity beyond nine
containers on one host. Each stays an open gate in `PRESUBMISSION.md`.

## Amendments

(none yet)
