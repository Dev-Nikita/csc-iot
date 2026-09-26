#!/usr/bin/env python3
"""Validate M2' and print diagnostic, not manuscript, action effects.

The prototype fingerprint does not expose the complete frozen failure/latency/
cost objective. J_m2_diag therefore checks branch mechanics only. With
--enforce-diagnostic-snr, dispersion is Q0.95 of all pairwise absolute differences among
repeats of the same (anchor, action) cell.
"""
import argparse
import collections
import glob
import json
import math
import os
import sys

from check_anchor import check as check_anchor

SNR_GATE = 3.0


def quantile(values, q):
    xs = sorted(values)
    if not xs:
        raise ValueError("empty quantile")
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return float(xs[lo])
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def pairwise_abs(values):
    return [abs(values[i] - values[j])
            for i in range(len(values)) for j in range(i + 1, len(values))]


def j_m2_diag(doc):
    """Higher is better; diagnostic only, never the manuscript's J_obs."""
    state = doc["state"]
    processed = sum((state.get("processed_counts") or {}).values())
    backlog = sum(q.get("length", 0)
                  for name, q in (state.get("queues") or {}).items()
                  if "backlog" in name)
    return processed - backlog


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def load(root):
    records = []
    patterns = ("s*-a*-*-r*", "a*-*-r*")
    dirs = []
    for pat in patterns:
        dirs = sorted(glob.glob(os.path.join(root, pat)))
        if dirs:
            break
    for directory in dirs:
        name = os.path.basename(directory)
        parts = name.split("-")
        # From protocol 0.9 a branch is scoped by its scenario. The completeness
        # check read three-part names only, so a complete 288-branch pilot was
        # reported as expected=96 actual=0 -- the run was fine and the verifier
        # was a version behind. A checker that cannot see the branches it is
        # checking must not be the thing that fails a matrix.
        if len(parts) == 4:
            scenario, anchor, action, repeat = parts
        elif len(parts) == 3:
            scenario, (anchor, action, repeat) = "s00", parts
        else:
            continue
        rec = {"branch_name": name, "scenario": scenario, "anchor_name": anchor,
               "action": action, "repeat": repeat, "dir": directory,
               "refused": os.path.exists(os.path.join(directory, "REFUSED.txt"))}
        for kind in ("anchor", "outcome", "branch"):
            path = os.path.join(directory, kind + ".json")
            if os.path.exists(path):
                rec[kind] = read_json(path)
        records.append(rec)
    return records


def expected_cells(root):
    meta = read_json(os.path.join(root, "matrix.json"))
    actions = meta["actions"]
    if isinstance(actions, str):
        actions = actions.split()
    # The scenario ids come from the recorded set, not from a count, so a
    # mismatch between the declared scenarios and what ran is itself visible.
    scenarios = []
    path = os.path.join(root, "scenarios.json")
    if os.path.exists(path):
        scenarios = [s["scenario_id"] for s in read_json(path)["scenarios"]]
    prefixes = [f"{sid}-" for sid in scenarios] or [""]
    expected = {f"{pre}a{a:02d}-{action}-r{repeat:02d}"
                for pre in prefixes
                for a in range(1, int(meta["anchors"]) + 1)
                for action in actions
                for repeat in range(1, int(meta["repeats"]) + 1)}
    return meta, expected, actions


