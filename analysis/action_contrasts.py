#!/usr/bin/env python3
"""Per-anchor action contrasts: the three findings of Section V-D.

These were the last figures in the manuscript with no script behind them. They
were recomputed by hand once, which is how the peak came to be reported as the
value at an intermediate anchor rather than the maximum.

    python3 analysis/action_contrasts.py <matrix-root> [--eta 0.0164]

Prints, per anchor, the median J_obs of each action and the NO_OP-minus-REROUTE
and THROTTLE-minus-NO_OP contrasts, each with a bootstrap interval, and then the
three summary figures the manuscript states: the pre-fault null, the peak of the
rerouting contrast, and its value at the deepest anchor.

The band is a declared argument rather than recomputed here, because the
preregistered band is the pooled one emitted by analysis/make_tables.py and a
second implementation of it would be a second definition.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from band_sensitivity import boot_ci, median  # noqa: E402


def load(root):
    cells = {}
    with open(os.path.join(root, "jobs.csv")) as fh:
        for r in csv.DictReader(fh):
            key = (r.get("scenario", "s00"), r["anchor"], r["action"])
            cells.setdefault(key, []).append(float(r["J_obs"]))
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--eta", type=float, default=0.0164,
                    help="the preregistered pooled band for this matrix")
    ap.add_argument("--gate", type=float, default=3.0,
                    help="a contrast counts as resolvable at gate x eta")
    args = ap.parse_args()

    cells = load(args.root)
    scenarios = sorted({s for s, _, _ in cells})
    if len(scenarios) != 1:
        sys.exit("REFUSED: %d scenarios in %s. These contrasts are defined per "
                 "anchor on a single-scenario matrix; on a factored one 'the "
                 "deepest anchor' is not one thing." % (len(scenarios), args.root))
    sc = scenarios[0]
    anchors = sorted({a for _, a, _ in cells})

    print("anchor  NO_OP    REROUTE  THROTTLE  NO_OP-RER   CI               "
          "THR-NO_OP  x eta")
    rer, thr = {}, {}
    for a in anchors:
        g = {act: cells.get((sc, a, act)) for act in ("NO_OP", "REROUTE", "THROTTLE")}
        if not g["NO_OP"]:
            continue
        mn = median(g["NO_OP"])
        row = [a, "%.4f" % mn]
        if g["REROUTE"]:
            c = mn - median(g["REROUTE"])
            lo, hi = boot_ci(g["NO_OP"], g["REROUTE"], n=2000)
            rer[a] = (c, lo, hi)
            row += ["%.4f" % median(g["REROUTE"])]
        else:
            row += ["---"]
        row += ["%.4f" % median(g["THROTTLE"]) if g["THROTTLE"] else "---"]
        row += ["%+.4f" % rer[a][0] if a in rer else "---"]
        row += ["[%+.4f,%+.4f]" % rer[a][1:] if a in rer else ""]
        if g["THROTTLE"]:
            t = median(g["THROTTLE"]) - mn
            thr[a] = t
            row += ["%+.4f" % t, "%.1f" % (t / args.eta)]
        print("%-7s %-8s %-8s %-9s %-11s %-17s %-10s %s" % tuple(row + [""] * (8 - len(row) + 1))[:8])

    print()
    first = anchors[0]
    if first in rer:
        c, lo, hi = rer[first]
        print("pre-fault null, %s          : %+.4f  CI [%+.4f, %+.4f]" % (first, c, lo, hi))
    if rer:
        peak = max(rer, key=lambda a: rer[a][0])
        c, lo, hi = rer[peak]
        print("peak rerouting contrast, %s : %+.4f  CI [%+.4f, %+.4f]" % (peak, c, lo, hi))
        last = anchors[-1]
        if last in rer:
            c2, lo2, hi2 = rer[last]
            print("deepest anchor, %s          : %+.4f  CI [%+.4f, %+.4f]" % (last, c2, lo2, hi2))
            print("peak and deepest intervals overlap: %s"
                  % ("yes" if not (hi < lo2 or hi2 < lo) else "no"))
    if thr:
        a0, aN = anchors[0], anchors[-1]
        if a0 in thr:
            print("throttling at %s            : %+.4f = %.1f x eta" % (a0, thr[a0], thr[a0] / args.eta))
        if aN in thr:
            res = "resolvable" if thr[aN] / args.eta >= args.gate else "below the gate"
            print("throttling at %s            : %+.4f = %.1f x eta, %s"
                  % (aN, thr[aN], thr[aN] / args.eta, res))


if __name__ == "__main__":
    main()
