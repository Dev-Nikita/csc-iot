# The second comparator: what is estimated, which unit is independent, which
# error is controlled

Frozen 2026-11-09, before it was run on anything.

The dispersion band answers one question: *is this difference larger than two
replays of the same action typically differ by?* That is a property of the
instrument and it is the right question for deciding whether an evaluation can
see a difference at all. It is **not** a test, it controls no error rate, and the
paper has never said otherwise --- but it has also not carried the other
comparator beside it, and a reviewer is entitled to ask for one. This file
defines it.

Both are reported. They are not alternatives and the weaker of the two is not
dropped when it disagrees: a cell where the band says "unresolvable" and the test
says "significant" is a cell where the difference is smaller than replay noise
yet consistent across replays, and that is a real and interesting state, not a
contradiction to be resolved by choosing.

## What is estimated

For one contrast cell --- one (scenario, anchor), where every branch starts from
the same verified-equivalent prefix --- and one pair of actions `a`, `b`:

    Delta(a,b) = mean of J_obs over a's repeats - mean over b's repeats

`J_obs` is lower-is-better, so `Delta < 0` means `a` is better.

## Which unit is independent, and the pairing that does NOT exist

Every repeat in a cell replays the **same** prefix. So repeat `i` of action `a`
and repeat `i` of action `b` share no random draw that the design assigns to the
index `i`: they are not a matched pair, and treating them as one would invent a
correlation the experiment does not have. **Within a cell the repeats are
exchangeable between actions, and the pairing is at the level of the cell** ---
the common prefix --- not of the repeat index.

This matters for the external review's §3.2, which asked for a paired interval.
The pairing it asks for is real but it sits one level up: cells are paired across
actions by construction, because all three actions are executed from the same
prefix. The test below uses exactly that and nothing more.

| level | question | independent unit | replication |
|---|---|---|---|
| L1, per cell | do these two actions differ on this prefix? | the cell | its repeats |
| L2, across points | do they differ in this fault family? | the **design point** | its cells |

Anchors inside a design point share the fault schedule and the workload stream.
They are not independent, so L2 resamples **design points**, never anchors and
never branches.

## L1: an exact permutation test inside the cell

Under the null that the action label carries no information about `J_obs` within
the cell, the labels are exchangeable. The test enumerates every way of splitting
the cell's `n_a + n_b` observations into groups of `n_a` and `n_b`, computes
`|Delta|` for each, and reports

    p = (number of splits with |Delta| >= |Delta_observed|) / (number of splits)

two-sided, with the observed split included in both counts.

**The attainable floor, corrected 2026-11-09 and computed rather than reasoned
about.** An earlier version of this file said the smallest attainable two-sided
p at six repeats is 1/924. That is wrong, and so is the blanket rule that it is
always 2/C(n,k). With **equal** group sizes every split pairs with its
complement, which swaps the groups and leaves `|Delta|` unchanged, so every
attainable p is an even multiple of 1/C(2n,n); with **unequal** sizes the
complement has the wrong size and is not in the reference set. Enumerated:

| repeats | reference set | smallest two-sided p |
|---|---|---|
| 3 vs 3 | 20 | **0.1000** |
| 5 vs 5 | 252 | 0.0079 |
| 6 vs 6 | 924 | 0.0022 |
| 5 vs 6 | 462 | 0.0022 |

**The consequence is operational and it is the important part of this
correction.** The strictest Holm threshold over three action pairs at a
family-wise 0.05 is 0.0167. At three repeats per action the floor is 0.10, so
**no comparison can be rejected at any usable level whatever the data say.**
Modes Q and R and every arm of part D run at three repeats. The second
comparator is therefore available for **mode F at six repeats only**, and a
count of zero decided cells in the three-repeat matrices is a property of the
repeat count, not a finding about the data, and above all not agreement between
the band and a test. `analysis/paired_comparator.py` computes the floor before
reading the data and prints UNAVAILABLE instead of a zero. Enumeration is used whenever the
split count is at most 20000; beyond that the reference set is sampled with a
seed fixed in this file (`PERM_SEED = 20261109`) and the output says so and gives
the count, because a p-value from a sampled reference set is an estimate and must
be labelled as one.

A permutation test was chosen over a bootstrap interval because the null here is
exchangeability of a label, which permutation tests exactly, and because at five
or six observations a bootstrap percentile interval has coverage no one should
rely on.

## Which error is controlled, and over what family

The family is **the cell**: the three pairwise comparisons among NO_OP, THROTTLE
and REROUTE at one (scenario, anchor). Within it the per-comparison level is
controlled by **Holm** at a family-wise 0.05. A cell is called *decided* when at
least one pair survives Holm.

When a family across cells is reported --- "in how many of the 72 cells is some
pair decided" --- the count is descriptive and is printed as a count, with the
per-cell family-wise level stated. It is not a second controlled test, and it is
not presented as one.

## The assumptions, stated so a reviewer can check them

1. **Exchangeability of the action label within a cell under the null, and the
   null is equality of DISTRIBUTIONS, not of means.** This is a correction: a
   permutation test is exact for the sharp null that the label carries no
   information. It is *not* exact for "equal means with unequal dispersion",
   which is the Behrens--Fisher situation, and this paper is about dispersion,
   so the possibility is live rather than academic. A rejection therefore means
   the label carries information --- in location, in spread, or in both --- and
   `analysis/order_effects.py` prints the within-cell range per action so a
   rejection driven by spread is visible instead of being described as a
   difference in means.

   The common verified prefix gives comparability of the starting state. It does
   **not** by itself give exchangeability, and this file previously implied that
   it did.
2. **Execution order is fixed and the confound it creates is partly not
   identifiable.** The runner executes a cell as scenario, anchor, action,
   repeat, so each action holds a contiguous block of wall-clock time, and the
   block order is the same in every cell. "First block" and "NO_OP" are
   therefore the same column: **a position-in-cell effect cannot be separated
   from an action effect by any analysis of this data.** Randomising the action
   order fixes it for a future matrix; it is not a change to make mid-campaign,
   and it is listed as such.

   What is measurable is measured: `analysis/order_effects.py` reports the
   within-block trend of `J_obs` against repeat index, and the across-matrix
   drift computed separately inside each action so the action effect is removed
   by construction. Both being nil makes a block-level drift large enough to
   matter less likely, which is weaker than excluded and is reported as weaker.
   The test is therefore **exact conditional on the declared exchangeability
   null**, and that qualification travels with every number it produces.
3. **No assumption of normality, equal variance or symmetry.** None is used.
4. **Nothing about independence across cells** at L1. Dependence between cells of
   one design point is handled at L2 by resampling design points.
5. **The test is about `J_obs` as measured.** A reduced cost term is still a
   reduced cost term; see the objective's own caveat.

## What this comparator cannot do

It cannot make a difference that is smaller than replay dispersion into a
difference an evaluation can see. A pair that is significant at p = 0.01 and
smaller than the band is a difference this instrument reproduces but cannot
resolve against its own noise --- a statement about consistency, not magnitude,
and useless for choosing a recovery action in production, where one execution is
all anyone gets. **That is the paper's point, and the comparator sharpens it
rather than softening it.** Reporting the test alone would replace a question
about what an evaluation can see with a question about what it can detect given
enough repeats, and those are not the same question.
