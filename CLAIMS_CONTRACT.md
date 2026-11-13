# What this paper claims, what each claim rests on, and what would refute it

Written 2026-11-09, while part D is running and before any of its numbers exist.
Every claim below names the table or section that carries its evidence, the
statistical unit it is asserted over, and the observation that would refute it.
A claim with no refutation criterion is not a claim, and nothing is added to this
file after the fact because a result turned out well.

The target is IEEE TDSC. The dependability stake is stated in each claim rather
than left implied, because the risk at this venue is not that the work is wrong
but that it reads as general statistics: **a recovery action chosen on evidence
that cannot distinguish it from its alternatives is a reliability decision taken
without grounds, and an evaluation that does not say so transfers that risk to
whoever deploys the winner.**

## The inferential units, declared once

| unit | what it is | what it is NOT |
|---|---|---|
| **branch** | one execution of one action from one reconstructed prefix | not an independent sample of the design point |
| **contrast cell** | one (scenario, anchor): the three actions on one prefix | the unit the band and the winner are defined on |
| **design point** | one scenario: mechanism, onset, severity, workload | the unit a claim about faults generalises over |
| **design point x seed** | one scenario at one derived seed | **the independent unit for part D** |

Anchors inside a design point share the fault schedule and the workload stream:
they are **not** independent replicates and no interval is computed by
resampling them as if they were. Repeats inside a cell are replays of one
prefix and are resampled only as the band's own cells, which is why the
bootstrap in `analysis/mode_comparison.py` resamples cells and not pairs.

Where several hypotheses are tested together --- the twelve design points of
part D are the case --- the family is declared before testing and the
per-hypothesis level is controlled by **Holm**, with the family stated in the
caption. A figure reported without a family is reported as descriptive and
labelled as such.

## C1 --- The measured resolution of this instrument binds

**Claim.** Repeated execution of the same action from the same verified-equivalent
state has a dispersion large enough, relative to between-action differences, that
a substantial share of recovery-action comparisons on this testbed is not
resolvable at the measured band.

*Unit:* contrast cell. *Evidence:* `tab:bands`, `tab:bands-single`,
`tab:bands-factored`, `tab:vop`. *Dependability stake:* the share is the share of
recovery choices the evaluation cannot justify.

**Refuted if** the unresolved share falls below **20 %** under all four declared
criteria, or if the pooled band is statistically indistinguishable from zero.
Observed 38--55 %, so the criterion is well clear of the result and is not a
threshold drawn around it.

## C2 --- A single execution always names a winner

**Claim.** A single-execution point estimate returns a strict winner at every
contrast, including every contrast the repeated-execution evidence leaves
unresolved.

*Unit:* contrast cell. *Evidence:* `tab:vop`, columns S and R.
*Dependability stake:* this is the practice the literature uses, and it is why
unresolvable comparisons are reported as differences.

**Refuted if** the single-execution winner abstains or ties at a material share
of contrasts, or if it agrees with the repeat-mean winner at essentially every
contrast while the unresolved share is also small --- the two together would mean
the repetition buys nothing.

**C2 inherits L-ORDER-001, and this is stated here rather than in a footnote.**
The resolvable share is a function of the band and of the between-action gap, and
the gap is confounded with execution position. A gap distorted by position can
make a comparison look resolvable or unresolvable when it is not, so C2 is a
claim about what *this evaluation, executed in this order,* can resolve --- and
becomes a claim about action distinguishability only once the randomised-order
arm specified in `RANDOMISED_ORDER.md` has been run and read.

Note the asymmetry that must stay in the text: repetition changes the winner at
only **2 of 454** resolved anchors. The claim is **not** that repetition gives a
different answer. It is that repetition gives the count of questions the evidence
cannot answer, which a single execution cannot report at all.

## C3 --- Three decision-time identifiability limits, each an instrumentation requirement

**Claim.** For three named quantities the decision needs, the decision-time
observation does not determine them: structurally for the first two, by
resolution for the third. Each is a requirement on instrumentation, not on
method, and each is stated as one.

