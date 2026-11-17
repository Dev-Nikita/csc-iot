#!/usr/bin/env python3
"""The primary reading of the randomised-order arm: estimate the position
effect where it is identifiable, and test the action effect with the mechanism
that actually assigned the actions.

    python3 -I analysis/order_within_arm.py <matrix>/jobs.csv \
        --schedule <matrix>/order_schedule.json

Why this file exists separately from analysis/order_effects.py. That script
bounds drift in a FIXED-order matrix, and it reads the repeat index as the
within-cell order proxy, which is correct only while the two coincide. In a
randomised arm the repeat index is decorrelated from time on purpose, so
reading it would analyse the one variable the schedule removed the meaning
from. Here the order is `cell_exec_index`, recorded per branch by the runner.

Three readings, in the order they matter:

1. **Position effect, action held fixed.** Inside each cell, Spearman of
   `J_obs` against `cell_exec_index` computed separately for each action, then
   pooled. Action is constant inside each correlation, so a non-zero result is
   position and nothing else. This is the quantity the fixed-order matrices
   cannot produce at all.

2. **Does adjusting for position change the verdict?** Inside each cell, remove
   a least-squares linear trend in `cell_exec_index` from `J_obs`, recompute the
   action means on the residuals, and report how many cells change winner or
   cross the band. If few do, the order confound in the fixed-order matrices is
   bounded by a measurement rather than by an argument.

3. **Design-based randomisation inference.** The sharp null is that the
   assignment of an action to a position has no effect. Its reference set is
   the set of assignments the CONSTRAINED mechanism could have produced, which
   `order_schedule.json` carries; a free permutation is not in it and using one
   would test a design that was not run. Every member is checked against the
   thirds constraint before use.
"""
import argparse
import collections
import csv
import itertools
import json
import random
import sys