def mutation_error(record):
    action = record["action"]
    if action == "NO_OP":
        return None
    branch = record.get("branch") or {}
    ack = branch.get("action_ack") or {}
    if not ack.get("applied") or ack.get("action") != action:
        return "missing verified action acknowledgement"
    state = record["outcome"]["state"]
    if action == "REROUTE":
        route = (state.get("routing") or {}).get("gw00/edge")
        if route != "edge01":
            return f"outcome route is {route!r}, expected 'edge01'"
    if action == "THROTTLE":
        limit = (state.get("rate_limits") or {}).get("gw00/admit")
        if limit != 50:
            return f"outcome admission limit is {limit!r}, expected 50"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="data/raw/<stack>/<experiment>")
    parser.add_argument("--prefix-only", action="store_true",
                        help="validate anchors only (burn-in; horizon may be zero)")
    parser.add_argument("--enforce-diagnostic-snr", action="store_true",
                        help="enforce SNR>=3 for mechanics diagnostics only; not D0")
    args = parser.parse_args()

    try:
        meta, expected, actions = expected_cells(args.root)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"invalid or missing matrix.json: {exc}", file=sys.stderr)
        return 2
    records = load(args.root)
    actual = {r["branch_name"] for r in records}
    missing, extra = sorted(expected - actual), sorted(actual - expected)
    refused = [r["branch_name"] for r in records if r["refused"]]
    required = ("anchor",) if args.prefix_only else ("anchor", "outcome", "branch")
    incomplete = [r["branch_name"] for r in records
                  if not r["refused"] and any(k not in r for k in required)]
    if missing or extra or refused or incomplete:
        print(f"INCOMPLETE MATRIX expected={len(expected)} actual={len(actual)} "
              f"missing={len(missing)} extra={len(extra)} refused={len(refused)} "
              f"incomplete={len(incomplete)}", file=sys.stderr)
        for label, values in (("missing", missing), ("extra", extra),
                              ("refused", refused), ("incomplete", incomplete)):
            if values:
                print(f"  {label}: {', '.join(values[:20])}", file=sys.stderr)
        return 1

    stack = meta.get("runtime_stack_id")
    metadata_errors = []
    for rec in records:
        for kind in required:
            doc = rec[kind]
            if doc.get("runtime_stack_id") != stack:
                metadata_errors.append(f"{rec['branch_name']} {kind}: stack mismatch")
            if kind != "branch" and doc.get("branch_id") != rec["branch_name"]:
                metadata_errors.append(f"{rec['branch_name']} {kind}: branch_id mismatch")
    if metadata_errors:
        print("METADATA FAILURE", file=sys.stderr)
        print("\n".join("  " + x for x in metadata_errors[:30]), file=sys.stderr)
        return 1

    anchor_errors = []
    for rec in records:
        for kind in ("anchor",) if args.prefix_only else ("anchor", "outcome"):
            path = os.path.join(rec["dir"], kind + ".json")
            problems = check_anchor(path, require_stack=True,
                                    expected_producers=("gw00", "gw01"))
            anchor_errors.extend(f"{rec['branch_name']} {kind}: {p}" for p in problems)
    if anchor_errors:
        print("ANCHOR INTEGRITY FAILURE", file=sys.stderr)
        print("\n".join("  " + x for x in anchor_errors[:30]), file=sys.stderr)
        return 1

    by_anchor = collections.defaultdict(list)
    for rec in records:
        by_anchor[rec["anchor_name"]].append(rec["anchor"]["hash"])
    print("PREFIX REPRODUCIBILITY")
    bad_prefix = False
    for anchor in sorted(by_anchor):
        hashes = by_anchor[anchor]
        distinct = len(set(hashes))
        print(f"  {anchor}: n={len(hashes)} distinct={distinct}")
        bad_prefix = bad_prefix or distinct != 1
    if bad_prefix:
        print("FAIL: branches did not start from exact common anchors", file=sys.stderr)
        return 1
    if args.prefix_only:
        print(f"PASS: {len(records)}/{len(expected)} prefix branches are complete and exact")
        return 0

    mutation_errors = [(r["branch_name"], mutation_error(r)) for r in records]
    mutation_errors = [(name, err) for name, err in mutation_errors if err]
    if mutation_errors:
        print("ACTION-EVIDENCE FAILURE", file=sys.stderr)
        for name, err in mutation_errors[:30]:
            print(f"  {name}: {err}", file=sys.stderr)
        return 1

    cells = collections.defaultdict(list)
    for rec in records:
        cells[(rec["anchor_name"], rec["action"])].append(j_m2_diag(rec["outcome"]))
    within, medians = [], {}
    for cell, values in sorted(cells.items()):
        within.extend(pairwise_abs(values))
        medians[cell] = quantile(values, 0.5)
    if not within:
        print("FAIL: at least two repeats per cell are required", file=sys.stderr)
        return 1
    eta = quantile(within, 0.95)

    contrasts = []
    for anchor in sorted(by_anchor):
        for i in range(len(actions)):
            for j in range(i + 1, len(actions)):
                contrasts.append(abs(medians[(anchor, actions[i])] -
                                     medians[(anchor, actions[j])]))
    signal = quantile(contrasts, 0.5) if contrasts else 0.0
    p_resolvable = (sum(x > eta for x in contrasts) / len(contrasts)) if contrasts else 0.0
    if eta == 0 and signal > 0:
        snr, verdict = math.inf, "PASS"
    elif eta == 0:
        snr, verdict = math.nan, "UNDEFINED (zero dispersion and zero signal)"
    else:
        snr = signal / eta
        verdict = "PASS" if snr >= SNR_GATE else "FAIL"

    print("\nDIAGNOSTIC ACTION SEPARATION (not manuscript J_obs)")
    print(f"  eta_J_diag (Q0.95 same-cell pairwise |delta|) = {eta:.6g}")
    print(f"  median between-action separation = {signal:.6g}")
    print(f"  P_resolvable_diag = {p_resolvable:.3f}")
    print(f"  SNR_J_diag = {snr}  gate={SNR_GATE:g}  verdict={verdict}")
    for action in actions:
        if action == "NO_OP":
            continue
        effects = [medians[(a, action)] - medians[(a, "NO_OP")]
                   for a in sorted(by_anchor) if (a, "NO_OP") in medians]
        if effects:
            print(f"  {action} - NO_OP median effect = {quantile(effects, 0.5):+.6g}")
    print("\nNOTE: J_m2_diag = processed - admission_backlog is a branch-mechanics")
    print("diagnostic. It must not be reported as the paper's lower-is-better J_obs.")
    if args.enforce_diagnostic_snr and (math.isnan(snr) or snr < SNR_GATE):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