*Unit:* the observation model, demonstrated by construction and then measured.
*Evidence:* `sec:results-identifiability`, including 187/187 after the
observability fix. *Dependability stake:* the limits are properties of what edge
platforms publish, so they bind any controller reading that telemetry, not only
ours.

**Refuted if** a decision-time observable already present in the recorded state
determines the quantity --- that would make it an implementation defect and not a
limit --- or if adding the named telemetry fails to restore identifiability.

**Explicitly not claimed:** that these are universal theorems. The first two are
demonstrated for the stated observation set; the third is a resolution limit and
is to be named as cost non-observability wherever the stronger word would invite
a theorem-level reading.

## C4 --- The phenomenon is not a property of our testbed

**Claim.** An independent published benchmark with repetitions of each
configuration shows the same structure: single-run comparisons resolve far fewer
contrasts than paired multi-run intervals, and repeated runs of one method flip
the top-1 verdict at a material rate.

*Unit:* fault case, and separately configuration-level mean --- reported
separately and never pooled. *Evidence:* `tab:rcaeval`,
`tab:replication-sensitivity`. *Dependability stake:* RCA methods are selected
for production on exactly these published comparisons.

**Refuted if** the single-run and multi-run readings agree at essentially all
contrasts on RCAEval.

**Explicitly not claimed:** that RCAEval validates fork-and-replay. It does not;
its runs do not start from a common verified state. It validates the more general
statement about the unit of comparison and the replication available to it, and
the text says so.

## C5 --- What the protocol's own steps are worth

**Claim.** The transport-quiescence barrier and the fresh topology per branch
either change a conclusion or they do not, measured rather than assumed.

*Unit:* contrast cell, within one substrate. *Evidence:* the three-mode
comparison, rules frozen in `MODE_COMPARISON.md` before any mode's objective was
compared. *Dependability stake:* a protocol step that provably changes nothing is
a step the field should stop paying for.

**Refuted if** a mode resolved in both arms names a different winner in a
material number of cells and the band ratio's interval excludes 1 --- then the
step is load-bearing and the paper must say so instead.

On the old substrate mode Q changed no resolved winner in 72 cells. That reading
is withdrawn as a cross-substrate statement: `99982ee46a1999be` is not
reproducible and the arms are not comparable to the new ones.

## C6 --- Whether the conclusions survive independent seeds

**Claim, stated before the data exist.** The central qualitative finding ---
a substantial share of contrasts unresolvable at the measured band, with a single
execution naming a winner at every one --- holds under independent generation of
the scenarios, not only under the one master seed the published matrices used.

*Unit:* **design point x seed**, five derived seeds per point, twelve points.
*Evidence:* part D, `bdg2-d-k1..5-s42`.

**Pass** requires all three:
1. every seed arm has an unresolved share of at least **20 %** at its own band;
2. the between-seed variance of that share does not exceed the within-seed
   variance by more than a factor of **four** --- beyond that the finding is a
   property of the seed and must be reported as one;
3. the sign of the resolvable/unresolved split is the same in every arm.

**Rule 2's operationalisation, fixed 2026-11-13 before part D's numbers were
read.** The frozen sentence names two variances without defining their units, so
the assignment is written down rather than chosen at reading time. Per (point,
seed) compute the unresolved share over that point's cells --- a 12 x 5 table
whose cells are the declared independent units. Then `sigma2_seed` is the
variance of the five seed means of those point-level shares, `sigma2_within` is
the mean over seeds of the variance of the twelve point-level shares inside that
seed, and rule 2 holds when `sigma2_seed <= 4 * sigma2_within`. Reading the seed
means as the between-seed quantity and the spread across points inside a seed as
the within-seed quantity is the only assignment consistent with "design point x
seed is the independent unit". `analysis/seed_variance.py` implements it and
`tests/test_seed_variance.py` asserts it, including a case built to fail it.

