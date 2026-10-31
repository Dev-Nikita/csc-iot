#!/usr/bin/env python3
"""Emit the B+D+G campaign's scenario set: the twelve points, exactly as run.

The twelve design points are fixed in CAMPAIGN_BDG.md, chosen by a rule over
design variables before any outcome was looked at. This script does not re-draw
them. It copies their declared factors -- mechanism, onset, severity, workload
and the per-scenario seed -- out of the scenario files the original matrices ran
with, so that a campaign branch at seed 42 is the same design point as an
archived branch at seed 42 and the only thing that changed is the substrate.

Redrawing them from a new master seed would have been easier and would have made
the substrate comparison meaningless.

    python3 scripts/gen_campaign_scenarios.py --out configs/scenarios-bdg.json

Run it on the analysis host: it reads data/raw/<stack>/<matrix>/scenarios.json,
which the runner wrote beside the branches.
"""
import argparse
import hashlib
import json
import pathlib
import sys

# (matrix, scenario_id) exactly as CAMPAIGN_BDG.md lists them.
POINTS = [
    ("b5-matrix-v2", "s91"), ("b5-matrix-v2", "s38"), ("b5-matrix-v2", "s102"),
    ("b5-matrix-v2", "s30"), ("b5-matrix-v2", "s15"),
    ("d45-matrix-v1", "s19"), ("d45-matrix-v1", "s05"), ("d45-matrix-v1", "s27"),
    ("d45-matrix-v1", "s28"), ("d45-matrix-v1", "s20"),
    ("d6-pilot-v2", "s04"), ("d6-pilot-v2", "s05"),
]

# Factors as recorded in the published archive, so a mismatch is caught here and
# not three thousand branches later.
EXPECT = {
    ("b5-matrix-v2", "s91"): ("D1", 8, 40, 60),
    ("b5-matrix-v2", "s38"): ("D1", 9, 60, 60),
    ("b5-matrix-v2", "s102"): ("D1", 8, 90, 60),
    ("b5-matrix-v2", "s30"): ("D3", 8, 0, 60),
    ("b5-matrix-v2", "s15"): ("D3", 10, 0, 100),
    ("d45-matrix-v1", "s19"): ("D4", 8, 40, 100),
    ("d45-matrix-v1", "s05"): ("D4", 12, 60, 100),
    ("d45-matrix-v1", "s27"): ("D4", 8, 90, 100),
    ("d45-matrix-v1", "s28"): ("D5", 8, 40, 100),
    ("d45-matrix-v1", "s20"): ("D5", 12, 60, 100),
    ("d6-pilot-v2", "s04"): ("D6", 8, 40, 100),
    ("d6-pilot-v2", "s05"): ("D6", 11, 60, 100),
}


def find_scenarios(root, matrix):
    hits = sorted(pathlib.Path(root).glob(f"*/{matrix}/scenarios.json"))
    hits = [h for h in hits if "_quarantine" not in str(h) and "_legacy" not in str(h)]
    if len(hits) != 1:
        sys.exit(f"REFUSED: {len(hits)} scenarios.json found for {matrix} under "
                 f"{root}; expected exactly one")
    return hits[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cache, out = {}, []
    for i, (matrix, sid) in enumerate(POINTS, 1):
        if matrix not in cache:
            path = find_scenarios(args.raw, matrix)
            cache[matrix] = (path, json.load(open(path)))
        path, doc = cache[matrix]
        rec = next((s for s in doc["scenarios"] if s["scenario_id"] == sid), None)
        if rec is None:
            sys.exit(f"REFUSED: {sid} is not in {path}")
        got = (rec["fault_type"], int(rec["fault_onset"]),
               int(rec["fault_severity"]), int(rec["workload_level"]))
        if got != EXPECT[(matrix, sid)]:
            sys.exit(f"REFUSED: {matrix}/{sid} declares {got}, the campaign "
                     f"protocol records {EXPECT[(matrix, sid)]}")
        new = dict(rec)
        new["scenario_id"] = f"c{i:02d}"
        new["origin_matrix"] = matrix
        new["origin_scenario_id"] = sid
        out.append(new)

    doc = {
        "master_seed": 42,
        "purpose": "campaign-bdg",
        "note": ("the twelve design points of CAMPAIGN_BDG.md, copied from the "
                 "scenario files the original matrices ran with, not redrawn"),
        "mechanisms": sorted({s["fault_type"] for s in out}),
        "workloads": sorted({int(s["workload_level"]) for s in out}),
        "scenarios": out,
    }
    doc["scenarios_hash"] = hashlib.sha256(
        json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]
    pathlib.Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {args.out}: {len(out)} design points, "
          f"mechanisms {doc['mechanisms']}, workloads {doc['workloads']}, "
          f"hash {doc['scenarios_hash']}")
    for s in out:
        print(f"  {s['scenario_id']} <- {s['origin_matrix']}/{s['origin_scenario_id']}  "
              f"{s['fault_type']} onset {s['fault_onset']} sev {s['fault_severity']} "
              f"load {s['workload_level']} seed {s['seed']}")


if __name__ == "__main__":
    main()
