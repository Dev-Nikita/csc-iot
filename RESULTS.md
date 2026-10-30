# Measured results

Every number here comes from a run on disk whose accounting audit passed. Where a
result goes against the method, it is in the same table as the rest. Nothing is
re-scored to a rule chosen after seeing it; `delta = 0.10`, `theta`, `tau_hat` and
the §11b retention rule were all fixed before any test split was examined.

Runs and substrates are named because `eta_J` is a property of a concrete stack
and does not transfer between them.

| stack | what ran on it |
|---|---|
| `161b4e3893c01695` | `b5-matrix-v2` (6210 branches, D1/D3, loads 60/100/140); budgets L=60, L=140 |
| `15192a04761cca10` | `d45-matrix-v1` (1800 branches, D4/D5, L=100) |
| `408a36b2a908cf6d` | `d6-pilot-v2` (108 branches, D6, L=100), first run with the cost term measured |

## 1. The latency budget is stable across four independently built substrates

The declared rule is the healthy per-event p99 rounded up to 50 ms, measured on a
dedicated calibration run of healthy pre-fault no-action branches.

| date | stack | branches | events | p99 | budget |
|---|---|---|---|---|---|
| 2026-09-22 | `5bc49e1c2750002a` | 30 | 27 000 | 750 | 750 ms |
| 2026-09-27 | `161b4e3893c01695` | 40 | 24 000 | 750 | 750 ms |
| 2026-10-04 | `15192a04761cca10` | 40 | 24 000 | 750 | 750 ms |
| 2026-10-04 | `408a36b2a908cf6d` | 40 | 24 000 | 750 | 750 ms |

Four rebuilds, one number. The substrate is cleared as a confound by measurement
rather than by assumption. **Against the method:** the budgets are NOT monotone in
load -- 850 ms at L=60 against 750 ms at L=100 and L=140 -- and that is reported
rather than smoothed. At L=60 the p99 rests on 14 400 events, so roughly 144 lie
above it and the estimate moves by one or two 25 ms bins; the alternative
explanation, that the 200 ms emission spread interacts with epoch quantisation
differently at low event density, is equally open. The declared rule is applied as
written either way.

## 2. Identifiability wall 1: onset and severity, from cumulative counters

`served + queued = arrivals x epochs` holds identically, so the onset and the
severity of a degradation are not separately identifiable from cumulative
counters. A direct test on 104 post-onset no-action branches recovered medians
**103.3 / 100.0 / 83.3** for true severities **40 / 60 / 90** -- it recovers the
arrival rate, not the capacity.

**This wall comes down.** Windowed observables (protocol 0.10) take the
preregistered structural sign test from **13 flipped signs of 203** to **0 of
187**, every flip having been THROTTLE at the earliest anchor, where the
cumulative arrival rate reads 50 while the steady rate is 100.

## 3. Identifiability wall 2: the capacity of an idle alternative

On `d45-matrix-v1` the preregistered sign test reproduces **96 of 101** resolvable
signs, 0.950: pre-fault 54/54, spanning 40/44, post-onset 2/3. **It fails the
test**, and all five flips are the same mechanism.

| contrast | regime | observed | predicted |
|---|---|---|---|
| `s03-a14-REROUTE` | spanning | -0.1430 | +0.1534 |
| `s27-a02-REROUTE` | spanning | -0.1737 | +0.0181 |
| `s27-a08-REROUTE` | post-onset | -0.1386 | +0.2480 |
| `s33-a14-REROUTE` | spanning | -0.1234 | +0.1559 |
| `s39-a14-REROUTE` | spanning | -0.1295 | +0.1354 |

The model predicts rerouting helps by about +0.15; the measurement says it hurts
by about -0.14. The cause is Assumption 1 as written: capacity is inferred from
throughput only where the queue is non-empty, and nominal capacity is used
otherwise. The relief edge carries no traffic under the current routing, so the
model credits it with its nominal 150 while D4 has degraded it to 20 or 45.

**This wall does not come down.** A counterfactual about rerouting needs the
capacity of a path carrying nothing, and no telemetry from the path in use
supplies it: the quantity is not under-sampled, it is unsampled. An operator can
supply the assumption -- a configured nominal, a probe, a health report from the
target -- and the paper says so rather than pretending to infer it.

