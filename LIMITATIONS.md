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

*What this touches, corrected 2026-11-09 after the claim below was put too
strongly.* An earlier version of this entry said the band "barely" feels the
confound and can absorb only two minutes of drift. That is too strong. Process
warm-up, accumulated host state and caching all act inside a block, and
sequential execution does not make repeats independent of each other --- it only
makes them share a position rather than differ by one.

The honest ordering is:

* **within-action dispersion** --- the band --- remains a meaningful measured
  quantity: it is the reproducibility of executing *that* action under *this*
  protocol, which is what it is defined as. It is **less exposed** than the
  gap, not nearly immune.
* **the between-action gap** is exposed: action identity and block position are
  the same column.
* **the resolvable fraction** is a function of both, so **it is not protected
  either**. A gap distorted by position can make a comparison look resolvable or
  unresolvable when it is not.

C1 therefore stands as a result about measured reproducibility of execution.
**C2 --- the share of comparisons an evaluation can resolve --- inherits this
confound and must not be read as establishing true distinguishability of action
effects.** That is a correction to this register and to the claims contract, not
a softening of wording.

*What can be checked now, and is:* `analysis/order_effects.py` --- within-block
trend of `J_obs` against repeat index, across-matrix drift computed inside each
action so the action effect is removed by construction, and per-action
within-cell dispersion so that a rejection driven by spread is visible. Both
trends being nil makes a block-level drift large enough to matter **less likely,
not excluded**, and is reported that way.

*What would remove it:* a randomised or balanced action order inside each cell,
fixed before the run. See `RANDOMISED_ORDER.md`, which specifies that matrix ---
one arm, 1296 branches, about 7.3 hours --- and the criterion it is read against,
written before it is run. It is **not** a change to the running campaign:
changing the runner mid-campaign would split the campaign across two designs,
which is worse than the limitation.

*And whether it must be run before submission.* If the central claim were only
that repeated execution has measurable dispersion, this could be future work.
The central claim is C2, the share of between-action comparisons an evaluation
can resolve, and that share inherits the confound. So the randomised arm is
**required before submission**, not deferred --- the alternative is betting that
a reviewer raises it only at major revision, and that is the bet this project has
already lost three times.

*Permitted interpretation, and this wording travels with every p-value the
permutation test produces:*

> The permutation procedure provides exact conditional inference under
> exchangeability of action labels. Because execution order was fixed and
> confounded with action identity, this assumption cannot be verified or
> guaranteed by the experimental design. Results are therefore reported as
> conditional sensitivity analyses rather than design-valid randomization tests.

*A hypothesis, labelled as one, and NOT claimed in the paper.* It is plausible
that a fixed action order is what an evaluation harness ordinarily does, and that
any evaluation executing candidates in a fixed sequence and reporting the
differences as action effects carries this confound whether or not it says so.
**That is a conjecture about other people's harnesses and this campaign
establishes none of it.** Making it a contribution would need one of two things
we do not have: a systematic reading of published benchmarking protocols showing
the practice is widespread and uncontrolled, or an experiment showing that
changing the order alone changes the comparative conclusion.

What this campaign does establish is narrower and is the only thing stated: **in
this design, action identity is perfectly confounded with execution position.**
It is a demonstrable methodological limitation of one testbed and a requirement
on reporting --- publish the execution order, randomise or balance it --- and it
is not evidence of an industry-wide defect. The paper says exactly that and no
more.

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

## L-DRIFT-001 --- Host drift over the matrix, measured

**Status: BOUNDED, with numbers.**

`analysis/order_effects.py` on `bdg2-f-s42`:

* **within-block trend nil.** Over 216 (cell, action) blocks the mean signed
  Spearman rho of `J_obs` against repeat index is **+0.0126**, sign-flip
  p = 0.67. There is no warm-up or thermal trend inside a block.
* **across-matrix drift real and sizeable.** Computed inside each action
  separately, so the action effect is removed by construction, rho against cell
  order is **+0.29 (NO_OP), +0.35 (THROTTLE), +0.34 (REROUTE)**. `J_obs` rises
  monotonically over the seven hours the matrix takes, in all three actions
  alike.

*What this means for each quantity, and the two readings differ.*

The action contrast is formed **inside** a cell, over minutes, and at that scale
the trend is nil --- which bounds the practical reach of `L-ORDER-001` without
removing the confound, since position and action remain the same column. The
**pooled band**, by contrast, is pooled **across** cells drawn from different
hours of the run, so the hours-scale drift enters it: part of the pooled
dispersion is host drift rather than replay nondeterminism. That inflates the
band, which makes the resolvability verdict *conservative* --- more comparisons
are called unresolvable than replay noise alone would require. The paper must
say this rather than let a reader infer the opposite.

*Per-action dispersion, which bears on the permutation test's null.* Median
within-cell range 0.0089 (NO_OP), 0.0100 (THROTTLE), 0.0080 (REROUTE); maxima
0.062, 0.081, 0.061. The three are close, so a rejection driven by unequal
spread rather than by location is unlikely here --- the Behrens--Fisher concern
is live in principle and small in this data, and both halves of that sentence
are reported.

*What would remove it:* a matrix whose cell order is randomised as well as its
action order, which would spread each cell's hours-scale position at random.
That is a further design change and is not in `RANDOMISED_ORDER.md`, which
addresses the within-cell order only. Noted as a known remaining limitation
rather than silently folded in.
