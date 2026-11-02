#!/usr/bin/env python3
"""Emit part D's scenario sets: the twelve design points at one derived seed each.

Part D asks how much of the campaign's measurement moves with the seed. The
runner needs no change for it: the per-scenario `seed` field of the declared set
is what the runner exports as MASTER_SEED for the branch, so five seeds are five
scenario sets, not a new runner interface. What was missing was the generator.

    python3 scripts/gen_campaign_seeds.py --k 1 --out configs/scenarios-bdg-k1.json

One set per k, k = 1..5, each run as its own mode-F matrix. The factors --
mechanism, onset, severity, workload -- are copied unchanged from the campaign
set, so the only thing that differs between the five arms is the seed.

THE DERIVATION, and the ambiguity in it that had to be resolved.

CAMPAIGN_BDG.md freezes

    seed(matrix, point, k) = int(sha256(f"csc-iot-BDG-{matrix}-{point}-{k}")
                                 .hexdigest()[:8], 16),  k = 1..5

`matrix` and `point` are not defined there, and two readings were available: the
campaign's own matrix name with its c01..c12 ids, or the origin matrix and
scenario the point was copied from. This script uses the ORIGIN pair --
`b5-matrix-v2`, `s91` -- because that pair is the identity of the design point
and does not change when the campaign renames a run, while `c07` is a label this
campaign happens to use. Amendment 6 records the choice. The script prints the
exact string it hashed for every point, so the seeds are checkable by hand and
the ambiguity cannot be resolved differently by accident later.

NETEM_SEED is NOT varied. Part D as declared varies the seed of the workload,
and varying the impairment draw at the same time would confound the two. The
limitation is real and belongs in the write-up: this is seed variance of the
workload, not of the whole substrate.
"""
import argparse
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_campaign_scenarios import POINTS  # noqa: E402  the same twelve points

K_MAX = 5
CAMPAIGN_SEED = 42  # part B's seed; a derived seed must never collide with it


def derive(matrix, point, k):
    """The frozen formula, with the string it hashes returned for the record."""
    material = f"csc-iot-BDG-{matrix}-{point}-{k}"
    return int(hashlib.sha256(material.encode()).hexdigest()[:8], 16), material


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, required=True, help=f"seed index, 1..{K_MAX}")
    ap.add_argument("--base", default="configs/scenarios-bdg.json",
                    help="the campaign set whose factors are copied")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not 1 <= args.k <= K_MAX:
        sys.exit(f"REFUSED: k={args.k}; the protocol declares k = 1..{K_MAX}")

    base = json.loads(pathlib.Path(args.base).read_text())
    if base.get("purpose") != "campaign-bdg":
        sys.exit(f"REFUSED: {args.base} declares purpose "
                 f"{base.get('purpose')!r}, not campaign-bdg")
    scenarios = base["scenarios"]
    if len(scenarios) != len(POINTS):
        sys.exit(f"REFUSED: {args.base} holds {len(scenarios)} scenarios and the "
                 f"campaign declares {len(POINTS)} design points")

    out, material = [], []
    for rec in scenarios:
        origin = (rec.get("origin_matrix"), rec.get("origin_scenario_id"))
        if None in origin:
            sys.exit(f"REFUSED: {rec['scenario_id']} does not record the origin "
                     f"matrix and scenario the seed is derived from")
        if (origin[0], origin[1]) not in POINTS:
            sys.exit(f"REFUSED: {rec['scenario_id']} claims origin "
                     f"{origin[0]}/{origin[1]}, which is not a campaign point")
        seed, mat = derive(origin[0], origin[1], args.k)
        if seed == CAMPAIGN_SEED:
            sys.exit(f"REFUSED: the derived seed for {rec['scenario_id']} at "
                     f"k={args.k} is {CAMPAIGN_SEED}, which is part B's seed. "
                     f"The arms would not be independent of it.")
        new = dict(rec)
        new["seed"] = seed
        new["seed_index"] = args.k
        new["seed_material"] = mat
        new["seed_at_k0"] = rec["seed"]
        out.append(new)
        material.append((rec["scenario_id"], mat, seed))

    if len({s["seed"] for s in out}) != len(out):
        sys.exit("REFUSED: two design points derived the same seed at this k")

    doc = {
        "master_seed": CAMPAIGN_SEED,
        "purpose": "campaign-bdg",
        "seed_index": args.k,
        "note": ("part D arm k={}: the twelve campaign design points with the "
                 "per-scenario seed replaced by the derivation frozen in "
                 "CAMPAIGN_BDG.md, factors unchanged. master_seed stays 42 "
                 "because only the per-scenario workload seed is varied; the "
                 "netem draw is held fixed and this is therefore seed variance "
                 "of the workload, not of the substrate.").format(args.k),
        "derived_from": {"base": args.base,
                         "base_hash": base.get("scenarios_hash")},
        "mechanisms": sorted({s["fault_type"] for s in out}),
        "workloads": sorted({int(s["workload_level"]) for s in out}),
        "scenarios": out,
    }
    doc["scenarios_hash"] = hashlib.sha256(
        json.dumps(doc, sort_keys=True).encode()).hexdigest()[:16]
    pathlib.Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {args.out}: k={args.k}, {len(out)} design points, "
          f"hash {doc['scenarios_hash']}")
    print(f"  base {args.base} hash {base.get('scenarios_hash')}")
    for sid, mat, seed in material:
        print(f"  {sid}  sha256({mat})[:8] -> {seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