## 4. Identifiability wall 3: the resource cost of an action

`d6-pilot-v2`, 108 branches, all three instrumented cost components present on
every branch:

| action | disruption | resource | bandwidth | cost | J_obs |
|---|---|---|---|---|---|
| NO_OP | 0.2309 | **0.0180** | **0.3253** | 0.1914 | 0.4631 |
| REROUTE | 0.1482 | **0.0181** | **0.3253** | 0.1639 | **0.4186** |
| THROTTLE | 0.4703 | 0.0166 | 0.2864 | 0.2578 | 0.4768 |

Recruiting a second edge moves `resource` by **0.0001**. A container's CPU is
dominated by its idle loop: the service tier runs at 1.8% of its own capacity, and
serving a few thousand JSON messages costs microseconds against 21 epochs of
300 ms across five containers. `bandwidth` is identical under NO_OP and REROUTE to
four decimals, because rerouting changes a message's subject and not how many are
sent; only THROTTLE moves it, by admitting less.

So bandwidth measures the volume of work, resource measures the idle baseline, and
neither prices the one thing rerouting does -- holding a second node open.
`C(REROUTE)` is no longer 0.000, which was the single claim made in advance, but at
0.1639 against 0.1914 **rerouting is still cheaper than doing nothing**.

**This wall does not come down by instrumentation.** The price of recruited
capacity is reported by `analysis/cost_sensitivity.py` as a declared assumption
swept over a range, and is deliberately absent from `J_obs`.

### 4a. What the ranking depends on, when the price is declared rather than measured

The price is per recruited edge, in the same units as the other cost components;
1.0 means holding one additional edge open costs as much as the worst disruption
this objective can measure. The cost term carries weight 0.2 and the price is one
of three components, so a price of `p` can move `J` by at most `0.0667 p`.
`recruited` is 0 under NO_OP and THROTTLE and exactly 1 under REROUTE on all 108
branches.

| price | NO_OP | REROUTE | THROTTLE | preferred |
|---|---|---|---|---|
| 0.00 | 0.4619 | **0.4174** | 0.4757 | REROUTE |
| 0.40 | 0.4619 | **0.4440** | 0.4757 | REROUTE |
| 0.65 | 0.4619 | **0.4607** | 0.4757 | REROUTE |
| 0.70 | **0.4619** | 0.4640 | 0.4757 | NO_OP |
| 1.00 | **0.4619** | 0.4840 | 0.4757 | NO_OP |

Rerouting is preferred while the declared price stays below **0.67** -- the gap of
0.0445 at zero price divided by the 0.0667 a unit of price moves `J`. Above 0.67
inaction is preferred; above **0.87** throttling also overtakes rerouting. The
crossing was predicted at 0.667 from the arithmetic before the sweep was run and
observed between the 0.65 and 0.70 grid points.

So rerouting does not win merely because it is unpriced. It wins because the
throughput gain of a second server outweighs any moderate price, and overturning
it requires pricing one additional node at two thirds of the entire cost scale.
Whether that is realistic is a deployment question this testbed cannot answer, and
the bound is what is reported rather than a value.

**Against the sweep itself:** its first version divided the price by the number of
recruitable edges, which redefined a price of 1.0 as recruiting *every* edge and
capped the price's effect on `J` at 0.0333 -- below the 0.0445 gap it was meant to
be able to close. It then reported "REROUTE preferred at every price", which was a
property of the normaliser and not of the system. A negative result about a
crossing is only meaningful if the crossing was reachable, so the sweep prints the
ceiling a price can reach beside its conclusion and a fixture asserts that ceiling
exceeds the measured gap.

## 4b. Action-conditioned prediction, and its two leakage controls

From `b5-matrix-v1` (2880 branches), folds held out by fault design point. Emitted
by `analysis/make_tables.py`; produced identically on the analysis host and on a
second machine under the committed code (protocol 0.29), which is what makes these
the reported figures rather than the earlier ones they replace.

| predictor | MAE | time-only | permuted | constant |
|---|---|---|---|---|
| telemetry, kNN | **0.0258** | 0.1011 | 0.1610 | 0.2008 |
| telemetry, ridge (linear) | 0.3216 | --- | --- | --- |
| post-onset (n=1560) | 0.0259 | --- | --- | 0.1615 |
| pre-fault (n=600) | 0.0122 | --- | --- | 0.2362 |
| spanning (n=720) | 0.0364 | --- | --- | 0.1624 |

