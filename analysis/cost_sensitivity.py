#!/usr/bin/env python3
"""How the ranking of actions depends on a price the testbed cannot measure.

Why this exists. The objective's cost term is declared over added latency,
resource use, bandwidth and disruption. After protocol 0.25 three of those are
measured, and the measurement settled the question it was built to answer:

    action     disruption   resource   bandwidth     cost    J_obs
    NO_OP          0.2309     0.0180      0.3253   0.1914   0.4631
    REROUTE        0.1482     0.0181      0.3253   0.1639   0.4186
    THROTTLE       0.4703     0.0166      0.2864   0.2578   0.4768

`resource` is the same to three decimals under every action, because a
container's CPU is dominated by its idle loop: recruiting edge01 adds 0.0001.
`bandwidth` is identical under NO_OP and REROUTE to four decimals, because
rerouting changes the SUBJECT of a message, not how many are sent. So bandwidth
measures the volume of work and resource measures the idle baseline, and neither
prices the one thing rerouting actually does -- hold a second node open.

That price is not a measurement available from this substrate, and it is not
invented here either. It is swept. The output is the statement a reader can use:
REROUTE is preferred only while the price of holding one additional edge open
through the horizon stays below p*, and above p* the ranking changes.

What is counted, and declared as counted:

    recruited(a) = (edges that served work) - 1

0 for an action that keeps work where it is, 1 for one that spreads it over a
second edge. Derived from each branch's own per-edge served counts, identical
across the actions at a decision point except where the action differs, which is
the property the comparison needs. The horizon is the same for all actions at one
decision point, so it cancels and is not carried.

This is an assumption with a reported range, NOT a measured component. It is kept
out of `analysis/jobs.py` on purpose: `J_obs` stays what was measured, and
nothing downstream of it silently inherits a price nobody paid.
"""
import argparse
import collections
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import branches

def mean(values):
    """Local, because analysis/statistics.py shadows the stdlib module here.

    Python puts a script's own directory first on sys.path, so every script in
    analysis/ that writes `import statistics` gets the project's paired-comparison
    module instead -- which imports pandas and fails. analysis/jobs.py already
    carried this workaround with a comment naming the cause; this file was written
    without reading it.
    """
    v = list(values)
    return sum(v) / len(v) if v else float("nan")


W_FAILURE, W_LATENCY, W_COST = 0.6, 0.2, 0.2
EDGES = ("edge00", "edge01", "edge02")
ACTIONS = ("NO_OP", "REROUTE", "THROTTLE")


def recruited(observed):
    """Edges serving work beyond the first. Declared, derived, not measured."""
    active = sum(1 for e in EDGES
                 if float(observed.get(f"{e}/served", 0.0)) > 0.0)
    return max(0, active - 1)


def load(root):
    rows = {}
    for d in sorted(glob.glob(os.path.join(root, "s*-a*-*-r*"))):
        try:
            with open(os.path.join(d, "outcome.json")) as fh:
                doc = json.load(fh)
        except OSError:
            continue
        rows[os.path.basename(d)] = doc.get("observed") or {}
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="data/raw/<stack>/<experiment>")
    ap.add_argument("jobs_csv")
    ap.add_argument("--prices",
                    default="0.0,0.2,0.4,0.5,0.6,0.65,0.7,0.8,1.0",
                    help="declared price of holding ONE extra edge open, in the "
                         "same units as the other cost components: 1.0 means it "
                         "costs as much as the worst disruption measurable")
    args = ap.parse_args()

    obs = load(args.root)
    jobs = {r["branch"]: r for r in csv.DictReader(open(args.jobs_csv))}
    missing = [b for b in jobs if b not in obs]
    if missing:
        print(f"REFUSED: {len(missing)} branches in the jobs file have no "
              f"outcome on disk, e.g. {missing[0]}", file=sys.stderr)
        return 2

    prices = [float(p) for p in args.prices.split(",")]
    print(f"{len(jobs)} branches from {args.root}")
    print("\nRECRUITED EDGES BEYOND THE FIRST, by action")
    rec = collections.defaultdict(list)
    for b, r in jobs.items():
        rec[r["action"]].append(recruited(obs[b]))
    for a in ACTIONS:
        if rec[a]:
            print(f"  {a:10s} mean {mean(rec[a]):.3f}   "
                  f"values {sorted(set(rec[a]))}")
    print("\nMEAN J WITH THE RESOURCE COMPONENT REPLACED BY A DECLARED PRICE")
    print("The measured resource figure is dropped from the mean and the price"
          "\nterm put in its place, so the two are never counted twice. The price"
          "\nis per RECRUITED EDGE; 1.0 means holding one extra edge open costs as"
          "\nmuch as the worst disruption this objective can measure. The cost term"
          "\ncarries weight 0.2 and the price is one of three components, so the"
          "\nmost a price of p can add to J is 0.0667 x p.")
    print(f"\n{'price':>6s}  " + "  ".join(f"{a:>9s}" for a in ACTIONS) + "   best")
    flip = None
    for p in prices:
        means = {}
        for a in ACTIONS:
            js = []
            for b, r in jobs.items():
                if r["action"] != a:
                    continue
                d = float(r["disruption"])
                bw = float(r["bandwidth"])
                # The price is PER RECRUITED EDGE, with no division. The first
                # version divided by (EDGES - 1) = 2, which quietly redefined
                # "price 1.0" as the cost of recruiting EVERY edge and capped the
                # price's effect on J at 0.2 x 1/3 x 0.5 = 0.0333 -- below the
                # 0.0445 gap it was supposed to be able to close. "No crossing at
                # any price" was then a property of the normaliser, not of the
                # system. Clipped at 1.0 because every other component is.
                res = min(1.0, p * recruited(obs[b]))
                cost = (d + bw + res) / 3.0
                js.append(W_FAILURE * float(r["Y_ms"])
                          + W_LATENCY * float(r["L_tilde_ms"])
                          + W_COST * cost)
            if js:
                means[a] = mean(js)
        best = min(means, key=means.get)
        print(f"{p:6.2f}  " + "  ".join(f"{means.get(a, float('nan')):9.4f}"
                                       for a in ACTIONS) + f"   {best}")
        if flip is None and best != "REROUTE":
            flip = p
    print()
    if flip is None:
        print("REROUTE remains preferred at every price swept. Report that with"
              "\nthe range, and check the ceiling before believing it: the most a"
              "\nprice can add to J is 0.0667 x p_max, and if that is smaller than"
              "\nthe gap at p = 0 then no crossing was ever reachable and the"
              "\nfinding is a property of the sweep.")
    else:
        print(f"The preferred action stops being REROUTE at a declared price of"
              f" {flip:.2f}.\nBelow it rerouting wins; at and above it the"
              f" ranking changes. That bound is\nthe reportable statement: it is"
              f" a property of the price, not of the method.")
    print("\nThis sweep is an ASSUMPTION with a reported range. It is not a"
          "\nmeasurement, it is not written into J_obs, and nothing downstream"
          "\nof the objective inherits it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
