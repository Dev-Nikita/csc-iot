#!/usr/bin/env python3
"""How much of the calibrated threshold is a property of which replays were seen?

Conformal risk control bounds the expected loss given the calibration outcomes.
Those outcomes are themselves measurements of a nondeterministic execution: the
ledger holds three replay repeats of every (anchor, action) cell. This asks what
the threshold would have been had the other repeats been the ones recorded.

Two resamplings, both over the repeats that were actually executed, neither
inventing a value:

  ONE   -- one repeat per cell, drawn uniformly, which is the regime a benchmark
           that runs each action once is in.
  BOOT  -- a bootstrap resample of the three repeats of each cell, which keeps
           the "any repeat failed" aggregation the point estimate uses.

Standard library only; imports neither the project CRC nor the predictor.

    python3 -I crc_replay_sensitivity.py <crc_calibration.csv> [draws]
"""
import collections
import csv
import math
import random
import sys

RUN = ("seed", "fault_type", "fault_onset", "fault_severity", "workload_level")


def one(rows, field):
    v = {r[field] for r in rows}
    if len(v) != 1:
        raise SystemExit(f"REFUSED: multiple {field}: {v}")
    return float(next(iter(v)))


def tau_hat(runs, grid, delta, u_max):
    """Largest tau whose corrected risk stays at or below delta; None if any."""
    n = len(runs)
    best, previous = None, -1.0
    for tau in grid:
        losses = []
        for anchors in runs.values():
            hits = 0
            for branches in anchors.values():
                hits += int(any(b[0] <= tau and b[1] <= u_max and b[2]
                                for b in branches))
            losses.append(hits / len(anchors))
        empirical = sum(losses) / n
        if empirical + 1e-15 < previous:
            raise SystemExit("REFUSED: reconstructed loss is not monotone")
        previous = empirical
        if (n * empirical + 1.0) / (n + 1) <= delta:
            best = tau
    return best


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    draws = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    rows = list(csv.DictReader(open(path, newline="")))
    delta, u_max = one(rows, "delta"), one(rows, "u_max")

    cells = collections.defaultdict(list)
    for r in rows:
        key = (tuple(r[k] for k in RUN), r["anchor"], r["action"])
        cells[key].append((float(r["risk"]), float(r["uncertainty"]),
                           int(r["failed"])))
    sizes = sorted({len(v) for v in cells.values()})
    grid = [-math.inf] + sorted({float(r["risk"]) for r in rows})

    def assemble(pick):
        runs = collections.defaultdict(lambda: collections.defaultdict(list))
        for (run, anchor, _action), v in cells.items():
            runs[run][anchor].extend(pick(v))
        return runs

    point = tau_hat(assemble(lambda v: v), grid, delta, u_max)
    print(f"ledger {path}")
    print(f"  rows {len(rows)}  cells {len(cells)}  repeats per cell {sizes}  "
          f"runs {len({k[0] for k in cells})}")
    print(f"  delta {delta:g}  u_max {u_max:g}")
    print(f"  point estimate, all repeats: tau_hat = "
          f"{'NONE' if point is None else f'{point:.10g}'}")

    rng = random.Random(20261030)
    for name, pick in (
            ("ONE  one repeat per cell",
             lambda v: [v[rng.randrange(len(v))]]),
            ("BOOT bootstrap of repeats",
             lambda v: [v[rng.randrange(len(v))] for _ in v])):
        vals, none = [], 0
        for _ in range(draws):
            t = tau_hat(assemble(pick), grid, delta, u_max)
            if t is None:
                none += 1
            else:
                vals.append(t)
        vals.sort()
        if not vals:
            print(f"  {name}: every draw abstained ({none} of {draws})")
            continue

        def q(p):
            h = (len(vals) - 1) * p
            lo = int(h)
            hi = min(lo + 1, len(vals) - 1)
            return vals[lo] + (h - lo) * (vals[hi] - vals[lo])

        same = sum(1 for v in vals if point is not None
                   and abs(v - point) < 1e-12)
        print(f"  {name}: {draws} draws, {none} abstained")
        print(f"      min {vals[0]:.6g}  Q0.05 {q(0.05):.6g}  median {q(0.5):.6g}"
              f"  Q0.95 {q(0.95):.6g}  max {vals[-1]:.6g}")
        print(f"      equal to the point estimate: {same} of {len(vals)}"
              f" ({same/len(vals):.1%})")
        if point:
            print(f"      ratio of the 0.05-0.95 span to the point estimate: "
                  f"{(q(0.95)-q(0.05))/point:.3f}")


if __name__ == "__main__":
    main()
