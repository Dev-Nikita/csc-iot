#!/usr/bin/env python3
"""How many independent experimental units are behind 8118 branches?

A branch is an execution, not an observation of a new system state. This counts
the levels of the design explicitly, so that a count of branches is never read as
a count of independent confirmations.

    python3 -I independent_units.py <zenodo-data-dir> <matrix> [<matrix> ...]
"""
import collections
import csv
import json
import sys

CFG = ("fault_type", "fault_onset", "fault_severity", "workload_level")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    root, matrices = sys.argv[1], sys.argv[2:]
    grand = collections.Counter()
    seen_cfg = collections.defaultdict(set)

    for m in matrices:
        rows = list(csv.DictReader(open(f"{root}/{m}/jobs.csv", newline="")))
        man = json.load(open(f"{root}/{m}/matrix.json"))
        scen = {r["scenario"] for r in rows}
        cfg = {tuple(r[k] for k in CFG) for r in rows}
        anchors = {(r["scenario"], r["anchor"]) for r in rows}
        actions = sorted({r["action"] for r in rows})
        repeats = sorted({r["repeat"] for r in rows})
        fams = sorted({r["fault_type"] for r in rows})

        s2c = collections.defaultdict(set)
        for r in rows:
            s2c[r["scenario"]].add(tuple(r[k] for k in CFG))
        multi = sum(1 for v in s2c.values() if len(v) > 1)
        per_scen = collections.Counter()
        for sc, _ in anchors:
            per_scen[sc] += 1

        print(f"\n{m}")
        print(f"  branches                      {len(rows)}")
        print(f"  = scenarios x anchors x actions x repeats")
        print(f"  scenarios (design points)     {len(scen)}")
        print(f"  distinct configurations       {len(cfg)}"
              f"   {'(one per scenario)' if len(cfg) == len(scen) else '(SHARED across scenarios)'}")
        print(f"  scenarios spanning >1 config  {multi}")
        print(f"  anchors per scenario          {sorted(set(per_scen.values()))}")
        print(f"  decision anchors              {len(anchors)}")
        print(f"  actions per anchor            {len(actions)}  {actions}")
        print(f"  repeats per cell              {len(repeats)}  {repeats}")
        print(f"  fault families                {fams}")
        print(f"  master_seed in manifest       {man.get('master_seed')}")
        print(f"  runtime stack                 {man.get('runtime_stack_id')}")
        print(f"  INDEPENDENT UNITS             {len(scen)} scenarios, "
              f"not {len(rows)} branches")
        grand["branches"] += len(rows)
        grand["scenarios"] += len(scen)
        grand["anchors"] += len(anchors)
        for c in cfg:
            seen_cfg[c].add(m)

    shared = {c: sorted(v) for c, v in seen_cfg.items() if len(v) > 1}
    print(f"\n{'='*66}\ntotal across the matrices listed")
    print(f"  branches   {grand['branches']}")
    print(f"  anchors    {grand['anchors']}")
    print(f"  scenarios  {grand['scenarios']}")
    print(f"  configurations appearing in more than one matrix: {len(shared)}")
    for c, v in sorted(shared.items())[:10]:
        print(f"    {c} -> {v}")


if __name__ == "__main__":
    main()
