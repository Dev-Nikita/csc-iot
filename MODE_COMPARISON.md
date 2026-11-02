# The rules for comparing the campaign modes, frozen before any objective
# outcome of one mode was compared with another

Written and committed 2026-11-02, before `analysis/mode_comparison.py` was run
on anything. What had been looked at by that point, and nothing else: the
branch counts of each matrix, the number of refused branches, the number of
prefix-split cells, the per-branch wall time, and whether the ablation flag was
recorded. No `J_obs` of one mode had been placed beside the `J_obs` of another.
That ordering is the only reason the comparison below means anything, and it is
the reason these rules are a file and not a commit message.

## What the comparison is for

Mode F is the protocol. Q removes the transport-quiescence barrier, R removes
the fresh topology per branch. The campaign asks whether either removal changes
a conclusion the paper draws. It is not asking whether the ablated run is
"worse": a protocol step that provably changes nothing is a step the paper
should stop claiming credit for, and that is a publishable answer.

## The unit, and the statistic on it

The unit is a **contrast cell**: one (scenario, anchor) pair, holding the three
actions. 12 design points x 6 anchors = 72 cells per mode.

Per cell, per mode, from that mode's own `jobs.csv`:

* `mean J_obs` per action over the mode's repeats;
* the **winner** = argmin of those means, ties broken by action name, which is
  the frozen rule already used by `analysis/value_of_protocol.py`;
* the **gap** = second-smallest minus smallest mean;
* `resolved` = gap > the mode's own pooled band.

The **pooled band** of a mode is Q0.95 of the absolute differences of all
within-cell pairs of repeats of the same action, computed inside that mode and
nowhere else. A mode that is noisier must be read against its own noise; using
F's band on Q's objectives would charge Q's noise to Q's conclusions twice.

## Repeat count is held fixed, not compared

F ran 10 repeats; Q and R ran 3. Ten repeats give a tighter mean and a different
pooled band, so a comparison of F-at-10 against Q-at-3 measures the repeat count
as much as the ablation. Therefore:

**Every F quantity that enters a mode comparison is computed from F's repeats
`r01`, `r02`, `r03` only, selected by repeat index.** Not by value, not by
agreement with anything, and the choice is recorded here before the selection
was made. F's full 10-repeat numbers are still reported, separately and labelled
`F10`, because they are the better estimate of F itself; they are not the thing
Q and R are compared against.

## What counts as a changed conclusion

For each cell present in both modes:

* **agreement** -- both modes resolved it and named the same winner;
* **disagreement** -- both modes resolved it and named different winners;
* **unresolved in one or both** -- not evidence of agreement or of
  disagreement, and reported as its own category, never folded into either.

The headline of the ablation is the count of disagreements among cells resolved
in both modes, and the change in the resolvable fraction (resolved cells / 72).
A mode that resolves far fewer cells has had its discriminating power removed
even where it never names a different winner, and that is the more likely shape
of the result here.

Two secondary readings, both decided now:

* the **band ratio** `eta_mode / eta_F3`. The band is the measurement's own
  resolution, so an ablation that inflates it has degraded the measurement
  whatever the winners do.
* the **shift in mean J_obs** per cell, pooled over actions, reported as the
  median and the Q0.10/Q0.90 of (mode - F3). An ablation that moves every
  objective in one direction is doing something systematic; one that scatters
  them is adding noise.

## The null mode, N

N is the false-positive calibration and costs nothing. From F's 10 repeats, each
cell's repeats of one action are split by index into `r01..r05` and `r06..r10`
and the two halves are treated as if they were two different actions. There is
no effect there to find by construction, so the fraction of such null contrasts
called resolvable is the procedure's own false-positive rate. At a Q0.95 band
the expectation is about 5 %; materially more than that and the resolvability
claims in the paper are overstated and the band is the wrong statistic.

N is computed from F at 10 repeats, because it needs the five-and-five split.
Its rate is a property of the band procedure, not of the ablations.

## The prefix mode, A'

The paper's action comparison is licensed by prefix identity within a cell. A'
asks what the answer would be if that were not required: the headline is
recomputed twice, once over all cells and once over cells whose anchor states
were identical, and the difference is the contribution of the split cells. The
split cells were counted before these rules were written (F 5 of 72, Q 4 of 72);
their identities were not used to decide any rule above.

## What the analyzer refuses to do

* It refuses a matrix with `VOID.txt` beside its manifest.
* It refuses a matrix whose manifest says `mode: reset` while every branch
  recorded `tore_down_first`, which is the void run's signature.
* It refuses two matrices with different `runtime_stack_id`, or different
  scenario-set hashes. Ablating one thing means holding everything else.
* It refuses to compare F at 10 repeats against an ablation, per the rule above.

A refusal exits non-zero and prints what is wrong. None of these are warnings.

## What this comparison cannot answer

Both ablations were run once, at seed 42, on three repeats. A difference in the
resolvable fraction of a few cells is inside what a single run of a stochastic
system can produce, and this design has no replicate of the ablation itself to
say otherwise. Conclusions are therefore limited to: no disagreement at all, or
a disagreement large enough to be visible against the band ratio. An ablation
that lands in between is reported as inconclusive and stays that way until it is
run again at another seed.

---

## Amendment 1, 2026-11-02: two defects in the rules above, found by running them

Both were found in the first output of `analysis/mode_comparison.py`, on mode Q.
Both are defects in the rules, not in the result, and both are recorded here
with the numbers the original rules produced, because an amendment that hides
what it replaces is a rewrite.

**The null mode as specified is not a matched test, and it flatters the band.**
N splits F's ten repeats five against five and compares the two means. The
pooled band is Q0.95 over *single-repeat* pairwise differences. A difference of
two five-repeat means is tighter than a difference of two single repeats by
construction, so the comparison is a mean against a band built for individuals,
and it will report a near-zero false-positive rate whatever the data do. It did:
0 of 216 null contrasts exceeded the band, against the 5 % the Q0.95 band is
supposed to admit, with the largest null gap 0.017291 against a band of
0.021611.

That number must not be reported as the procedure's false-positive rate, and it
is exactly the kind of number that gets reported because it is favourable.

The matched test uses the same repeat count as the comparison it calibrates:
F's `r01..r03` against `r04..r06`, read against the **F3** band, which is the
band the Q and R comparisons actually use. `N5` is kept and printed beside it,
labelled as the unmatched reading it is.

**The band is a point estimate and the comparison turns on its ratio.** Q's band
came out 1.202 times F3's, and 1.333 times on prefix-clean cells, which the
rules above would read as a degraded measurement. But Q0.95 of 648 pairwise
differences has sampling error of its own, and a ratio of two such estimates
from one run of each mode has more. With no replicate of either mode, the rules
as written cannot tell a real inflation from the spread of the estimator.

The band therefore gets an interval: 2000 bootstrap resamples **of contrast
cells**, with replacement, recomputing Q0.95 over the resampled cells' pairs,
reported as a 95 % percentile interval for each mode's band and for the ratio.
Cells are the resampling unit because repeats within a cell are not independent
of each other. The interval is a statement about this run's precision, not about
the ablation's reproducibility, which still needs a second seed.

A band ratio whose interval contains 1 is **not** evidence that the ablation
inflated the band, and will be reported as inconclusive however suggestive the
point estimate looks.
