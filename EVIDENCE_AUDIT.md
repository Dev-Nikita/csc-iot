# C1--C7: the verdict on each claim, against the criterion frozen for it

2026-11-13. Each verdict is read off the criterion written in
`CLAIMS_CONTRACT.md` before the numbers existed. Nothing here is a judgement
call; where a criterion was met the verdict is supported, where it was not it is
contradicted, and where the data do not reach it the verdict is inconclusive and
the claim is narrowed rather than the experiment extended.

Campaign: 5832 branches on stack `4df75e0d98c288c5` --- F 1296 at six repeats,
Q 648, R 648, part D 3240 over five derived seeds.

| claim | verdict | what decided it |
|---|---|---|
| C1 measured resolution binds | **supported** | 20 of 72 cells resolved, 72.2 % unresolved, against a refutation bound of "below 20 % unresolved" |
| C2 one execution always names a winner | **supported, and inherits L-ORDER-001** | unchanged from the archived corpus; the order confound is bounded only once the randomised arm is read |
| C3 three identifiability limits | **supported** | unchanged; 187/187 after the observability fix |
| C4 not confined to our testbed | **supported** | unchanged; RCAEval single-run 8 of 375 against 43 of 75 paired |
| C5 what the protocol's steps are worth | **supported, with two opposite answers** | Q: 0 disagreements in 72 cells. R: prefix identity destroyed in 72 of 72 cells |
| C6 survives independent seeds | **supported** | all three frozen rules hold; 9 of 12 points identical across five seeds |
| C7 band and a controlled test disagree | **supported** | top pair: band 20/72, test 35/72, band-only 0 |

## C5 --- and this is the result the mode study was for

Two protocol steps, two opposite answers, both measured rather than assumed.

**The transport-quiescence barrier changes nothing detectable.** On this
substrate mode Q agrees with F in all 19 cells resolved in both, disagrees in
none, and leaves 53 of 72 unresolved in one or both. The band ratio is 1.337
with a 95 % interval of **[0.779, 1.979]** --- inconclusive, the interval
contains 1. On the old substrate the same comparison also found no disagreement.
The barrier never fired in 648 branches, and removing it does not move a
conclusion.

**The fresh topology per branch is load-bearing in the strongest sense
available.** Mode R excludes **648 of 648 branches**: 72 of 72 cells hold nine
distinct prefix states, group sizes `[1,1,1,1,1,1,1,1,1]`, every branch in a
state of its own. No cell holds a majority prefix state, so no action comparison
in the arm is licensed and there is nothing to score. Removing that step does
not degrade the comparison, it removes the premise the comparison rests on ---
everywhere.

## C7 --- the numbers, and why the honest version is weaker than the first one

On `bdg2-f-s42`, 72 cells, family-wise 0.05, band 0.018976:

| reading | cells | share |
|---|---|---|
| resolved at the band | 20 | 27.8 % |
| **top pair decided by the test** | **35** | **48.6 %** |
| any pair decided | 62 | 86.1 % |
| both | 20 | 27.8 % |
| test only, top-pair gap under the band | 15 | 20.8 % |
| **band only, not decided** | **0** | **0.0 %** |

The like-for-like row is the top pair, because that is the pair the band judges.
The first version of the analysis printed the any-pair count --- 86.1 % --- beside
the band's 27.8 %, which compares different pairs and would have supported a
much louder claim than the data do. The any-pair count is high because the third
action usually sits far from the other two.

Two things follow, and the second is the one worth the paper's space.

**The band is strictly more conservative than a standard test.** Zero cells of
72 are resolved by the band and not decided by the test. The band is therefore
not a home-made criterion that waves differences through: everything it accepts,
an exact permutation test with Holm correction also accepts.

**Fifteen of 72 comparisons are significant and smaller than replay noise.** A
correct, exact, multiplicity-controlled test calls them real; the instrument
that produced them cannot separate them from its own dispersion. Those are the
comparisons the title is about. Significance there is a statement about
reproducibility across six replays, not about a magnitude anyone can act on ---
in production one execution is all there is.

By design point the test fails exactly where the band fails hardest: at the two
D5 points it decides 1 and 2 of 6 cells, and resolves 0. D5 is undecidable by
either criterion, which is a property of the mechanism.

## What is still open before submission

1. **The randomised-order arm.** `L-ORDER-001` is not closed and C2 inherits it.
   `scripts/run_randomised_order_arm.sh` runs it: 1296 branches, about 7.3
   hours, order drawn per cell from the design and constrained so each action
   appears in each third. The primary reading is **within** that arm, where
   action and position are independent; the comparison against `bdg2-f-s42` is
   the secondary robustness check under the two verdicts in
   `RANDOMISED_ORDER.md`.
2. **The data-availability register, verified.** Twenty-three rows, schema
   consistent, none of them yet recomputed against the published package.
3. **`L-DRIFT-001`.** Within a block the trend is nil; across the matrix
   `J_obs` drifts with rho +0.29 to +0.35 inside each action. The pooled band
   mixes cells from different hours, so part of it is host drift --- which makes
   the resolvability verdict conservative, and must be said so a reader does not
   infer the opposite.
4. **One pass over the manuscript**, after 1--3, not before. The current PDFs
   still carry the pre-campaign text: 12 pages, abstract 191 words, archive 0.7.