The telemetry model cuts the error against a time-only predictor by 74 per cent,
and permuting the telemetry raises it by a factor of 6.2. Both controls must pass
before any prediction figure is reported.

The time-only control reads 0.1011 and not the 0.1174 of earlier drafts: its
feature set is the elapsed epoch and the candidate action, both low-cardinality,
so a large share of training points sit at identical distance and which of them
entered the neighbour set was arbitrary until neighbour selection was made
deterministic. See protocol amendments 0.27 to 0.29.

Spanning holdout: 0.0348 with spanning branches allowed in training, 0.0479 with
them removed, 0.0479 with the test branch's fault setting also removed, against
0.1922 for a constant predictor.

## 4c. What the actions do, per anchor

From `m2prime-903` (900 branches, one fault setting, 30 anchors), emitted by
`analysis/action_contrasts.py` against the preregistered pooled band
`eta_J = 0.0164`. These were the last figures in the manuscript with no script
behind them; recomputing them by hand once is how the peak came to be reported as
the value at an intermediate anchor rather than the maximum.

| finding | anchor | value | bootstrap CI |
|---|---|---|---|
| pre-fault null, NO_OP minus REROUTE | a01 | -0.0001 | [-0.0002, +0.0050] |
| **peak** rerouting contrast | a11 | **+0.2769** | [+0.2722, +0.2851] |
| deepest anchor | a30 | **+0.1741** | [+0.1675, +0.1806] |

The peak and deepest intervals do not overlap.

Throttling, as THROTTLE minus NO_OP:

| anchor | contrast | multiples of eta_J | resolvable at the 3x gate |
|---|---|---:|---|
| a01 (shallowest) | +0.7375 | 45.0 | yes |
| a30 (deepest) | +0.0377 | 2.3 | no |

Throttling is harmful wherever it resolves and most harmful earliest, at 45 times
the band. It stops being distinguishable from inaction at the deepest anchors not
because it stops hurting -- the contrast is still positive -- but because inaction
has caught up with it.

**Correction, 2026-10-05.** Earlier drafts said the contrast "rises to 0.264 at an
intermediate anchor". 0.2636 is the value at a10; the contrast keeps rising to
0.2769 at a11. The figure was not wrong about a10, but the sentence read as if it
were the maximum, and it was not. The manuscript now reports the peak.

## 5. The decision layer: two degeneracies in opposite directions

`CRA_eta` against the oracle bound, with `eta_J` from each matrix's own replay
dispersion.

| set | B1 threshold | B2 assoc | B5t time-only | B6 CSC | A1b no gate | oracle |
|---|---|---|---|---|---|---|
| in-distribution (60 pts) | 1.000 | 0.983 | 1.000 | 0.633 \| 0.974 acting | 0.533 | 1.000 |
| parameter shift (180) | 1.000 | 0.972 | 1.000 | 0.583 \| 0.946 acting | 0.461 | 1.000 |
| mechanism shift (138) | 0.993 | 0.978 | 0.993 | 0.399 \| 0.885 acting | 0.254 | 1.000 |
| **transfer, D4/D5 (200)** | 0.890 | 0.890 | 0.890 | 0.900 \| 0.863 acting | **0.955** | 1.000 |

Abstention under B6: 0.367 / 0.383 / 0.558 / 0.490 across the four sets.

### The full `evaluate.py` output, including A2

Recomputed on the analysis host 2026-10-05 (`logs/decision_eval.log`) after the
A2 row was found to have no record anywhere. Every previously reported figure for
B6 and A1b was reproduced exactly, and the two A2 figures the manuscript carried
(0.589, 0.428) were confirmed. `n` is decision points, `acted` the subset where
the method intervened.

