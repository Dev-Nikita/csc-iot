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

**A2 (`A2_no_mni`, minimum-necessary selection removed) is missing from this
table.** The manuscript reports it as 0.633 / 0.589 / 0.428 / 0.900, and 0.589 and
0.428 appear nowhere in this repository: `paper/check_transcribed.py` lists them
as unrecorded. They are to be read off the `evaluate.py` output on the analysis
host and written here before submission, or recomputed. Until then they are two
figures in the manuscript with no provenance in the record, which is a blocking
pre-submission gate.

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
