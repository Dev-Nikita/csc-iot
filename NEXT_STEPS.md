# What to do next, in order

Updated 2026-09-27. Each step says who does it, what it produces, and what
would make it fail. A step is not finished until its check passes; a step whose
check fails is not worked around.

Commands marked **[server]** run on `cybernord` in `~/csc-iot`. Commands marked
**[mac]** run in the project folder. `make deploy HOST=cybernord` before any
server step that uses code changed since the last deploy.

---

## Step 1 — Spanning-regime holdout (no new runs) — mine

The prediction result has one unanswered question. In the spanning regime the
fault has not happened at decision time and nothing observable carries it, yet
the model reaches MAE 0.0367 against 0.1624 for a constant. Two explanations
fit: it is predicting the consequences of what has already accumulated, or it
has learned the distribution of onsets from training and is exploiting it.

Train with every spanning branch removed, test only on spanning branches. If the
error holds, the skill transfers. If it collapses, the model was using the onset
distribution, and the paper says so — that is the difference between a
controller that reads state and one that has memorised the experiment.

**Check:** a number, either way, and one sentence in
Section~\ref{sec:results-prediction} replacing the TODO.

## Step 2 — Structural model `Ĵ(s,a)` — mine

Written before the challenger exists so that it cannot be tuned against it, for
the same reason the gate and the budget rule were frozen in advance. Inputs are
the 57 permitted features only. Two assumptions go in the paper, not only the
code: capacity is inferred from throughput only when the queue is non-empty
(with an empty queue, throughput is the arrival rate and says nothing about
capacity), and the shape of the latency distribution is taken as observed while
the shift comes from queueing arithmetic.

**Check:** `analysis/test_structural.py` — the model must reproduce, on
recorded branches, the sign of every contrast that survived all four bands in
Section~\ref{sec:results-actions}. A structural model that cannot order the
actions it was built to order is not a baseline.

## Step 3 — B5 in three regimes — mine, then one decision

In-distribution, parameter shift (train on the two milder severities, test on
the strongest), mechanism shift (needs Step 5). Apply the retention rule from
protocol §11b, which was fixed before any of these test sets existed:
`ΔCRA_η ≥ 0.05` or `Reg_η ≤ 0.90 × Reg_η(challenger)`, bootstrap CI excluding
zero. A tie is a tie and the explicit structural layer is dropped.

**Check:** the rule is applied as written, and the outcome — including a tie —
selects the architecture for Step 6.

## Step 4 — Calibrate the budget for the other workload levels — yours

The frozen 750 ms applies to 100 events per epoch only. The healthy per-event
latency distribution depends on offered load, so a single budget across levels
would make the failure term measure the load. Two calibration runs, about 15
minutes each.

**[mac]** `make deploy HOST=cybernord`

**[server]**
```bash
cd ~/csc-iot && make build TAGS=nats && make up-nats && make stack-nats
export STACK_ID=$(python3 check_reportable_stack.py --print-stack-id)

for L in 60 140; do
  python3 scripts/gen_scenarios.py --n 1 --master-seed 2026 \
    --mechanisms D1 --workloads $L --out /tmp/cal-$L.json 2>/dev/null \
    || { echo "level $L has no budget yet -- expected, that is what we are fixing"; }
done
```
The generator refuses a level with no budget, which is the guard working. The
calibration run therefore has to bypass it deliberately: the budget is measured
on **no-action pre-fault branches**, where the SLA is not used at all.

**Check:** `analysis/calibrate_budget.py … --workload 60` and `--workload 140`
each print a per-event $p_{99}$; both go into `configs/budgets.json` with their
provenance **before** any comparative run at those levels.

## Step 5 — MIGRATE, and the D2/D3 fault mechanisms — mine

Four actions and three mechanisms are what the plan promises. `MIGRATE` needs
real state movement with an acknowledgement, like the existing actions. `D3`
(edge stall) is expressible with the flags that exist — severity 0. `D2`
(ingress impairment ramp) needs netem re-applied part-way through a branch; the
scenario generator refuses to emit it until it exists, rather than running `D1`
under its name.

**Check:** the runner's per-branch fault verification passes for every new
mechanism, and the audit's degradation bound binds on the new branches.

## Step 6 — The controller — mine

Ensemble of ten, conformal risk control on the declared set-level loss,
minimum-necessary intervention with guarded abstention, on whichever
architecture Step 3 selected. Abstention is reported per regime beside the
ensemble spread that produced it, and never as a single rate: an abstention that
no measurable signal produced is not the mechanism working.

**Check:** a closed-loop run in which the selector demonstrably chooses — the
log names the action, the cheaper alternatives it rejected and why.

## Step 7 — Baselines, ablations, D0 — yours to run, mine to analyse

B1 never intervene, B2 reactive threshold, B3 greedy predicted-best without gate
or cost ordering, B4 replay oracle (labelled as not implementable online), B5t
time-only control retained. A1 removes the gate, A2 removes the cost ordering.
Then the D0 determinism audit on the frozen configuration.

Branch cost grows with the anchor: 2880 branches with anchors to 30 took 17.5
hours, about 22 s each, against 15.4 s measured on a pilot with short anchors.
The next design size comes from a fit of cost against anchor, not from one mean.

## Step 8 — Finish the manuscript — mine

Results are written from validated artifacts only. Abstract and conclusion last.
`\thanks` e-mail and the artifact URL still say TODO and must be filled. The
paper is 9 pages now against a 10-page TNSM core, so Step 6 and Step 7 have
roughly one page between them; something in Sections II–IV gives way rather than
buying overlength pages.

---

## Standing rules that have already earned their place

- A run is not read until `analysis/audit_accounting.py` returns zero.
- A verifier that cannot fail is not a verifier. Three of them were fixed after
  they failed correct runs, and one had never executed at all.
- `bash scripts/audit_repo.sh` after every deploy: it guards the invariants that
  each cost a run, against a stale copy quietly undoing them.
- Numbers reach the paper through `analysis/make_tables.py`, never by hand.
