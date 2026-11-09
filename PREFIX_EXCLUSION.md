# The exclusion policy for cells whose prefix is not identical, frozen before
# any objective outcome of the affected matrix was computed

Written 2026-11-09. What had been looked at when this was written, and nothing
else: the anchor hashes of `bdg2-f-s42`, the count of cells holding more than one
prefix state, the group sizes inside those cells, and which design points and
anchors they fall on. **No `J_obs` of `bdg2-f-s42` exists yet** --- the chain
stopped before `jobs.py` ran, so nothing in this file can have been chosen to
suit an outcome. That ordering is the only thing that makes an exclusion policy
honest, and it is why this is a file rather than a decision taken at analysis
time.

## What happened

`bdg2-f-s42` completed all 1296 branches with zero refusals. Five of its 72
contrast cells reconstructed two prefix states instead of one, each with group
sizes **[17, 1]**: a single branch out of eighteen started from a state that was
not equivalent to the other seventeen.

    c09-a14   c09-a20   c09-a26   c09-a30   c10-a26

`c09` and `c10` are the campaign's two **D5** design points (origin
`d45-matrix-v1/s28` and `/s20`). The anchor list is 2, 8, 14, 20, 26, 30, and
every affected anchor is 14 or later.

**This is a reproduction, not a surprise.** The same phenomenon was found and
quantified on the old substrate: 13 of 200 cells of `d45-matrix-v1`, all D5, all
at late anchors, with the impact on every reported result measured and nil. The
old-stack campaign arm `bdg-b-s42` split in 5 of 72 cells, three of which
(`c09-a26`, `c09-a30`, `c10-a26`) are the same cells as here. So prefix identity
under D5 at late anchors fails at a low rate on three different runs, two
different repeat counts and two different stacks. It is a property of the
mechanism and the instrument, not of a bad night.

## Why a branch, not a cell, is the unit of exclusion

A cell holding two prefix states does not license an action comparison: the
actions were not applied to the same state. There are three ways to respond and
the choice must be made on a criterion that cannot see the objective.

1. **Branch-level (primary).** Exclude the branches that are not in their cell's
   majority prefix state. The criterion is the **anchor hash alone** --- the
   state reconstructed before the action was applied --- which is recorded
   before the action runs and is independent of `J_obs` by construction. Five
   branches of 1296 are excluded, 0.39 %, and all 72 cells survive with 17
   repeats instead of 18.
2. **Cell-level (sensitivity).** Drop all five cells entirely, 67 of 72 remain.
3. **A-prime (sensitivity).** Keep everything and require nothing, which is the
   mode already defined in `MODE_COMPARISON.md`.

The primary is branch-level because the exclusion criterion is a documented
technical failure of the replay --- the branch did not start where its cell
started --- and because dropping a whole cell throws away seventeen valid
replays to punish one. **All three are computed and all three are reported.** If
they agree, the question is closed. If they disagree, that disagreement is the
result and is reported as one; it is not a menu.

**No tie-breaking by preference.** If a split cell has no strict majority --- two
groups of equal size --- there is no licensed comparison in it and the **whole
cell** is excluded under the primary policy as well. A majority chosen by
coin-flip would be an outcome-free-looking choice that is not one.

## What is recorded, and what the code may not do

`analysis/prefix_exclusion.py` writes `prefix_exclusions.json` beside the
matrix manifest, listing the policy version, every affected cell, its group
sizes, the excluded branch names and the anchor hashes that decided it. The
analysis reads that file; it never recomputes the decision while scoring. The
file is written once: a second run that would produce different content refuses
rather than overwrite, because an exclusion set that moves is not a policy.

The script reads `anchor.json` and nothing else. It cannot open `outcome.json`,
`jobs.csv` or `structural.csv`, and a test asserts that the decision is
unchanged when the objective values are replaced by their negatives.

## What this does not fix

Excluding the minority branch makes the cell comparable. It does not explain why
D5 at a late anchor occasionally reconstructs a different state, and the paper
must not imply that it does. The rate is the measurement: 5 of 1296 here, 13 of
200 cells there, and the mechanism is a stated open item --- a candidate is that
the gateway admission fault's interaction with the per-branch topology rebuild
leaves a timing-dependent residue that the recorded state exposes at late
anchors but not at early ones. That is a hypothesis, it is labelled as one, and
it is not tested in this paper.

---

## Addendum, 2026-11-09: the composition of the exclusion set, checked

The criterion cannot see the objective. That is necessary and it is not
sufficient: if every excluded branch happened to be the same action, that action
would be compared on fewer replays than its rivals precisely in the cells where
the instrument misbehaved, and the contrast would be biased without a single
outcome having been looked at. The spread is therefore computed, recorded in
`prefix_exclusions.json` and judged.

For `bdg2-f-s42` the five excluded branches are

    c09-a14-REROUTE-r06   c09-a20-NO_OP-r06   c09-a26-NO_OP-r05
    c09-a30-THROTTLE-r03  c10-a26-THROTTLE-r01

which is NO_OP 2, THROTTLE 2, REROUTE 1, at repeats 1, 3, 5, 6 and 6. No action
holds more than 40 % of the set and no repeat index dominates. The divergence is
therefore not tied to a particular action and not tied to the last repeat of a
cell, which is what a residue left by the preceding branch would look like. The
branch-level reading is safe to use as the primary here.

Had the set been confined to one action, the cell-level exclusion would have
been the correct primary instead, and the tool says so rather than leaving the
reader to notice. This rule is stated now, with the composition in hand but with
no objective computed, so it cannot be a rationalisation later.