**Refuted if** any arm resolves essentially everything, or if the between-seed
spread swamps the effect.

**Inconclusive** if the arms disagree without either bound being met. Five seeds
at twelve points is a feasibility sample, not a confirmatory one. The honest
response to an inconclusive outcome is to **narrow the claim**, not to add seeds
until it clears: an experiment extended until it agrees is not evidence. If the
power at five seeds proves insufficient for the three-way variance split, C6 is
reported as "consistent with, not established by" and the generalisation in the
abstract is cut accordingly.

## C7 --- The band and a controlled test disagree, and the disagreement is the finding

**Claim.** An exact permutation test inside each contrast cell, with Holm over
the cell's three action pairs at a family-wise 0.05, decides a share of the
comparisons that the dispersion band leaves unresolved. The two comparators
answer different questions and the gap between them is not an error in either.

*Unit:* contrast cell for the test; design point for any family statement.
*Evidence:* `analysis/paired_comparator.py`, rules frozen in
`STATISTICAL_COMPARATOR.md` before it was run. *Dependability stake:* a
difference that is reproducible across replays but smaller than replay noise is
useless for choosing a recovery action in production, where one execution is all
anyone gets --- and a test reported without the band would present exactly that
difference as a reason to deploy one action over another.

**Refuted if** the test decides essentially the same cells as the band, in which
case the band adds nothing a standard test does not and the paper must say so;
or if it decides essentially nothing, in which case at five or six repeats the
test is underpowered and must be reported as such rather than as agreement.

**Explicitly not claimed:** that the test is the better comparator. Reporting it
alone would replace the question of what an evaluation can *see* with the
question of what it can *detect given enough repeats*, which is the substitution
this paper exists to object to.

**Where C7 does not apply, computed before the data were read.** The smallest
two-sided p an exact permutation test can attain at three repeats per action is
0.10, against a strictest Holm threshold of 0.0167. Modes Q and R and every arm
of part D run at three repeats, so the test cannot reject there whatever the data
say. C7 is asserted **for mode F at six repeats only**, and in the three-repeat
matrices the comparator is reported as unavailable --- never as agreement between
the band and a test, which is what a naive count of zero decided cells would
look like.

**And the qualification that travels with every p-value, in the exact words
that go into the methods section and the limitations:**

> The permutation procedure provides exact conditional inference under
> exchangeability of action labels. Because execution order was fixed and
> confounded with action identity, this assumption cannot be verified or
> guaranteed by the experimental design. Results are therefore reported as
> conditional sensitivity analyses rather than design-valid randomization tests.

So C7 is **not** a claim of design-valid inference even in mode F. It is a claim
that a conditional test, under a stated and unverifiable assumption, decides a
different set of cells than the band does. That is still worth reporting, and it
is less than a randomization test would be worth. The register entry is
`L-ORDER-001`.

The test is exact under exchangeability of the action label, which is the sharp
null of equal distributions, not of equal means. The runner executes a cell in a fixed order
and the block order is identical in every cell, so position-in-cell and action
identity are the same column and a position effect is **not identifiable from
this data**. What is measurable --- within-block trend, across-matrix drift
inside each action, and the per-action dispersion that makes a spread-driven
rejection visible --- is measured by `analysis/order_effects.py` and reported.
Randomising the action order is a change for the next matrix, not for a running
campaign.

## What is claimed nowhere in this paper

* That CSC improves availability, SLA violations or end-to-end latency. There is
  no closed-loop evaluation; §VII says so and no claim depends on it.
* That CSC outranks a reactive baseline. It does not on one fault family, and
  that is printed in `tab:decision` beside everything else.
* That the archive makes every number independently recomputable. Retraining the
  predictor from raw telemetry needs logs that stayed on the analysis host. The
  data-availability statement names exactly which figures are recomputable from
  the published archive and which are not.
* That the protocol is preregistered where it is not. Analyses frozen after
  results were seen are labelled protocol-frozen post-hoc, individually.