| block | method | n | CRA_eta | acted | CRA\|acting | Reg_eta | PFR | WIR | abst |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| in-distribution | B6 CSC | 60 | 0.633 | 38 | 0.974 | 0.0612 | 0.714 | 0.000 | 0.367 |
| | A1b no gate | 60 | 0.533 | 60 | 0.533 | 0.0770 | 0.000 | n/a | 0.000 |
| | A2 no MNI | 60 | 0.633 | 38 | 0.974 | 0.0612 | 0.714 | 0.000 | 0.367 |
| parameter shift | B6 CSC | 180 | 0.583 | 111 | 0.946 | 0.0791 | 0.760 | 0.000 | 0.383 |
| | A1b no gate | 180 | 0.461 | 180 | 0.461 | 0.1007 | 0.000 | n/a | 0.000 |
| | **A2 no MNI** | 180 | **0.589** | 111 | **0.955** | **0.0785** | 0.800 | 0.000 | 0.383 |
| mechanism shift | B6 CSC | 138 | 0.399 | 61 | 0.885 | 0.1072 | 0.607 | 0.023 | 0.558 |
| | A1b no gate | 138 | 0.254 | 138 | 0.254 | 0.1376 | 0.000 | n/a | 0.000 |
| | **A2 no MNI** | 138 | **0.428** | 61 | **0.951** | **0.1020** | 0.750 | 0.019 | 0.558 |
| transfer D4/D5 | B6 CSC | 200 | 0.900 | 102 | 0.863 | 0.0047 | n/a | 0.154 | 0.490 |
| | **A1b no gate** | 200 | **0.955** | 200 | 0.955 | **0.0009** | n/a | n/a | 0.000 |
| | A2 no MNI | 200 | 0.900 | 102 | 0.863 | 0.0055 | n/a | 0.137 | 0.490 |

**A2 is never worse than the full method and is better on two blocks.** Removing
minimum-necessary intervention leaves the gate and the abstention rate untouched
and replaces the cheapest admissible action with the lowest-risk one. It matches
CSC in-distribution and on transfer, beats it on both shifted blocks, and has
lower regret on three of four. Minimum-necessary intervention is one of the
mechanisms this work specifies, and on these fault families the measurement does
not support it. This is the third result against the method and it is reported in
the manuscript beside the other two.

`PFR` is undefined on the transfer block and `WIR` is undefined wherever a method
never intervenes; those cells read n/a rather than zero.

Two readings, both against the method:

**On D1/D3 a one-line reactive threshold attains the oracle.** B1 is a threshold on
the per-edge service deficit, and it is perfect in-distribution and under
parameter shift, 0.993 under mechanism shift. A comparison in which a baseline
reaches the bound measures nothing about a decision method.

**On D4/D5 the degenerate ablation wins.** `A1b_no_gate` removes the gate and
therefore always takes the cheapest action -- NO_OP, cost 0 by definition -- and it
scores **0.955** with regret **0.0009**, against CSC's 0.900 / 0.0047. Doing
nothing is near-optimal there. The same ablation scores 0.254 on mechanism shift.

The two sets are degenerate in **opposite** directions, and section 4 explains
both: rerouting wins wherever it is an unpriced recruitment of capacity, and
inaction wins wherever no action is priced correctly either.

B6 abstains on 36.7% / 38.3% / 55.8% / 49.0% of decision points. When it acts it
is near-oracle (0.974 / 0.946 / 0.885 / 0.863); the abstention follows from
`theta = 0.0602` making 797 of 1080 calibration branches count as failures, after
which equation (9) forces `tau_hat = 0.0447` below the risk of any failing action.
`delta`, `theta` and `tau_hat` are frozen as declared.

Replayed on the analysis host on 2026-10-30 by `analysis/recompute_crc_independent.py`,
which reads only the frozen ledger `crc_calibration.csv` and imports nothing from
this project -- not the CRC module, not the predictor, only `argparse`, `csv` and
`math`. It reports `rows=1080 runs=20 theta=0.06019238095 u_max=0.15 delta=0.1`,
`tau_hat=0.04468686866`, `empirical_risk=0.05` and `corrected_risk=0.09523809524`.
The corrected risk is at or below `delta = 0.10`, as equation (9) requires, and the
threshold agrees with the reported `0.0447` to the precision the paper states. The
reconstruction also refuses a non-monotone loss curve and did not refuse, so the
monotonicity the derivation assumes holds on the real calibration data rather than
only in the implementation that produced it.