SIGNFLIP_DRAWS = 20000
SIGNFLIP_SEED = 20261117


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    if len(xs) < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def detrend(points):
    """Residuals of J on position, least squares, inside one cell."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        # Every branch at the same position: nothing to detrend, and the
        # earlier version unpacked these 2-tuples as 3-tuples and would have
        # raised the first time a cell hit it.
        return [y - my for y in ys], 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return [y - (my + b * (x - mx)) for x, y in zip(xs, ys)], b


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        if "cell_exec_index" not in (rd.fieldnames or []):
            sys.exit("REFUSED: this jobs.csv has no cell_exec_index column. "
                     "Re-score the matrix with the current analysis/jobs.py; "
                     "without the execution position there is nothing here to "
                     "analyse.")
        for r in rd:
            if not r.get("cell_exec_index"):
                continue
            rows.append({"cell": (r["scenario"], r["anchor"]),
                         "action": r["action"],
                         "pos": int(r["cell_exec_index"]),
                         "J": float(r["J_obs"])})
    if not rows:
        sys.exit("REFUSED: no branch in this matrix records an execution "
                 "position. It was run under the fixed order; use "
                 "analysis/order_effects.py, which is written for that case.")
    return rows


def thirds_ok(seq, actions):
    n = len(seq)
    if n % 3:
        return False
    k = n // 3
    return all(set(actions) <= {a for a, _ in part}
               for part in (seq[:k], seq[k:2 * k], seq[2 * k:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_csv")
    ap.add_argument("--schedule", help="the matrix's order_schedule.json")
    ap.add_argument("--draws", type=int, default=2000)
    args = ap.parse_args()

    rows = load(args.jobs_csv)
    cells = collections.defaultdict(list)
    for r in rows:
        cells[r["cell"]].append(r)
    actions = sorted({r["action"] for r in rows})
    print("ORDER EFFECT WITHIN THE RANDOMISED ARM")
    print(f"  {len(cells)} cells, {len(rows)} branches, actions {actions}")
    print("  Position and action are independent inside a cell by "
          "construction, so the\n  position effect is identifiable here and is "
          "not identifiable in a fixed-order\n  matrix by any analysis.\n")

    # ---- 1. position effect with action held fixed ------------------------
    per_action = collections.defaultdict(list)
    for key, rs in cells.items():
        for a in actions:
            pts = [(r["pos"], r["J"]) for r in rs if r["action"] == a]
            rho = spearman([p[0] for p in pts], [p[1] for p in pts])
            if rho is not None:
                per_action[a].append(rho)
    print("1. POSITION EFFECT, action held fixed (Spearman of J_obs vs "
          "position inside a cell)")
    all_rhos = []
    for a in actions:
        v = per_action[a]
        all_rhos += v
        print(f"   {a:10s} cells={len(v):4d}  mean signed rho {mean(v):+.4f}  "
              f"mean |rho| {mean([abs(x) for x in v]):.4f}")
    print(f"   {'pooled':10s} cells={len(all_rhos):4d}  mean signed rho "
          f"{mean(all_rhos):+.4f}")
    # "Small" is not a verdict. Under no position effect the sign of each
    # cell's rho is arbitrary, so flipping signs gives the null distribution of
    # the mean directly, with no assumption about the shape of rho at n=6.
    rng = random.Random(SIGNFLIP_SEED)
    obs = abs(mean(all_rhos))
    hits = 1
    for _ in range(SIGNFLIP_DRAWS - 1):
        if abs(mean([r if rng.random() < 0.5 else -r
                     for r in all_rhos])) >= obs:
            hits += 1
    p_pos = hits / SIGNFLIP_DRAWS
    print(f"   sign-flip test of the pooled mean: p = {p_pos:.4f} over "
          f"{SIGNFLIP_DRAWS} draws")
    print(f"   verdict: {'a position effect is distinguishable from zero' if p_pos <= 0.05 else 'NOT distinguishable from zero at this sample'}")
    print("   A real position effect shows as a mean SIGNED rho away from "
          "zero. The mean of\n   |rho| is large at six points whatever the "
          "data do and is printed only beside it.")

    # ---- 2. does adjusting for position change the verdict? ---------------
    # The band of this arm, so a winner change can be reported where it
    # matters: a cell the evaluation could not resolve anyway has no conclusion
    # for the adjustment to overturn.
    pair_diffs = []
    for key, rs in cells.items():
        by_action = collections.defaultdict(list)
        for r in rs:
            by_action[r["action"]].append(r["J"])
        for vals in by_action.values():
            pair_diffs += [abs(a - b)
                           for a, b in itertools.combinations(vals, 2)]
    pair_diffs.sort()
    h = (len(pair_diffs) - 1) * 0.95
    lo = int(h)
    band = pair_diffs[lo] + (h - lo) * (pair_diffs[min(lo + 1, len(pair_diffs) - 1)] - pair_diffs[lo])

    changed_winner = 0
    changed_resolved = resolved_cells = 0
    gaps_before, gaps_after, slopes = [], [], []
    for key, rs in sorted(cells.items()):
        pts = [(r["pos"], r["J"]) for r in rs]
        resid, slope = detrend(pts)
        slopes.append(slope)
        before = {a: mean([r["J"] for r in rs if r["action"] == a])
                  for a in actions}
        after = collections.defaultdict(list)
        for r, e in zip(rs, resid):
            after[r["action"]].append(e)
        after = {a: mean(v) for a, v in after.items()}
        ob = sorted(before.items(), key=lambda kv: (kv[1], kv[0]))
        oa = sorted(after.items(), key=lambda kv: (kv[1], kv[0]))
        gap_before = ob[1][1] - ob[0][1]
        gaps_before.append(gap_before)
        gaps_after.append(oa[1][1] - oa[0][1])
        flipped = ob[0][0] != oa[0][0]
        changed_winner += int(flipped)
        if gap_before > band:
            resolved_cells += 1
            changed_resolved += int(flipped)
    print("\n2. ADJUSTING FOR POSITION inside each cell (linear detrend on "
          "position)")
    print(f"   band of this arm {band:.6f}; cells resolved at it "
          f"{resolved_cells} of {len(cells)}")
    print(f"   cells whose winner changes after adjustment: {changed_winner} "
          f"of {len(cells)}")
    print(f"   of those, cells that were RESOLVED at the band: "
          f"{changed_resolved} of {resolved_cells}   <-- the ones with a "
          f"conclusion to overturn")
    print("   A winner change in a cell the evaluation cannot resolve "
          "overturns nothing: there\n   was no conclusion there to begin "
          "with. Only the second line bears on a result.")
    print(f"   median best-to-runner-up gap  before {sorted(gaps_before)[len(gaps_before)//2]:.6f}"
          f"   after {sorted(gaps_after)[len(gaps_after)//2]:.6f}")
    print(f"   median within-cell slope of J on position: "
          f"{sorted(slopes)[len(slopes)//2]:+.8f}")
    print("   Few winners changing means the order confound in the "
          "fixed-order matrices is\n   bounded by a measurement rather than "
          "by an argument -- bounded, not removed.")

    # ---- 3. design-based randomisation inference --------------------------
    if not args.schedule:
        print("\n3. RANDOMISATION INFERENCE: skipped, no --schedule given.")
        return 0
    sched = json.loads(open(args.schedule, encoding="utf-8").read())
    by_cell = {(c["scenario"], c["anchor"]): c for c in sched["cells"]}
    bad = 0
    for c in sched["cells"]:
        for ref in c["reference_sample"]:
            seq = [(x.split("|")[0], x.split("|")[1]) for x in ref]
            if not thirds_ok(seq, sched["actions"]):
                bad += 1
    if bad:
        sys.exit(f"REFUSED: {bad} members of the reference set violate the "
                 f"thirds constraint the schedule was drawn under. A reference "
                 f"set that is not the design's own distribution tests a "
                 f"design that was not run.")
    print(f"\n3. RANDOMISATION INFERENCE against the constrained mechanism")
    print(f"   reference set: {sched['reference_sample_size']} assignments per "
          f"cell, every one satisfying\n   the thirds constraint (checked, "
          f"{len(sched['cells'])} cells)")

    decided = decided_top = total = 0
    for key, rs in sorted(cells.items()):
        c = by_cell.get(key)
        if c is None:
            continue
        by_pos = {r["pos"]: r["J"] for r in rs}
        if len(by_pos) != len(c["order"]):
            continue
        labels = [x.split("|")[0] for x in c["order"]]
        order_pos = list(range(1, len(labels) + 1))
        observed = {}
        for a in sched["actions"]:
            observed[a] = mean([by_pos[p] for p, l in zip(order_pos, labels)
                                if l == a])
        ov = sorted(observed.items(), key=lambda kv: (kv[1], kv[0]))
        # Two statistics, because the spread across all three actions is
        # dominated by whichever action sits far from the other two -- the same
        # defect the permutation comparator had when it printed "any pair"
        # beside the band's top-two verdict. The top-pair statistic is the
        # like-for-like one and it is reported as such.
        obs_spread = ov[-1][1] - ov[0][1]
        obs_top = ov[1][1] - ov[0][1]
        top_names = {ov[0][0], ov[1][0]}
        hits_spread = hits_top = 1
        draws = min(args.draws, len(c["reference_sample"]))
        for ref in c["reference_sample"][:draws]:
            lab = [x.split("|")[0] for x in ref]
            m = {}
            for a in sched["actions"]:
                m[a] = mean([by_pos[p] for p, l in zip(order_pos, lab)
                             if l == a])
            v = sorted(m.values())
            if (v[-1] - v[0]) >= obs_spread:
                hits_spread += 1
            # the same PAIR of actions, re-labelled by the mechanism
            pair = sorted(m[a] for a in top_names)
            if (pair[1] - pair[0]) >= obs_top:
                hits_top += 1
        total += 1
        decided += int(hits_spread / (draws + 1) <= 0.05)
        decided_top += int(hits_top / (draws + 1) <= 0.05)
    print(f"   TOP pair, the like-for-like statistic: {decided_top} of "
          f"{total} = {decided_top / total if total else float('nan'):.1%} "
          f"reject at 0.05")
    print(f"   spread over all three actions:         {decided} of {total} = "
          f"{decided / total if total else float('nan'):.1%}")
    print("   The three-action spread is driven by whichever action sits far "
          "from the other\n   two, which is a different question from the one "
          "the band answers. Use the top\n   pair; the spread is printed so "
          "the gap between them is visible.")
    print("   This is design-valid: the reference set is the mechanism that "
          "assigned the\n   actions, not an exchangeability assumption. It is "
          "the one test in this paper\n   that does not carry the "
          "L-ORDER-001 qualification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
