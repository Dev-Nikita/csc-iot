# Value of the protocol: frozen analysis plan

Written 2026-10-30, **before any comparative result was computed**. Only the
column names and row counts of `structural.csv` and `jobs.csv` were inspected to
write it. Nothing here may be changed after the first run of the analysis; if a
rule turns out to be wrong, the change is recorded as a dated amendment below
together with the result it replaces, and both are reported.

This is **not** a preregistration. Five D4 decision states were already known to
show a wrong-direction structural prediction before this plan was written, and
that knowledge is what motivated the analysis. The plan is therefore *post-hoc,
protocol-frozen*: the rules are fixed before the distribution is seen, but they
were chosen by someone who had already seen five of its members. The manuscript
must say exactly that and must not call the criterion preregistered.

## The question

Does executing the alternatives from a verified-equivalent state change the
conclusion a conventional evaluation would reach, and how often?

A result in which the conclusion rarely changes is a reportable result. The
protocol still adds measured uncertainty to a conclusion that happens to agree,
and that is worth stating. No rule below is conditioned on the answer.

## Unit of analysis

One **decision anchor**: a `(scenario, anchor)` pair within one matrix. Anchors
are not pooled across matrices, because the dispersion band is a property of a
run. All eligible anchors enter; none is dropped for being uninteresting.

## The three evaluations compared, on identical units

For each anchor, over the actions executed at it:

- **P (predicted).** The action minimising `J_hat`, the structural model's
  predicted objective. This stands for an evaluation that reasons about
  alternatives instead of running them.
- **S (single execution).** The action minimising `J_obs` using **one** branch
  per action: repeat index `min(repeat)` for that cell, chosen by index and not
  by value. This stands for a benchmark in which each action was run once.
- **R (resolution-aware).** The action minimising the mean of `J_obs` over all
  repeats of that cell, with the comparison declared **unresolved** when the gap
  between the best and the second-best mean is less than or equal to the band.

All three read the same anchors, the same actions and the same objective
column. No rescaling, no reweighting, no exclusion that applies to one and not
the others.

## The band

`eta_J` is the pooled 0.95 quantile of `|J_obs(i) - J_obs(j)|` over pairs of
repeats of the same `(scenario, anchor, action)` cell, computed **within each
matrix** and used only for that matrix. Linear interpolation between order
statistics. This is the paper's existing definition, carried over unchanged.

## Classification of each anchor

Exactly one label, tested in this order:

1. `unavailable` -- fewer than two actions have at least one branch at this
   anchor, so no comparison exists.
2. `unresolved` -- the R gap is at or below `eta_J`. Reported as its own
   outcome, never merged into agreement.
3. `changed` -- resolved, and the winner differs between the compared pair.
4. `unchanged` -- resolved, and the winner is the same.

Reported as three separate contrasts: P vs S, P vs R, S vs R.

## Ties

If two actions tie exactly on the deciding quantity, the winner is the
alphabetically first action name, and the anchor is additionally counted in a
`tied` column. Ties are never resolved by looking at the other evaluation.

## Direction, not only ranking

Separately from the winner, for every `(anchor, action)` with `action != NO_OP`,
the **predicted improvement** `J_hat(NO_OP) - J_hat(action)` and the **observed
improvement** `mean J_obs(NO_OP) - mean J_obs(action)` are recorded. A pair is
`sign-flipped` when the two have opposite signs and the observed magnitude
exceeds `eta_J`. This is the quantity the five known D4 states exhibit, and it is
reported over the whole matrix, not over a selected subset.

## Reported outputs, all of them

1. Counts of every label for each of the three contrasts, per matrix.
2. The confusion matrix of P-winner against R-conclusion, including `unresolved`
   as a column.
3. The distribution of the R gap, and its ratio to `eta_J`.
4. Sign-flip counts and the full list of flipped `(anchor, action)` pairs.
5. Every count broken down by `fault_type` and by `regime`, so that an effect
   confined to one mechanism is visible as such.
6. Counts of `unavailable` and `tied`.

Zero and negative results are reported in the same table as positive ones.

## Case selection, fixed now

If one example is discussed in the manuscript, it is chosen by this rule, applied
after the distribution is computed and without further choice: among
`sign-flipped` pairs, the one with the **largest observed magnitude**; ties
broken by scenario then anchor then action, alphabetically. Whatever that rule
selects is what gets discussed, including if it is unrepresentative -- in which
case the respect in which it is unrepresentative is stated.

## What this analysis cannot establish

It compares a structural prediction and a single execution against repeated
execution **on the same testbed**. It does not show that a published benchmark
elsewhere would have reached the wrong conclusion, and it is not evidence about
field deployments. It also cannot separate "the structural model is wrong" from
"the structural model is right about a quantity the objective does not price";
the cost-instrumentation limit in the paper is the second possibility and must
stay in the discussion.

## Amendments

(none yet)
