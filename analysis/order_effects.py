#!/usr/bin/env python3
"""Is the action label confounded with execution order? Measure what can be
measured and name what cannot.

    python3 -I analysis/order_effects.py <matrix>/jobs.csv [--actions "A B C"]

The permutation test in analysis/paired_comparator.py is exact under
exchangeability of the action label within a cell. The common verified prefix
gives comparability of the starting state; it does NOT by itself give
exchangeability, because the runner executes a cell in a FIXED nested order --
scenario, anchor, action, repeat -- so each action occupies a contiguous block of
wall-clock time inside the cell.

Two consequences, and they are different:

* **Not identifiable at all.** The action order is the same in every cell
  (NO_OP, THROTTLE, REROUTE), so "first block" and "NO_OP" are the same column.
  A position-in-cell effect cannot be separated from an action effect by any
  analysis of this data. No amount of care here recovers it; only randomising
  the action order in a future matrix does, and that is a change for the next
  campaign, not a change to make mid-run.
* **Measurable.** A drift over the minutes a cell takes should leave a trend
  WITHIN each action's own block of repeats, and a drift over the hours the
  matrix takes should leave a trend across cells within one action. Both are
  computed here. If both are nil, a block-level drift large enough to matter is
  less likely -- which is weaker than excluded, and is reported as weaker.
"""
import argparse
import collections
import csv
import itertools
import random
import sys

TREND_SEED = 20261109
TREND_DRAWS = 20000


def spearman(xs, ys):
    """Rank correlation, ties averaged. Returns None when it is undefined."""
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
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def permutation_mean_abs(values, draws=TREND_DRAWS, seed=TREND_SEED):
    """Is the mean |rho| larger than relabelling would give? Sign-flip null."""
    if not values:
        return None, None
    obs = sum(abs(v) for v in values) / len(values)
    rng = random.Random(seed)
    hits = 0
    for _ in range(draws - 1):
        # Under the null of no trend, the sign of each cell's rho is arbitrary;
        # the magnitude distribution is what it is. Flipping signs tests
        # location, so the statistic is the mean of the SIGNED rho instead, and
        # the mean |rho| is reported as a descriptive magnitude beside it.
        s = sum(v if rng.random() < 0.5 else -v for v in values) / len(values)
        if abs(s) >= abs(sum(values) / len(values)):
            hits += 1
    return obs, (hits + 1) / draws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_csv")
    ap.add_argument("--actions", default="NO_OP THROTTLE REROUTE",
                    help="the runner's action order, which IS the block order")
    args = ap.parse_args()
    order = args.actions.split()

    rows = []
    with open(args.jobs_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"cell": (r["scenario"], r["anchor"]),
                         "action": r["action"],
                         "repeat": int(r["repeat"].lstrip("r")),
                         "J": float(r["J_obs"])})
    if not rows:
        sys.exit(f"REFUSED: no rows in {args.jobs_csv}")

    print("ORDER EFFECTS: what the fixed execution order permits and forbids\n")
    print(f"  runner block order inside a cell: {' -> '.join(order)}")
    print("  Every cell uses this same order, so position-in-cell and action")
    print("  identity are the SAME column. A position effect is not")
    print("  identifiable from this data by any analysis. What follows bounds")
    print("  drift; it cannot remove the confound.\n")

    # 1. within-block trend: repeat index against J_obs, inside one action
    per_block = collections.defaultdict(list)
    for r in rows:
        per_block[(r["cell"], r["action"])].append((r["repeat"], r["J"]))
    rhos = []
    for key, pts in sorted(per_block.items()):
        if len(pts) < 3:
            continue
        pts.sort()
        rho = spearman([p[0] for p in pts], [p[1] for p in pts])
        if rho is not None:
            rhos.append(rho)
    if rhos:
        mean_abs, p = permutation_mean_abs(rhos)
        signed = sum(rhos) / len(rhos)
        print(f"  within-block trend over {len(rhos)} (cell, action) blocks")
        print(f"    mean signed rho {signed:+.4f}   mean |rho| {mean_abs:.4f}   "
              f"sign-flip p {p:.4f}")
        print("    A systematic warm-up or thermal drift inside a cell would "
              "show here as a")
        print("    mean signed rho away from zero.")
    else:
        print("  within-block trend: not computable (fewer than 3 repeats)")

    # 2. across-cell drift inside one action, which removes the action effect
    print("\n  across-matrix drift, computed separately inside each action so")
    print("  the action effect is removed by construction")
    cells_in_order = sorted({r["cell"] for r in rows})
    index = {c: i for i, c in enumerate(cells_in_order)}
    for action in order:
        pts = [(index[r["cell"]], r["J"]) for r in rows if r["action"] == action]
        if len(pts) < 3:
            continue
        rho = spearman([p[0] for p in pts], [p[1] for p in pts])
        print(f"    {action:10s} n={len(pts):5d}  rho vs cell order "
              f"{rho:+.4f}" if rho is not None else f"    {action}: undefined")
    print("    Cells are ordered as the runner visited them, so this is a "
          "proxy for")
    print("    wall-clock order. A large value here is host drift over hours, "
          "not an action")
    print("    effect, because each row is one action compared with itself.")

    # 3. dispersion by action: a rejection can come from spread, not location
    print("\n  within-cell dispersion by action -- a permutation test rejects")
    print("  equality of DISTRIBUTIONS, so a difference in spread is also a")
    print("  rejection and must be visible")
    for action in order:
        spreads = []
        for (cell, a), pts in per_block.items():
            if a != action or len(pts) < 2:
                continue
            vals = [p[1] for p in pts]
            spreads.append(max(
                abs(x - y) for x, y in itertools.combinations(vals, 2)))
        if spreads:
            spreads.sort()
            med = spreads[len(spreads) // 2]
            print(f"    {action:10s} cells={len(spreads):4d}  median "
                  f"within-cell range {med:.6f}  max {spreads[-1]:.6f}")
    print("\n  If the ranges differ markedly between actions, the null the")
    print("  permutation test rejects is equality of distributions and the")
    print("  rejection must not be described as a difference in means alone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