This is an implementation-independent replay, not an independent audit: the same
person ran it, on the host that produced the data. What it rules out is a defect in
the project's own CRC code or an arithmetic slip in transcription. What it cannot
rule out is a problem in the ledger's construction -- which runs entered the
calibration pool, and whether they are exchangeable with a future run. Those two
checks are in `CRC_AUDIT.md` and remain open for someone outside this work.

## 5b. What executing the alternatives actually changes

Rules frozen in `VALUE_OF_PROTOCOL.md` and committed before the distribution was
computed; produced by `analysis/value_of_protocol.py` from the published archive
and recorded in `analysis/value_of_protocol_output.txt`. Three evaluations on the
same anchors, the same actions and the same objective column: **P** picks the
action minimising the structural prediction `J_hat`; **S** picks the one
minimising a single executed branch; **R** picks the one minimising the mean over
repeats and declares the anchor unresolved when the gap to the runner-up is at or
below `eta_J`.

| contrast | | d45-matrix-v1 (200 anchors) | b5-matrix-v2 (690 anchors) |
|---|---|---|---|
| P vs S | changed / unchanged | 104 / 96 | 131 / 559 |
| P vs R | changed / unchanged / unresolved | 23 / 7 / 170 | 7 / 417 / 266 |
| S vs R | changed / unchanged / unresolved | 0 / 30 / 170 | 2 / 422 / 266 |

The result is not the one the protocol was expected to produce, and it is the
more interesting one.

**Repetition almost never changes the winner.** Where the comparison resolves at
all, a single execution and five-fold repeated execution pick the same action in
30 of 30 anchors on d45 and 422 of 424 on b5. What repetition buys is not a
different answer but the knowledge of whether there is an answer.

**Most comparisons do not resolve.** 170 of 200 anchors on d45 (85.0 per cent)
and 266 of 690 on b5 (38.6 per cent) have a best-to-runner-up gap at or below the
dispersion band. A conventional evaluation reports a winner at every one of them.

**Where it does resolve, the structural prediction is wrong far more often on
d45 than on b5.** 23 of the 30 resolved d45 anchors change the winner against the
prediction, against 7 of 424 on b5. The two matrices disagree by a factor of
forty, and the manuscript must not quote either alone.

**The effect is confined to one mechanism.** On d45 every changed anchor is D4:
D5 contributes 0 changed, 0 unchanged and 100 unresolved. That is a limitation,
not a headline, and it is reported as one.

**Sign flips are more numerous than the five the supplement tabulates, under a
weaker rule.** Taking the pooled band alone, 35 of 196 resolvable
`(anchor, action)` contrasts against `NO_OP` have predicted and observed
improvements of opposite sign on d45, and 16 on b5. The supplement's table of
five is the failure set of the preregistered sign test, which requires a contrast
to survive **all four** bands and admits 101 contrasts. Both are correct for
their own rule; the gap between 5 and 35 is itself a statement about how much the
conclusion depends on the strictness of the resolvability criterion, and it
belongs in the paper.

The case the frozen selection rule picks -- largest observed magnitude among
sign-flipped pairs -- is `s27-a02-REROUTE` on d45: observed `-0.1682`, predicted
`+0.0182`. It is one of the five already in the supplement. Its predicted benefit
is small, so it illustrates a wrong direction rather than a large predicted gain
reversed; `s27-a08-REROUTE` (observed `-0.1403`, predicted `+0.2359`) is the more
striking case and was **not** selected, which is stated here so that the choice
cannot be revisited after the fact.

The supplement's five rows use the **median** over repeats and this analysis uses
the **mean**; that is the whole of the difference between its `-0.1737` and the
`-0.1682` here. One definition has to be chosen for the manuscript.

**Neither claim depends on the band.** Repeating the classification under all
four declared bands (pooled, worst cell, contrast-local, and a bootstrap interval
on the difference of means excluding zero):

| criterion | unresolved d45 | unresolved b5 | S vs R changed d45 | S vs R changed b5 |
|---|---|---|---|---|
| pooled | 170 | 266 | 0 | 2 |
| worst cell | 189 | 299 | 0 | 0 |
| local | 144 | 258 | 0 | 1 |
| bootstrap | 119 | 220 | 2 | 6 |
| all four | 189 | 299 | 0 | 0 |

