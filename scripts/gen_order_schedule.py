#!/usr/bin/env python3
"""Emit the within-cell execution order for the randomised-order arm, and the
constrained reference set that randomisation inference must use.

    python3 -I scripts/gen_order_schedule.py --scenarios configs/scenarios-bdg.json \
        --anchors 2,8,14,20,26,30 --actions "NO_OP THROTTLE REROUTE" \
        --repeats 6 --out configs/order-bdg2-forder.json

Implements RANDOMISED_ORDER.md. The draw is per (scenario, anchor) cell, from

    order_seed(scenario, anchor) = int(sha256(
        f"csc-iot-BDG-order-{scenario}-{anchor}").hexdigest()[:8], 16)

so the schedule regenerates from the design alone, and it is **constrained**:
every action must appear at least once in each third of the cell's positions. A
free permutation can leave one action mostly early by chance in a cell of
eighteen, which would reproduce the very confound this arm exists to remove.

The constraint is part of the rule. The generator rejects a draw that violates
it and draws again from the same stream --- which is rejection sampling from the
constrained set, not retrying until the data look good, because no outcome is
visible here at all. If a cell cannot be satisfied within the attempt budget the
generator REFUSES rather than relaxing the constraint.

It also writes `reference_sample`: assignments drawn from the SAME constrained
mechanism, for randomisation inference. A reference set of free permutations
would not be the distribution this design induces, so the analysis must use
this one and assert that every member satisfies the constraint.
"""
import argparse
import hashlib
import json
import pathlib
import random
import sys

MAX_DRAWS = 10000
REFERENCE_SAMPLE = 2000


def order_seed(scenario, anchor):
    material = f"csc-iot-BDG-order-{scenario}-{anchor}"
    return int(hashlib.sha256(material.encode()).hexdigest()[:8], 16), material


def thirds_ok(seq, actions):
    """Every action at least once in each third of the positions."""
    n = len(seq)
    if n % 3:
        return False
    k = n // 3
    for part in (seq[:k], seq[k:2 * k], seq[2 * k:]):
        present = {a for a, _ in part}
        if set(actions) - present:
            return False
    return True


def draw_cell(scenario, anchor, actions, repeats):
    """One cell's order, plus the reference sample from the same mechanism."""
    seed, material = order_seed(scenario, anchor)
    rng = random.Random(seed)
    base = [(a, r) for a in actions for r in range(1, repeats + 1)]
    realised, draws = None, 0
    while draws < MAX_DRAWS:
        draws += 1
        cand = base[:]
        rng.shuffle(cand)
        if thirds_ok(cand, actions):
            realised = cand
            break
    if realised is None:
        sys.exit(f"REFUSED: {scenario}-{anchor}: no assignment satisfying the "
                 f"thirds constraint in {MAX_DRAWS} draws. The constraint is "
                 f"part of the rule and is not relaxed; change the design "
                 f"instead.")
    reference = []
    while len(reference) < REFERENCE_SAMPLE:
        cand = base[:]
        rng.shuffle(cand)
        if thirds_ok(cand, actions):
            reference.append(["%s|r%02d" % (a, r) for a, r in cand])
    return {
        "scenario": scenario, "anchor": anchor,
        "seed": seed, "seed_material": material,
        "draws_to_satisfy": draws,
        "order": ["%s|r%02d" % (a, r) for a, r in realised],
        "reference_sample": reference,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--anchors", required=True, help="comma-separated")
    ap.add_argument("--actions", required=True)
    ap.add_argument("--repeats", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    actions = args.actions.split()
    anchors = [int(x) for x in args.anchors.split(",") if x.strip()]
    if (len(actions) * args.repeats) % 3:
        sys.exit(f"REFUSED: {len(actions)} actions x {args.repeats} repeats is "
                 f"not divisible into three equal parts, so the thirds "
                 f"constraint is not defined.")
    doc = json.loads(pathlib.Path(args.scenarios).read_text())
    scenarios = [s["scenario_id"] for s in doc["scenarios"]]

    cells, total_draws = [], 0
    for sid in scenarios:
        for a in anchors:
            rec = draw_cell(sid, f"a{a:02d}", actions, args.repeats)
            total_draws += rec["draws_to_satisfy"]
            cells.append(rec)

    out = {
        "note": ("within-cell execution order for the randomised-order arm; "
                 "see RANDOMISED_ORDER.md. Constrained: every action appears "
                 "in each third of a cell's positions."),
        "actions": actions, "anchors": anchors, "repeats": args.repeats,
        "scenarios_file": args.scenarios,
        "scenarios_hash": doc.get("scenarios_hash"),
        "constraint": "every action in each third of the positions",
        "reference_sample_size": REFERENCE_SAMPLE,
        "cells": cells,
    }
    out["schedule_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in out.items() if k != "cells"} |
                   {"orders": [c["order"] for c in cells]},
                   sort_keys=True).encode()).hexdigest()[:16]
    pathlib.Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out}: {len(cells)} cells, "
          f"{len(actions) * args.repeats} branches each, "
          f"hash {out['schedule_hash']}")
    print(f"  mean draws to satisfy the constraint: "
          f"{total_draws / len(cells):.2f}")
    for rec in cells[:3]:
        print(f"  {rec['scenario']}-{rec['anchor']}  "
              + " ".join(x.split("|")[0][:2] + x.split("|")[1][1:]
                         for x in rec["order"]))
    print(f"  ... and {len(cells) - 3} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
