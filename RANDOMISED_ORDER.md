# The randomised-order arm: design and reading criterion, frozen before it runs

Written 2026-11-09, while the campaign is still executing and before this arm
exists. It is specified now precisely so that the criterion cannot be chosen
after the numbers are seen.

## Why it is required rather than deferred

`L-ORDER-001`: the runner executes a cell as scenario, anchor, action, repeat,
with the same block order in every cell of every matrix, so action identity and
execution position are the same column. The paper's central claim C2 is the
share of between-action comparisons an evaluation can resolve, and that share is
a function of the band **and** of the between-action gap. The gap carries the
confound, so C2 carries it.

An arm with the action order randomised inside each cell is the only thing that
bounds it. If the resolvable share is materially the same, the confound is
measured to be small and C2 reads as a claim about action distinguishability. If
it moves, C2 must be restated as a claim about this evaluation executed in this
order --- which is still a result, and a sharper one about benchmark design, but
a different sentence.

## The design

One matrix, mode F, on the campaign's stack, everything copied from
`bdg2-f-s42` except the order:

    name        bdg2-forder-s42
    points      the same twelve, configs/scenarios-bdg.json, hash 064f7ab679849152
    anchors     2, 8, 14, 20, 26, 30
    actions     NO_OP, THROTTLE, REROUTE
    repeats     6
    branches    12 x 6 x 3 x 6 = 1296, about 7.3 hours at 20.4 s
    seeds       master 42, netem 424242 --- unchanged

**The order rule.** Within each (scenario, anchor) cell, the sequence of the
eighteen branches is a permutation of the three actions x six repeats, drawn
from a seed derived exactly as the campaign's other seeds are:

    order_seed(scenario, anchor) = int(sha256(
        f"csc-iot-BDG-order-{scenario}-{anchor}").hexdigest()[:8], 16)

so anyone can regenerate the schedule. The runner records the realised execution
index of every branch in `startup.json` as `exec_index`, which the existing
matrices do not have and which makes the order analysable rather than merely
randomised.

**Balance, not only randomness.** A free permutation can still put one action
mostly early by chance in a small design. The draw is therefore constrained: in
each cell every action must appear at least once in the first six positions,
once in the middle six and once in the last six. The constraint is part of the
rule, not a retry until the data look good, and the generator refuses a cell it
cannot satisfy rather than relaxing it.

## The reading criterion, decided now

The comparison is `bdg2-forder-s42` against `bdg2-f-s42`: same points, same
anchors, same repeats, same stack, same seeds, one difference.

**Primary quantity:** the unresolved share over the 72 cells, each at its own
pooled band, computed by the machinery already frozen in `MODE_COMPARISON.md`
and `analysis/mode_comparison.py`, with the prefix-exclusion policy applied.

* **Confound bounded (C2 stands as written):** the unresolved shares differ by
  no more than **8 percentage points**, and no cell resolved in both arms names a
  different winner.
* **Confound material (C2 is restated):** the shares differ by more than 8
  points, or cells resolved in both arms disagree on the winner. C2 then becomes
  a claim about an evaluation executed in a declared order, the abstract's
  38--55 % range is reported as order-dependent, and the reporting requirement
  --- publish the order, randomise or balance it --- moves from a limitation to a
  result.
* **Inconclusive:** the shares differ by 8 points or less but some cell resolved
  in both arms disagrees. Reported as inconclusive. One arm at one seed cannot
  separate an order effect from ordinary run-to-run movement, and no further arm
  is run to break the tie, because an experiment extended until it agrees is not
  evidence.

Eight points is chosen against an observed unresolved share of 38--55 %: large
enough that ordinary movement between two runs of 1296 branches will not trip
it, small enough that it would catch an effect able to change the paper's
headline range. It is written here before either number exists.

## What this arm does not do

It does not make the existing matrices design-valid. Their order was fixed and
stays fixed; `L-ORDER-001` remains OPEN for them. This arm **bounds** the size
of what that confound could have done to the headline, on the same points and
the same substrate. That is the strongest thing available without re-running the
whole corpus, and the paper will say so in those words.

It also does not rescue the permutation test. That test is conditional under
`L-ORDER-001` in the existing matrices; in this arm the action label is
randomised within the cell, so there the test *is* design-valid --- and if the
two arms' test verdicts differ, that difference is itself the measurement of how
much the conditioning cost.

## When it runs

After the current campaign finishes, as its own matrix, under the run lock. Not
before: changing the runner while F, Q, R and part D are executing would split
the campaign across two designs, which is worse than the limitation it fixes.
