#!/usr/bin/env python3
"""Part D: does the central finding survive independent generation of the
scenarios? Implements the C6 pass rule frozen in CLAIMS_CONTRACT.md before any
of part D's numbers existed.

    python3 -I analysis/seed_variance.py <raw-root> --arm bdg2-d-k1-s42 ... \
        [--reference bdg2-f-s42]

The unit of inference is the **design point x seed**: twelve points, five
derived seeds. Anchors inside a point share the fault schedule and the workload
stream, so they are replication within the point, never independent draws.

The frozen pass rule, restated so code and protocol cannot drift:

  1. every seed arm has an unresolved share of at least 20 % at its own band;
  2. the between-seed variance of that share does not exceed the within-seed
     variance by more than a factor of four;
  3. the sign of the resolvable/unresolved split is the same in every arm.

OPERATIONALISATION of rule 2, decided here and before the numbers were read,
because the frozen sentence names two variances without defining their units:

  * per (point, seed) compute the unresolved share over that point's cells.
    That is a 12 x 5 table and its cells are the declared independent units.
  * sigma2_seed  = variance of the five seed means of those point-level shares.
  * sigma2_within = mean over seeds of the variance of the twelve point-level
    shares inside that seed.
  * rule 2 holds when sigma2_seed <= 4 * sigma2_within.

Reading the seed means as the between-seed quantity and the spread across points
inside a seed as the within-seed quantity is the only assignment consistent with
"design point x seed is the independent unit". It is written down before use.
"""
import argparse
import collections
import csv
import itertools
import json
import os
import sys

MIN_UNRESOLVED_SHARE = 0.20
MAX_VARIANCE_RATIO = 4.0


def quantile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    h = (len(xs) - 1) * p
    lo = int(h)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (h - lo) * (xs[hi] - xs[lo])


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def variance(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def load_arm(root, name):
    """jobs.csv of one arm, with its frozen prefix exclusions already applied.

    jobs.py applies the exclusions when it writes jobs.csv, so this reads what
    was scored and does not re-decide anything.
    """
    d = os.path.join(root, name)
    jobs = os.path.join(d, "jobs.csv")
    if not os.path.exists(jobs):
        raise SystemExit(
            f"REFUSED: {jobs} does not exist. Score the arm first:\n"
            f"  python3 -I analysis/jobs.py {d} --latency-max-ms 3000 "
            f"--latency-max-epochs 14 --allow-partial-cost --out {jobs}")
    excl = os.path.join(d, "prefix_exclusions.json")
    n_excluded = 0
    if os.path.exists(excl):
        with open(excl, encoding="utf-8") as fh:
            n_excluded = len(json.load(fh).get("excluded_branches", []))
    rows = []
    with open(jobs, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"point": r["scenario"], "anchor": r["anchor"],
                         "action": r["action"], "J": float(r["J_obs"]),
                         "fault": r.get("fault_type", "?")})
    if not rows:
        raise SystemExit(f"REFUSED: {jobs} has no rows")
    return rows, n_excluded


