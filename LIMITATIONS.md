# The limitations register

One entry per structural limitation of the experiment. Each has an id, a status,
what can still be checked, and what would remove it. The point of a register is
that a limitation is settled once: its status and its permitted interpretation
are decided here, and no later analysis has to rediscover it or argue about it.

`OPEN` means acknowledged and not removable from the data in hand. `BOUNDED`
means a measurement limits how large it can be. `CLOSED` means removed, with the
evidence named.

---

## L-ORDER-001 --- Action identity is perfectly confounded with execution-block position

**Status: OPEN.** Not fixable in the existing data by any analysis.

`scripts/m2prime_nats_matrix.sh` executes a cell as scenario, anchor, action,
repeat. Each action therefore occupies a contiguous block of wall-clock time
inside the cell, and the block order --- NO_OP, THROTTLE, REROUTE --- is
identical in every cell of every matrix. "First block" and "NO_OP" are the same
column. A position-in-cell effect and an action effect are not separately
identifiable, and no adjustment recovers them.

*What this does and does not touch.* It touches the **between-action gap**, which
is the quantity an action comparison rests on. It barely touches the
**dispersion band**: the band is built from differences between repeats of the
*same* action, which are consecutive in time inside one block, so the only drift
it can absorb is drift over the two minutes a block takes rather than over the
cell. The band is the least affected quantity in the paper, and the paper's
central claims C1 and C2 are about the band and the unresolved share.

*What can be checked now, and is:* `analysis/order_effects.py` --- within-block
trend of `J_obs` against repeat index, across-matrix drift computed inside each
action so the action effect is removed by construction, and per-action
within-cell dispersion so that a rejection driven by spread is visible. Both
trends being nil makes a block-level drift large enough to matter **less likely,
not excluded**, and is reported that way.

*What would remove it:* a randomised or balanced action order inside each cell,
fixed before the run. That is a change for a future matrix. Changing the runner
mid-campaign would split the campaign across two designs, which is worse than
the limitation.

*Permitted interpretation, and this wording travels with every p-value the
permutation test produces:*

> The permutation procedure provides exact conditional inference under
> exchangeability of action labels. Because execution order was fixed and
> confounded with action identity, this assumption cannot be verified or
> guaranteed by the experimental design. Results are therefore reported as
> conditional sensitivity analyses rather than design-valid randomization tests.

*And the part that is not a limitation.* A fixed action order is what an
evaluation harness ordinarily does. An evaluation that executes candidate actions
in a fixed sequence and reports the differences as action effects has this
confound whether or not it says so, and most do not say so. That is a finding
about benchmark design and it belongs in the paper as one --- stated as a
requirement on reporting, not as a defence of our own design.

## L-REPEATS-001 --- At three repeats no comparison can be rejected

**Status: OPEN, and arithmetic rather than empirical.**

The smallest two-sided p an exact permutation test can attain is 2/C(2n,n) at
equal group sizes: 0.10 at three repeats against three. The strictest Holm
threshold over three action pairs at a family-wise 0.05 is 0.0167. Modes Q and R
and all five arms of part D run at three repeats, so the second comparator cannot
reject there whatever the data say.

*Permitted interpretation:* report the comparator as **unavailable** in those
matrices. A count of zero decided cells is a property of the repeat count. It
must never be presented as the band and a test agreeing.

*What would remove it:* six repeats in the ablations, which costs double and
**does not touch L-ORDER-001**. Spending it would buy a test that is still only
conditionally valid. Not recommended, and the campaign is not being extended for
it.

## L-CLOSED-LOOP-001 --- No closed-loop evaluation

**Status: OPEN by design, and no claim depends on it.**

The controller is not evaluated over full system trajectories, so availability,
agreement-violation rate and end-to-end latency are not claimed anywhere. §VII
says so. The paper reports the evaluation layer it measures and names the one it
does not.

## L-REPRO-001 --- Predictor retraining needs logs that are not published

**Status: OPEN, with the scope being made exact.**

Retraining the predictor from raw telemetry requires logs that remained on the
analysis host. The published archive carries derived data sufficient to recompute
the reported tables, which is a weaker property than full reproducibility.

*What is being done:* `data_availability.csv` records, per result, whether it is
recomputable from the public archive, and `scripts/audit_data_availability.py`
verifies each row rather than asserting it. The data-availability statement is
rewritten from the verified register. No blanket "fully reproducible" survives.

## L-SEED-001 --- One master seed in the published matrices

**Status: BOUNDED once part D lands; OPEN until then.**

The three published matrices draw their scenarios from one master seed. Part D
answers it with five derived seeds over twelve design points, under the pass
rule frozen in `CLAIMS_CONTRACT.md` C6 before its data existed. Five seeds is a
feasibility sample; if the variance split is underpowered, C6 is reported as
"consistent with, not established by" and the generalisation in the abstract is
cut rather than the experiment extended.

## L-PREFIX-001 --- Prefix identity fails under D5 at late anchors

**Status: BOUNDED, with a measured rate.**

13 of 200 cells of `d45-matrix-v1`; 5 of 72 in `bdg-b-s42`; 5 of 72 in
`bdg2-f-s42` at group sizes [17, 1], all in the two D5 design points, all at
anchors 14 or later, across two substrates and two repeat counts. Resolved by the
policy in `PREFIX_EXCLUSION.md`, frozen before the affected matrix had an
objective, with the exclusion decided on anchor hashes alone and its composition
checked for concentration in one action.

*Not explained:* why D5 at a late anchor occasionally reconstructs a different
state. The rate is the measurement; the mechanism is an open question and is
labelled as one.

## L-COST-001 --- The cost term is reduced

**Status: OPEN and disclosed.**

`J_obs` is computed with the cost component populated from disruption alone;
the other declared components are not instrumented. Every run carrying it is a
reduced-objective measurement and `analysis/jobs.py` refuses to produce it
without `--allow-partial-cost`, so the reduction cannot enter a table silently.

## L-STACK-001 --- One recorded stack id is not reproducible

**Status: OPEN and not attributed.**

`99982ee46a1999be` cannot be reproduced from the stack that stands today, and
the responsible field cannot be named, because the only full record of its
composition was overwritten by a check before the discrepancy was known. The
mode study and part D therefore run entirely on `4df75e0d98c288c5`, and the old
and new arms are **not** presented as a comparison of two substrates: two
irreconcilable ids are not two substrates.

## L-RCAEVAL-001 --- The external benchmark is not redistributed

**Status: OPEN by licence and by good practice.**

The RCAEval results are recomputed from the benchmark's own public release, which
this archive does not copy. A reader reproduces them by downloading RCAEval and
running the reanalysis script against it, which is level B: the code and the
procedure are published, the inputs come from their original publisher.

## L-PACKAGE-001 --- The accounting audit needs the raw branch tree

**Status: OPEN and bounded.**

`analysis/audit_accounting.py` reads per-branch records, not the aggregated
`jobs.csv`, so it runs against the raw tree rather than against the published
package. The package carries what the reported tables need; it does not carry
every branch directory, which would be two orders of magnitude larger. A reader
can verify the tables at level A and the audit itself only at level B, with the
raw tree available on request.

---

*The column `limitations` in `data_availability.csv` carries limitation ids and
nothing else. Prose there was how a limitation came to exist in two places with
two wordings; `tests/test_data_availability.py` now asserts that every id cited
in the register has a heading here.*
