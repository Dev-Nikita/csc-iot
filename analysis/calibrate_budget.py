#!/usr/bin/env python3
"""Derive the latency budget from HEALTHY NO_OP branches, per event.

The rule is fixed in EXPERIMENT_PROTOCOL.md section 2a (protocol 0.6) and
declared before any per-event latency was observed:

    budget = healthy per-event p99, rounded UP to the next 50 ms multiple.

This script reads only NO_OP branches at the declared healthy anchors. It
refuses to read anything else, because a budget chosen with the actions in
view is a budget chosen for its effect on the comparison.
"""
import argparse
import glob
import json
import math
import os
import sys

PREFIX = "lat_hist_ms_"
RULE_QUANTILE = 0.99
ROUND_MS = 50


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="data/raw/<stack>/<experiment>")
    ap.add_argument("--healthy-anchors", required=True,
                    help="comma list, e.g. a01,a02,a03 -- the declared partition")
    args = ap.parse_args()
    healthy = set(args.healthy_anchors.split(","))

    hist = {}
    branches = 0
    for d in sorted(glob.glob(os.path.join(args.root, "a*"))):
        anchor, action, _ = os.path.basename(d).split("-")
        if action != "NO_OP" or anchor not in healthy:
            continue
        with open(os.path.join(d, "outcome.json")) as fh:
            obs = json.load(fh).get("observed") or {}
        found = False
        for k, v in obs.items():
            metric = k.split("/", 1)[-1]
            if metric.startswith(PREFIX):
                b = int(metric[len(PREFIX):])
                hist[b] = hist.get(b, 0) + v
                found = True
        if not found:
            print(f"REFUSED: {d} has no per-event latency histogram; the "
                  "binary predates it", file=sys.stderr)
            return 2
        branches += 1

    if not branches:
        print("REFUSED: no healthy NO_OP branches under this root", file=sys.stderr)
        return 2

    total = sum(hist.values())
    bins = sorted(hist)

    def quantile(q):
        acc = 0.0
        for b in bins:
            acc += hist[b]
            if acc >= q * total:
                return b + 25  # upper edge of the 25 ms bin: conservative
        return bins[-1] + 25

    def above(ms):
        return sum(v for b, v in hist.items() if b >= ms) / total

    print(f"HEALTHY NO_OP per-event latency: {branches} branches, {total:.0f} events")
    for q in (0.50, 0.90, 0.95, 0.99, 0.999):
        print(f"  p{q*100:g}  <= {quantile(q):5d} ms")
    print(f"  max bin     {bins[-1]}-{bins[-1]+25} ms")
    print("\nfraction of HEALTHY events above a budget")
    for ms in range(400, 801, 50):
        print(f"  {ms:4d} ms   {above(ms):6.3f}")
    budget = int(math.ceil(quantile(RULE_QUANTILE) / ROUND_MS) * ROUND_MS)
    print(f"\nRULE (declared): p{RULE_QUANTILE*100:g} rounded up to {ROUND_MS} ms"
          f"  ->  budget = {budget} ms")
    print(f"healthy events that budget already counts as failures: {above(budget):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
