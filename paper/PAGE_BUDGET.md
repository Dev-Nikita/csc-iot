# PAGE_BUDGET.md

Measured, not estimated. Method: compile with a stand-in Results section sized
the way the real one will be (about 950 words, two figures, two tables) and a
190-word abstract, then count how full the last page is.

| Date | State | Measured length |
|---|---|---|
| 2026-08-25 | first full draft, Sections I--IV, VI, VII written | ~6.9 pages |
| 2026-08-25 | after compression pass (II, IV, VI trimmed; III tightened) | ~6.5 pages |
| 2026-08-25 | after the methodology correction pass, second compression | **~6.6-6.7 pages** |

With Results still a placeholder the document compiles to 6 pages. That number
is not the one to plan against: the placeholder is roughly 0.5 pages shorter
than the real section will be.

The correction pass removed Proposition 1 and its proof (about 0.25 page, as
predicted) but added more than it removed: the dynamic SCM, the set-level loss
and its two-property justification, the separated objectives, the tie-aware
metrics and the set-theoretic PFR/WIR definitions. That is the right trade --
those additions are what make the paper defensible -- but it means the page
target is now met by cutting *presentation*, not mathematics.

## Where the remaining ~0.4 page comes from

Do this **after** Results exist, not before --- until the data are in, there is no
way to know which argument the Results section will need to lean on, and cutting
that argument now is the expensive mistake.

Ordered by cost to the paper, cheapest first:

1. **Section IV protocol paragraph → supplementary** (~0.15 p). The split,
   pairing and exclusion policy can be compressed to three sentences with a
   pointer, since the full protocol is already in `EXPERIMENT_PROTOCOL.md` and
   ships with the artifact.
2. **Merge Table I into prose** (~0.2 p). Only if the Related Work argument
   survives without the grid; the grid is the fastest way for a reviewer to see
   the gap, so this is a real loss.
3. ~~Proposition proof → supplementary~~ — **spent**. The proposition was removed
   entirely in the correction pass because it was not valid, not to save space.
4. **Fig. 2 → supplementary** (~0.25 p). Last resort. The architecture figure is
   what makes the systems contribution legible at a glance.
5. **Introduction paragraphs 2--3 merged** (~0.1 p). Already trimmed once;
   further cuts start removing the reason the gap exists.

Reserve 1 and 3 are close to free. 2 and 4 are not --- take them only if the
alternative is exceeding six published pages.

## Hard constraints

- IoT-J allows 8 published pages before overlength charges. Six is the internal
  target so that a revision that adds a reviewer-requested experiment does not
  push the paper over.
- If the final draft lands at 6.5 and the reserve above only reaches 6.2,
  submit at 6.2 rather than cutting an argument to reach exactly 6.0. Rounding
  to 7 published pages still costs nothing.
