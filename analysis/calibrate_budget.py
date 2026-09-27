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

import branches

PREFIX = "lat_hist_ms_"
RULE_QUANTILE = 0.99
ROUND_MS = 50


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="data/raw/<stack>/<experiment>")
    ap.add_argument("--healthy-anchors", default="",
                    help="pre-0.9 runs only: the declared anchor partition. From "
                         "0.9 the pre-fault regime is a property of each branch "
                         "and this is ignored.")
    ap.add_argument("--workload", type=int,
                    help="refuse any branch whose workload level differs; the "
                         "budget is calibrated per level")
    args = ap.parse_args()
    legacy_healthy = set(args.healthy_anchors.split(",")) if args.healthy_anchors else set()

    matrix = branches.read_matrix(args.root)
    pattern = "s*-a*" if glob.glob(os.path.join(args.root, "s*-a*")) else "a*"

    # A calibration is a declared rule applied to a COMPLETED dedicated run.
    # Applied while the run is still executing it silently uses whatever branches
    # happen to exist: L=60 was once read at 20 of 40 pre-fault no-action
    # branches, which produced a plausible number from half a measurement. A
    # budget is then frozen and every later Y is scored against it, so a partial
    # read is not a smaller error than a wrong rule.
    expected = 0
    if matrix:
        try:
            expected = (int(matrix["anchor_count"]) * int(matrix["repeats"])
                        * len(str(matrix["actions"]).split())
                        * int(matrix["scenario_count"]))
        except (KeyError, TypeError, ValueError):
            expected = 0
    present = len(glob.glob(os.path.join(args.root, pattern)))
    if expected and present < expected:
        print(f"REFUSED: {present} of {expected} branches are present, so this "
              f"run is incomplete.", file=sys.stderr)
        print("  A budget calibrated on part of a run is frozen and then scores "
              "every later Y.", file=sys.stderr)
        print("  Wait for it to finish -- bash scripts/run_nightly.sh --status "
              "must show exit 0 --", file=sys.stderr)
        print("  then run this again.", file=sys.stderr)
        return 2
    hist = {}
    count = 0
    loads = set()
    for d in sorted(glob.glob(os.path.join(args.root, pattern))):
        rec = branches.read(d, matrix)
        if rec["action"] != "NO_OP":
            continue
        # "Healthy" means the branch spans no fault at all, which the regime says.
        if rec.get("legacy") and legacy_healthy:
            if f"a{rec['anchor']:02d}" not in legacy_healthy:
                continue
        elif rec["regime"] != "pre-fault":
            continue
        loads.add(rec["workload_level"])
        if args.workload is not None and rec["workload_level"] != args.workload:
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
        count += 1

    if not count:
        print("REFUSED: no pre-fault NO_OP branches under this root", file=sys.stderr)
        return 2
    if args.workload is None and len(loads) > 1:
        print(f"REFUSED: this root mixes workload levels {sorted(loads)}. The "
              "budget is calibrated per level; pass --workload.", file=sys.stderr)
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

    lvl = args.workload if args.workload is not None else (sorted(loads)[0] if loads else "?")
    print(f"PRE-FAULT NO_OP per-event latency at workload {lvl}: "
          f"{count} branches, {total:.0f} events")
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
