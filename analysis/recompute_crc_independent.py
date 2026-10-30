#!/usr/bin/env python3
"""Recompute CRC from an exported ledger without project CRC/predictor imports."""
import argparse
import csv
import math


RUN_FIELDS = ("seed", "fault_type", "fault_onset", "fault_severity",
              "workload_level")


def one_value(rows, field):
    values = {r[field] for r in rows}
    if len(values) != 1:
        raise SystemExit(f"REFUSED: ledger has multiple {field} values: {values}")
    return float(next(iter(values)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("--curve")
    args = ap.parse_args()
    rows = list(csv.DictReader(open(args.ledger, newline="")))
    if not rows:
        raise SystemExit("REFUSED: empty CRC ledger")
    delta, u_max, theta = (one_value(rows, x)
                           for x in ("delta", "u_max", "theta"))
    runs = {}
    for r in rows:
        key = tuple(r[k] for k in RUN_FIELDS)
        runs.setdefault(key, {}).setdefault(r["anchor"], []).append(r)
    n = len(runs)
    grid = [-math.inf] + sorted({float(r["risk"]) for r in rows})
    curve, best, previous = [], None, -1.0
    for tau in grid:
        losses = []
        for anchors in runs.values():
            hits = 0
            for branches in anchors.values():
                hits += int(any(float(b["risk"]) <= tau
                                and float(b["uncertainty"]) <= u_max
                                and int(b["failed"]) == 1
                                for b in branches))
            losses.append(hits / len(anchors))
        empirical = sum(losses) / n
        if empirical + 1e-15 < previous:
            raise SystemExit("REFUSED: reconstructed loss is not monotone")
        previous = empirical
        corrected = (n * empirical + 1.0) / (n + 1)
        feasible = corrected <= delta
        if feasible:
            best = tau
        curve.append((tau, empirical, corrected, feasible))
    print(f"rows={len(rows)} runs={n} theta={theta:.10g} "
          f"u_max={u_max:.10g} delta={delta:.10g}")
    print("tau_hat=" + ("NONE" if best is None else f"{best:.10g}"))
    if best is not None:
        chosen = next(x for x in curve if x[0] == best)
        print(f"empirical_risk={chosen[1]:.10g} "
              f"corrected_risk={chosen[2]:.10g}")
    if args.curve:
        with open(args.curve, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["tau", "empirical_risk", "corrected_risk", "feasible"])
            for tau, empirical, corrected, feasible in curve:
                w.writerow(["-inf" if math.isinf(tau) else f"{tau:.17g}",
                            f"{empirical:.17g}", f"{corrected:.17g}",
                            int(feasible)])


if __name__ == "__main__":
    main()