Over 890 anchors the unresolved share runs 38.1 to 54.8 per cent (pooled 49.0),
and the winner changes between a single execution and repeated execution at 0 to
8 of the 402 to 551 anchors a criterion resolves, at most 1.5 per cent. Recorded
as amendment 1 in `VALUE_OF_PROTOCOL.md`: the pooled figures were computed first,
are unchanged, and the four columns were added after external review asked.

What this does not establish: the comparison is between a structural prediction
and execution on one testbed. It is not evidence that a published benchmark
elsewhere reached a wrong conclusion. It also cannot separate "the structural
model is wrong" from "the model is right about something the objective does not
price", which is this paper's own third limit.

## 5c. Independent units, and what the threshold depends on

From `analysis/independent_units.py` and `analysis/crc_replay_sensitivity.py`,
both reading the published archive, both standard library only; frozen output in
`analysis/units_and_sensitivity_output.txt`.

| matrix | branches | design points | anchors | actions | repeats |
|---|---|---|---|---|---|
| `b5-matrix-v2` | 6210 | 115 | 690 | 3 | 3 |
| `d45-matrix-v1` | 1800 | 40 | 200 | 3 | 3 |
| `d6-pilot-v2` | 108 | 6 | 12 | 3 | 3 |
| total | 8118 | 161 | 902 | | |

No configuration appears in more than one matrix. The independent unit is the
design point, of which there are 161. One master seed, 42, drives all three, so
no design point has an independent seed replication, and anchors inside a design
point are not independent of one another.

Resampling the calibration outcomes over the replay repeats that were actually
executed, 2000 draws each:

| resampling | min | Q0.05 | median | Q0.95 | max | abstained |
|---|---|---|---|---|---|---|
| one repeat per cell | 0.0446869 | 0.0446869 | 0.0467014 | 0.0481864 | 0.0505439 | 0 |
| bootstrap of repeats | 0.0446869 | 0.0446869 | 0.0446869 | 0.0456463 | 0.0481864 | 0 |

The 0.05-0.95 span is 7.8 and 2.1 per cent of the point estimate, and the
reported `tau_hat = 0.0446869` is the minimum over all 4000 draws. That follows
from the aggregation: an anchor counts as failing when any admissible branch
there failed, so using all three repeats is the strictest reading of the
calibration data. Replay nondeterminism could only have made the gate more
permissive.

## 6. Replay dispersion

| run | mechanisms | eta_J pooled | worst cell | ratio |
|---|---|---|---|---|
| `d45-pilot-v8` | D4, D5 | 0.0152 | 0.0220 | 1.44x |
| `d45-matrix-v1` | D4, D5 | 0.0183 | -- | -- |
| `d6-pilot-v2` | D6 | 0.0110 | 0.0178 | 1.62x |
| `b5-matrix-v2` | D1, D3 | 0.0280 | -- | -- |

The epoch-quantised variant gives `eta_J = 0.0000` on every run. That is a
property of the units, not of the system: quantising to logical time erases the
timing variation impairment actually causes, so a band measured on it is zero by
construction. The measured-latency variant is the one reported.

## 7. What is not instrumented, and is not claimed

- `added_latency` is **excluded by argument**: the latency an action imposes is
  already the `L~` term, and charging it again counts one effect twice.
- The cost term is a **reduced** objective and is described as one wherever it
  appears.
- The RPC is `stdlib-framed-tcp`, a typed boundary. No draft may name gRPC
  without changing it first.
- Impairment is kernel netem on one interface of the device simulator. There is no
  physical radio, no RF measurement and no energy measurement anywhere in this
  work, and none is claimed.
- Mechanism D2 (an ingress impairment ramp) is refused by the generator rather
  than silently emitted as D1. MIGRATE has no side effects and is not evaluated.
- `git_commit` recorded `protocol-0.9` for every run between 2026-09-25 and
  2026-10-04 (protocol 0.18). No measurement depends on the field; the affected
  runs are bounded by date against the commit history and that range is what the
  manuscript states.

## Second system: resolvability on RCAEval RE1 (recorded 2026-10-30, CORRECTED)