def analyse_arm(rows):
    """Band, per-cell resolvability, and the per-point unresolved share."""
    cells = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        cells[(r["point"], r["anchor"])][r["action"]].append(r["J"])
    diffs = [abs(a - b)
             for per_action in cells.values()
             for vals in per_action.values()
             for a, b in itertools.combinations(vals, 2)]
    band = quantile(diffs, 0.95)
    per_cell, per_point = {}, collections.defaultdict(list)
    for key, per_action in cells.items():
        if len(per_action) < 2:
            continue
        means = {a: mean(v) for a, v in per_action.items()}
        order = sorted(means.items(), key=lambda kv: (kv[1], kv[0]))
        gap = order[1][1] - order[0][1]
        resolved = gap > band
        per_cell[key] = {"gap": gap, "resolved": resolved,
                         "winner": order[0][0]}
        per_point[key[0]].append(resolved)
    unresolved = sum(1 for c in per_cell.values() if not c["resolved"])
    return {"band": band, "pairs": len(diffs), "cells": len(per_cell),
            "unresolved": unresolved,
            "share": unresolved / len(per_cell) if per_cell else float("nan"),
            "per_cell": per_cell,
            "point_share": {p: 1.0 - mean([1.0 if r else 0.0 for r in v])
                            for p, v in per_point.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="data/raw/<stack>")
    ap.add_argument("--arm", action="append", required=True,
                    help="a part-D arm; repeatable, one per derived seed")
    ap.add_argument("--reference", help="the seed-42 arm, reported not tested")
    args = ap.parse_args()

    print("PART D: SEED VARIANCE")
    print("C6 pass rule frozen in CLAIMS_CONTRACT.md before these numbers "
          "existed;")
    print("rule 2's operationalisation is fixed in this file's docstring.")
    print(f"unit of inference: design point x seed\n")

    arms = {}
    for name in args.arm:
        rows, n_excl = load_arm(args.root, name)
        arms[name] = analyse_arm(rows)
        arms[name]["excluded"] = n_excl

    ref = None
    if args.reference:
        rows, n_excl = load_arm(args.root, args.reference)
        ref = analyse_arm(rows)
        ref["excluded"] = n_excl

    print(f"{'arm':22s}{'band':>10s}{'cells':>7s}{'unres':>7s}{'share':>9s}"
          f"{'excl':>6s}")
    for name in args.arm:
        a = arms[name]
        print(f"{name:22s}{a['band']:10.6f}{a['cells']:7d}{a['unresolved']:7d}"
              f"{a['share']:9.1%}{a['excluded']:6d}")
    if ref:
        print(f"{args.reference + ' (ref)':22s}{ref['band']:10.6f}"
              f"{ref['cells']:7d}{ref['unresolved']:7d}{ref['share']:9.1%}"
              f"{ref['excluded']:6d}")
        print("  The reference is seed 42 and is reported, never counted as a "
              "sixth arm:")
        print("  part B drew it, and the five derived seeds exist to be "
              "independent of it.")

    # Denominators differ when a cell is lost; say so rather than compare shares
    # as if they did not.
    denoms = {name: arms[name]["cells"] for name in args.arm}
    if len(set(denoms.values())) > 1:
        print(f"\n  NOTE: the arms do not share a denominator: {denoms}. "
              f"Shares are\n  reported per arm and the counts are printed "
              f"beside them.")

    # ---- the three rules -------------------------------------------------
    print("\nRULE 1  every arm at or above "
          f"{MIN_UNRESOLVED_SHARE:.0%} unresolved")
    rule1 = True
    for name in args.arm:
        ok = arms[name]["share"] >= MIN_UNRESOLVED_SHARE
        rule1 = rule1 and ok
        print(f"  {name:22s}{arms[name]['share']:9.1%}  {'ok' if ok else 'FAIL'}")

    points = sorted({p for a in arms.values() for p in a["point_share"]})
    table = {name: [arms[name]["point_share"].get(p) for p in points]
             for name in args.arm}
    print(f"\nper-point unresolved share, the 12 x {len(args.arm)} table of "
          f"independent units")
    print(f"  {'point':8s}" + "".join(f"{n.split('-')[2]:>9s}"
                                      for n in args.arm) + f"{'mean':>9s}")
    for i, p in enumerate(points):
        vals = [table[n][i] for n in args.arm if table[n][i] is not None]
        print(f"  {p:8s}" + "".join(
            f"{table[n][i]:9.2f}" if table[n][i] is not None else f"{'-':>9s}"
            for n in args.arm) + f"{mean(vals):9.2f}")

    seed_means = [mean([v for v in table[n] if v is not None])
                  for n in args.arm]
    within = [variance([v for v in table[n] if v is not None])
              for n in args.arm]
    s2_seed, s2_within = variance(seed_means), mean(within)
    ratio = (s2_seed / s2_within) if s2_within > 0 else float("inf")
    print(f"\nRULE 2  between-seed variance <= {MAX_VARIANCE_RATIO:g} x "
          f"within-seed variance")
    print(f"  seed means of the point-level share: "
          + ", ".join(f"{m:.3f}" for m in seed_means))
    print(f"  sigma2_seed   {s2_seed:.6f}")
    print(f"  sigma2_within {s2_within:.6f}  (mean of the per-seed variances "
          f"across points)")
    print(f"  ratio         {ratio:.3f}   "
          + ("ok" if ratio <= MAX_VARIANCE_RATIO else "FAIL"))
    rule2 = ratio <= MAX_VARIANCE_RATIO

    print("\nRULE 3  the same sign of the split in every arm")
    signs = {name: (arms[name]["share"] > 0.5) for name in args.arm}
    rule3 = len(set(signs.values())) == 1
    for name in args.arm:
        print(f"  {name:22s}{'mostly unresolved' if signs[name] else 'mostly resolved'}")
    print(f"  {'ok' if rule3 else 'FAIL'}")

    print("\nVERDICT")
    if rule1 and rule2 and rule3:
        print("  C6 SUPPORTED: all three frozen rules hold.")
    elif not rule1 and all(arms[n]['share'] < 0.05 for n in args.arm):
        print("  C6 CONTRADICTED: the arms resolve essentially everything.")
    elif not rule2:
        print("  C6 CONTRADICTED: the between-seed spread swamps the effect;")
        print("  the finding is a property of the seed and must be reported as "
              "one.")
    else:
        print("  C6 INCONCLUSIVE: the arms disagree without either bound being")
        print("  met. Five seeds at twelve points is a feasibility sample. Per")
        print("  CLAIMS_CONTRACT.md the response is to NARROW the claim --")
        print("  report C6 as consistent with, not established by, and cut the")
        print("  generalisation in the abstract -- and NOT to add seeds until")
        print("  it clears.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
