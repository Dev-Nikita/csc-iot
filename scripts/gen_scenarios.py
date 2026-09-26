#!/usr/bin/env python3
"""Draw the declared scenario factors, reproducibly, before any run.

A scenario is (mechanism, onset, severity, workload, seed). Through protocol 0.7
every branch carried one fault at one onset with one severity, which made the
anchor index an exact proxy for fault age: a predictor could score well by
memorising a schedule that never varied. The factor exists to remove that.

The draw is a pure function of the master seed, so the scenario set is part of
the declared configuration rather than something chosen after seeing results.
"""
import argparse
import hashlib
import json
import random
import sys

# Declared levels (protocol 0.9 section 11a).
ONSET_RANGE = (8, 24)          # inclusive epochs
SEVERITY_LEVELS = (40, 60, 90)  # post-onset serve-per-epoch, from 150
WORKLOAD_LEVELS = (60, 100, 140)  # events per epoch

# Mechanisms. D1 and D3 are expressible with the node flags that exist; D2 needs
# netem re-applied part-way through a branch and is not implemented, so it is
# refused here rather than quietly emitted and silently run as D1.
MECHANISMS = {
    "D1": "edge capacity degradation at onset",
    "D3": "edge stall at onset (serve rate to zero)",
}
NOT_IMPLEMENTED = {
    "D2": "ingress impairment ramp: requires netem re-application mid-branch",
}


def draw(master_seed, n, mechanisms, workloads):
    rng = random.Random(master_seed)
    out = []
    for i in range(1, n + 1):
        # Mechanism, severity and workload are assigned round-robin rather than
        # drawn. A random draw of 24 scenarios gave 12 at the mildest severity
        # and 4 at the strongest, which leaves the parameter-shift split of B5
        # with too few scenarios on the held-out side to say anything. Onset
        # stays random: it is the factor whose whole purpose is to stop the
        # anchor index from indexing the fault's age.
        mech = mechanisms[(i - 1) % len(mechanisms)]
        onset = rng.randint(*ONSET_RANGE)
        sev = 0 if mech == "D3" else SEVERITY_LEVELS[(i - 1) % len(SEVERITY_LEVELS)]
        load = workloads[(i - 1) % len(workloads)]
        seed = rng.randrange(1, 2**31 - 1)
        out.append({
            "scenario_id": f"s{i:02d}",
            "fault_type": mech,
            "fault_onset": onset,
            "fault_severity": sev,
            "workload_level": load,
            "seed": seed,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--master-seed", type=int, required=True)
    ap.add_argument("--mechanisms", default="D1",
                    help="comma list from " + ",".join(sorted(MECHANISMS)))
    ap.add_argument("--workloads", default="100",
                    help="comma list from " + ",".join(str(w) for w in WORKLOAD_LEVELS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    mechs = args.mechanisms.split(",")
    for m in mechs:
        if m in NOT_IMPLEMENTED:
            print(f"REFUSED: mechanism {m} is declared but not implemented "
                  f"({NOT_IMPLEMENTED[m]}). Emitting it would run something else "
                  f"under its name.", file=sys.stderr)
            return 2
        if m not in MECHANISMS:
            print(f"REFUSED: unknown mechanism {m}", file=sys.stderr)
            return 2
    loads = [int(w) for w in args.workloads.split(",")]
    for w in loads:
        if w not in WORKLOAD_LEVELS:
            print(f"REFUSED: workload {w} is not a declared level "
                  f"{WORKLOAD_LEVELS}", file=sys.stderr)
            return 2
    budgets = json.load(open("configs/budgets.json"))["budgets_ms"]
    for w in loads:
        if str(w) not in budgets:
            print(f"REFUSED: workload {w} has no calibrated latency budget in "
                  f"configs/budgets.json. Calibrate it first with "
                  f"analysis/calibrate_budget.py; borrowing another level's "
                  f"budget would make Y measure the load.", file=sys.stderr)
            return 2

    scenarios = draw(args.master_seed, args.n, mechs, loads)
    doc = {
        "master_seed": args.master_seed,
        "declared_levels": {
            "onset_range": list(ONSET_RANGE),
            "severity_levels": list(SEVERITY_LEVELS),
            "workload_levels": list(WORKLOAD_LEVELS),
            "mechanisms": mechs,
        },
        "scenarios": scenarios,
    }
    blob = json.dumps(doc, sort_keys=True).encode()
    doc["scenarios_hash"] = hashlib.sha256(blob).hexdigest()[:16]
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print(f"wrote {args.out}: {len(scenarios)} scenarios, "
          f"hash {doc['scenarios_hash']}")
    for s in scenarios:
        print(f"  {s['scenario_id']}  {s['fault_type']}  onset {s['fault_onset']:2d}  "
              f"severity {s['fault_severity']:3d}  load {s['workload_level']:3d}  "
              f"seed {s['seed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