Source: `secondstand/results.jsonl` (375 rows, one per case) and
`secondstand/analysis_output.txt`, produced by `secondstand/batch.py` and
`secondstand/analyse2.py` over the RCAEval RE1 suite downloaded from the authors'
Hugging Face repository (`phamquiluan/RCAEval`, patterns `re1*`, 124 MB).
Three shipped metrics-only methods were attempted. BARO and N-Sigma include the
true service in 373 of 375 rankings each; epsilon-Diagnosis does so in only 23 of
375. Its 352 absent services remain in the raw output but are excluded from
inference: mapping them to reciprocal-rank zero made a nearly constant failure
mode appear artificially stable. The analysis below therefore compares BARO and
N-Sigma only.

**A correction, recorded in place of the figures it replaces.** The first
analysis (`analyse.py`, superseded) compared the MEAN of five repetitions against
a band built from differences between SINGLE repetitions. A mean of five is about
sqrt(5) ~= 2.24 times less dispersed in standard deviation than one observation
(measured: within-configuration sd 0.197 for a single repetition, 0.088 for the
mean of five; the corresponding difference scales are 0.278 and 0.125), so that
criterion was far too
conservative, and it produced the figure "0 of 75 for BARO against N-Sigma" that
was briefly the headline of this probe. An independent review identified the
mismatch; it was reproduced and confirmed here before anything was changed. The
superseded figures were: band 0.667, 170 of 225 contrasts below it (75.6 per
cent), BARO vs N-Sigma 0 of 75, BARO vs epsilon-Diagnosis 13 of 75, N-Sigma vs
epsilon-Diagnosis 42 of 75, and by system 17, 31 and 7 of 75. They are listed so
that the earlier claim can be traced, and they must not be cited.

Design constants, not measurements:

- cases scored: 375
- configurations (dataset x service x fault): 75
- repetitions per configuration: 5
- methods in inference: 2; method pairs: 1
- within-configuration, within-method repetition pairs: 1500
- single-observation contrasts: 375
- per-configuration contrasts: 75

Measurements:

- repetition pairs flipping hit@1: 30.9 per cent
- repetition pairs flipping hit@5: 14.1 per cent
- repetition pairs differing in reciprocal rank by more than 0.25: 35.9 per cent
- band, pooled Q0.95 of |difference between two single repetitions| of the same
  method on the same fault: 0.750

Criterion A, one run of each method against the band, which is the regime the
manuscript's own design is in (one branch per action per anchor):

- BARO vs N-Sigma: 8 of 375

Criterion B, five repetitions, paired bootstrap confidence interval on the mean
difference, 4000 resamples, resolvable when the interval excludes zero:

- BARO vs N-Sigma: 43 of 75

Criterion C, whole suite, hierarchical bootstrap over configurations and then
repetitions, 4000 resamples:

- BARO minus N-Sigma: -0.2190, 95 per cent interval -0.2630 to -0.1761
- epsilon-Diagnosis comparisons are excluded

Resampling whole repetitions within configurations preserves N-Sigma $>$ BARO.

Negative control recorded because it bounds the method: under the benchmark's
own Avg@k, which is binary per case, the Q0.95 of pairwise differences saturates
at 1.0 as soon as any repetition disagrees, so no per-configuration contrast is
resolvable under it by construction. This is reported as a property of the
metric, not as a measurement of the methods.

Replication-depth sensitivity (`secondstand/replication_sensitivity.py`, seed
17, 4000 paired-bootstrap resamples per subset). Every subset of size n from the
five paired repetitions is enumerated; the full-five mean difference is the
descriptive reference, not an independent truth:

- n=2: 750 subsets; sign agreement 83.33%; median absolute subset-to-full
  deviation 0.1000; 90th percentile 0.2400
- n=3: 750 subsets; sign agreement 92.13%; median deviation 0.0667; 90th
  percentile 0.1600
- n=4: 375 subsets; sign agreement 96.53%; median deviation 0.0417; 90th
  percentile 0.1000
- n=5: 75 subsets; sign agreement 100%; zero deviation by construction

The paired percentile-bootstrap interval-exclusion rate is non-monotone: 42.13%,
28.67%, 48.53% and 57.33% at n=2,3,4,5. It is therefore a small-sample diagnostic,
not a replication power curve. Exact two-sided sign-flip tests reject none at
0.05; their minimum attainable p-values are 0.5, 0.25, 0.125 and 0.0625.
