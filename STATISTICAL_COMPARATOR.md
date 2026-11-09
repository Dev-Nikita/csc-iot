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

two-sided, with the observed split included in both counts. At six repeats per
action this is 924 splits and the test is **exact**; the smallest attainable
p-value is 1/924 = 0.00108, which is small enough for a 5 % level after
correction over three action pairs. Where a prefix exclusion leaves five repeats
against six, it is 462 splits and still exact. Enumeration is used whenever the
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

1. **Exchangeability of the action label within a cell under the null.** This is
   what the common verified prefix buys and it is the whole reason the test is
   available. If prefix identity fails in a cell, the assumption fails with it,
   which is why `prefix_exclusions.json` is applied before this runs.
2. **No assumption of normality, equal variance or symmetry.** None is used.
3. **Nothing about independence across cells** at L1. Dependence between cells of
   one design point is handled at L2 by resampling design points.
4. **The test is about `J_obs` as measured.** A reduced cost term is still a
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
