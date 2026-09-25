#!/usr/bin/env python3
"""Where does the replay dispersion come from?

J_obs = 0.6 Y + 0.2 L~ + 0.2 C_obs, and only the terms that VARY between
repeats of the same cell contribute to eta_J. Before changing the design again,
this says which term carries the variation and whether it is the system or the
instrument:

  * dispersion contributed by each term, in the units of J_obs;
  * whether Y moves in discrete steps (a threshold artefact: a batch of events
    crossing the budget together) or continuously (real timing variation);
  * where the latency budget sits relative to the observed mean latency --
    a budget in the middle of the distribution turns small timing changes into
    large swings of the violated fraction.

Reads the jobs.csv written by analysis/jobs.py.
"""
import argparse
import collections
import csv
import itertools
import sys

W = {"Y_ms": 0.6, "L_tilde_ms": 0.2, "disruption": 0.2}


def q95(vals):
    v = sorted(vals)
    if not v:
        return 0.0
    return v[min(int(0.95 * (len(v) - 1) + 0.5), len(v) - 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_csv")
    ap.add_argument("--sla-ms", type=float, default=500.0,
                    help="the declared latency budget these branches ran with")
    ap.add_argument("--healthy-anchors", default="",
                    help="comma-separated anchors that lie entirely before the "
                         "fault, e.g. a01,a02,a03,a04 -- used to say what the "
                         "agreement should promise")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.jobs_csv)))
    if not rows:
        print("empty jobs.csv", file=sys.stderr)
        return 2
    cells = collections.defaultdict(list)
    for r in rows:
        cells[(r["anchor"], r["action"])].append(r)

    print(f"{len(rows)} branches, {len(cells)} cells\n")
    print("DISPERSION BY TERM (Q0.95 of within-cell pairwise |delta|, in J units)")
    total = {}
    for term, w in W.items():
        pairs = []
        for v in cells.values():
            vals = [float(r[term]) for r in v]
            pairs += [abs(a - b) * w for a, b in itertools.combinations(vals, 2)]
        total[term] = q95(pairs)
    jpairs = []
    for v in cells.values():
        vals = [float(r["J_obs"]) for r in v]
        jpairs += [abs(a - b) for a, b in itertools.combinations(vals, 2)]
    eta = q95(jpairs)
    for term, val in sorted(total.items(), key=lambda kv: -kv[1]):
        share = val / eta * 100 if eta else 0
        print(f"  {term:12s} {val:8.4f}   ({share:5.1f}% of eta_J)")
    print(f"  {'eta_J':12s} {eta:8.4f}")

    print("\nIS Y DISCRETE? (distinct values per cell, and the smallest gap)")
    steps = []
    discrete_cells = 0
    for (a, act), v in sorted(cells.items()):
        vals = sorted({round(float(r["Y_ms"]), 6) for r in v})
        if len(vals) > 1:
            gaps = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
            steps += gaps
            if len(vals) <= 3:
                discrete_cells += 1
    if steps:
        print(f"  cells with <=3 distinct Y values: {discrete_cells}/{len(cells)}")
        print(f"  smallest observed gap in Y: {min(steps):.4f}"
              f"   median gap: {sorted(steps)[len(steps)//2]:.4f}")
        print("  A few values per cell separated by a constant gap means a BATCH of")
        print("  events crosses the budget together: an instrument artefact.")
        print("  Many closely spaced values mean genuine timing variation.")

    print(f"\nLATENCY BUDGET vs OBSERVED LATENCY (budget {args.sla_ms:.0f} ms)")
    lats = sorted(float(r["mean_lat_ms"]) for r in rows)
    below = sum(1 for x in lats if x < args.sla_ms)
    print(f"  mean latency across branches: min {lats[0]:.0f}  "
          f"median {lats[len(lats)//2]:.0f}  max {lats[-1]:.0f} ms")
    print(f"  branches whose MEAN latency is below the budget: {below}/{len(lats)}")
    # This count mixes healthy and degraded branches, and a degraded branch is
    # SUPPOSED to exceed the budget -- that is the failure being measured. Only
    # the healthy branches can say whether the instrument is mis-set, and they
    # are examined below. The earlier wording here read as a warning about the
    # budget whatever the branches were doing.
    print("  Degraded branches are expected above the budget: that is the failure")
    print("  being measured. Whether the budget is mis-set is decided on healthy")
    print("  NO_OP branches only, below.")
    if args.healthy_anchors:
        healthy = set(args.healthy_anchors.split(","))
        # NO_OP only. "Healthy" and "degraded" describe the SYSTEM, and the
        # only branches that show the system without intervention are the
        # no-action ones. Including THROTTLE here compared the fault against
        # branches the action itself had overloaded: a throttle applied at a
        # pre-fault anchor caps admission below the offered load for the whole
        # horizon, so its latency exceeded the fault's. That is how the healthy
        # set came to have a HIGHER p95 (1197 ms) than the degraded set (1057),
        # which is impossible for states of the system and was a defect in this
        # comparison, not in the design.
        noop = [r for r in rows if r["action"] == "NO_OP"]
        hv = sorted(float(r["mean_lat_ms"]) for r in noop if r["anchor"] in healthy)
        dv = sorted(float(r["mean_lat_ms"]) for r in noop if r["anchor"] not in healthy)
        if hv and dv:
            def pct(v, p):
                return v[min(int(p * (len(v) - 1) + 0.5), len(v) - 1)]
            print("\nHEALTHY vs DEGRADED LATENCY (NO_OP branches only, branch mean, ms)")
            print(f"  healthy  n={len(hv):3d}  p50 {pct(hv,.5):6.0f}  p95 {pct(hv,.95):6.0f}"
                  f"  max {hv[-1]:6.0f}")
            print(f"  degraded n={len(dv):3d}  p50 {pct(dv,.5):6.0f}  p95 {pct(dv,.95):6.0f}"
                  f"  max {dv[-1]:6.0f}")
            overlap = sum(1 for x in dv if x <= hv[-1]) / len(dv)
            print(f"  degraded branches inside the healthy range: {overlap:.0%}")
            print("\n  An agreement is a promise the system keeps WHILE HEALTHY. A budget")
            print("  below the healthy distribution is violated by a working system, which")
            print("  makes the failure term measure the budget rather than the failure.")
            # The budget rule is NOT this. Protocol 0.6 replaced the branch-mean
            # p95 rule with the healthy per-event p99, because the agreement is a
            # promise about each event and branch means understate the per-event
            # spread by roughly the emission window. Printing the superseded rule
            # beside the frozen budget invited reading it as a recommendation to
            # lower the budget, which is the one move the integrity rules forbid
            # after results are in view.
            superseded = 50 * (int(pct(hv, .95) / 50) + 1)
            print(f"  For reference only, the SUPERSEDED 0.4 rule (healthy branch-mean")
            print(f"  p95) would give {superseded:.0f} ms. It is not the rule: the budget is")
            print(f"  frozen at {args.sla_ms:.0f} ms by the healthy per-event p99 of protocol 0.6,")
            print(f"  measured on a dedicated calibration run. Use analysis/calibrate_budget.py.")
            if overlap > 0.3:
                print("\n  WARNING: the degraded state largely overlaps the healthy one. No")
                print("  choice of threshold separates them. The fault has not developed")
                print("  far enough within the horizon -- that is a design problem, not an")
                print("  instrument one, and moving the budget will not fix it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
