#!/usr/bin/env python3
"""Decide, from anchor hashes alone, which branches a split cell cannot license.

Implements PREFIX_EXCLUSION.md, which was frozen before any J_obs of the
affected matrix existed.

    python3 -I analysis/prefix_exclusion.py <matrix-root> --write
    python3 -I analysis/prefix_exclusion.py <matrix-root>            # dry run

The decision input is `anchor.json`'s hash: the state reconstructed BEFORE the
action was applied. This module does not open outcome.json, jobs.csv or
structural.csv, and tests/test_prefix_exclusion.py asserts that negating every
objective value leaves the decision unchanged.

Policy, restated so code and protocol cannot drift:

* a cell whose branches reconstruct one state is untouched;
* a cell with a strict majority state excludes the branches outside it
  (POLICY = "branch-majority");
* a cell with no strict majority excludes the whole cell, because a majority
  chosen by coin-flip would look outcome-free and would not be.
"""
import argparse
import collections
import glob
import json
import os
import sys

POLICY = "branch-majority-v1"


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cell_states(root):
    """{(scenario, anchor): {branch_name: anchor_hash}} -- anchors only."""
    out = collections.defaultdict(dict)
    for path in sorted(glob.glob(os.path.join(root, "*-a*", "anchor.json"))):
        name = os.path.basename(os.path.dirname(path))
        parts = name.split("-")
        if len(parts) == 4:
            key = (parts[0], parts[1])
        elif len(parts) == 3:
            key = ("s00", parts[0])
        else:
            continue
        try:
            out[key][name] = read_json(path)["hash"]
        except (KeyError, ValueError, OSError) as exc:
            raise SystemExit(f"REFUSED: cannot read the anchor state of {name}: "
                             f"{exc}. A branch with no readable prefix cannot "
                             f"be judged, and guessing is not available.")
    return out


def decide(states):
    """The exclusion set. Pure: hashes in, decision out."""
    cells, excluded_branches, excluded_cells = [], [], []
    for key in sorted(states):
        per_branch = states[key]
        counts = collections.Counter(per_branch.values())
        label = "-".join(key) if key[0] != "s00" else key[1]
        if len(counts) == 1:
            continue
        sizes = sorted(counts.values(), reverse=True)
        strict_majority = len(sizes) > 1 and sizes[0] > sizes[1]
        rec = {"cell": label, "branches": len(per_branch),
               "distinct_states": len(counts), "group_sizes": sizes}
        if strict_majority:
            keep_hash = counts.most_common(1)[0][0]
            drop = sorted(b for b, h in per_branch.items() if h != keep_hash)
            rec.update({"resolution": "branches excluded",
                        "majority_state": keep_hash,
                        "excluded_branches": drop,
                        "excluded_states": sorted(
                            {per_branch[b] for b in drop})})
            excluded_branches.extend(drop)
        else:
            rec.update({"resolution": "cell excluded -- no strict majority",
                        "excluded_branches": sorted(per_branch)})
            excluded_cells.append(label)
            excluded_branches.extend(sorted(per_branch))
        cells.append(rec)
    out = {"policy": POLICY, "split_cells": cells,
           "excluded_branches": sorted(excluded_branches),
           "excluded_cells": sorted(excluded_cells)}
    out["composition"] = composition(out["excluded_branches"])
    return out


def composition(names):
    """How the excluded branches spread over actions and repeats.

    This is the one way the policy could distort the comparison it exists to
    protect. The exclusion criterion cannot see the objective, but it does not
    need to: if every excluded branch were a REROUTE, then REROUTE would be
    compared on fewer replays than its rivals in exactly the cells where the
    instrument misbehaved, and the contrast would be biased without a single
    outcome having been looked at.

    So the spread is computed, recorded and judged. Concentration in one action
    is not proof of bias and is not treated as a refusal -- with five branches
    any split looks lumpy -- but it is stated, and a set that is entirely one
    action is called out as something to resolve before the comparison, not
    after.
    """
    actions, repeats = collections.Counter(), collections.Counter()
    for name in names:
        parts = name.split("-")
        if len(parts) == 4:
            actions[parts[2]] += 1
            repeats[parts[3]] += 1
    worst = max(actions.values()) if actions else 0
    return {"by_action": dict(sorted(actions.items())),
            "by_repeat": dict(sorted(repeats.items())),
            "n": len(names),
            "max_share_one_action": (worst / len(names)) if names else 0.0,
            "single_action_only": bool(actions) and len(actions) == 1}


def load(root):
    """The frozen exclusion set of a matrix, or None if it has none."""
    path = os.path.join(root, "prefix_exclusions.json")
    if not os.path.exists(path):
        return None
    doc = read_json(path)
    if doc.get("policy") != POLICY:
        raise SystemExit(
            f"REFUSED: {path} was written under policy {doc.get('policy')!r} "
            f"and this code implements {POLICY!r}. A result must not be scored "
            f"under one exclusion policy and described under another.")
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="data/raw/<stack>/<experiment>")
    ap.add_argument("--write", action="store_true",
                    help="write prefix_exclusions.json beside the manifest")
    args = ap.parse_args()

    states = cell_states(args.root)
    if not states:
        raise SystemExit(f"REFUSED: no branch anchors under {args.root}")
    decision = decide(states)
    decision["matrix"] = os.path.basename(args.root.rstrip("/"))
    decision["cells_total"] = len(states)
    decision["branches_total"] = sum(len(v) for v in states.values())

    n_b = len(decision["excluded_branches"])
    print(f"{decision['matrix']}: {decision['cells_total']} cells, "
          f"{decision['branches_total']} branches")
    print(f"  split cells: {len(decision['split_cells'])}")
    for rec in decision["split_cells"]:
        print(f"    {rec['cell']}: {rec['distinct_states']} states, sizes "
              f"{rec['group_sizes']} -> {rec['resolution']}")
    print(f"  excluded branches: {n_b}"
          + (f" ({n_b / decision['branches_total']:.2%})"
             if decision["branches_total"] else ""))
    for b in decision["excluded_branches"]:
        print(f"    {b}")
    if decision["excluded_cells"]:
        print(f"  excluded whole cells: {', '.join(decision['excluded_cells'])}")
    comp = decision["composition"]
    if comp["n"]:
        print(f"  spread over actions: {comp['by_action']}")
        print(f"  spread over repeats: {comp['by_repeat']}")
        print(f"  largest share in one action: "
              f"{comp['max_share_one_action']:.0%}")
        if comp["single_action_only"]:
            print("  WARNING: every excluded branch is the SAME action. The "
                  "criterion cannot see the")
            print("  objective, but excluding one action's replays only in the "
                  "cells where the")
            print("  instrument misbehaved would bias the contrast anyway. "
                  "Resolve this before")
            print("  the comparison, not after -- the cell-level reading is the "
                  "safe primary here.")

    path = os.path.join(args.root, "prefix_exclusions.json")
    body = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if not args.write:
        print(f"\ndry run; --write would write {path}")
        return 0
    if os.path.exists(path):
        if open(path, encoding="utf-8").read() == body:
            print(f"\n{path} already records exactly this decision")
            return 0
        print(f"\nREFUSED: {path} exists and records a DIFFERENT decision. An "
              f"exclusion set that moves is not a policy; investigate before "
              f"replacing it.", file=sys.stderr)
        return 2
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
