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

# Run under `python3 -I` the script's own directory is NOT on sys.path, so a
# sibling import fails with ModuleNotFoundError. The documented recompute
# commands use -I deliberately -- it is how a script that reads downloaded data
# is run safely -- so every analysis that imports a sibling puts its own
# directory on the path itself rather than depending on how it was invoked.
# This cost a scoring run of five part-D arms.
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import branches

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
    # The patterns used to be ("s*-a*-*-r*", "a*-*-r*"), which assumed every
    # scenario id begins with "s". A campaign whose points are named c01..c12 to
    # keep them distinct from the archived ones produced 2160 good branches and
    # was reported as expected=2160 actual=0: the second time this checker has
    # failed a healthy matrix by not recognising the names in it. Widening the
    # glob again would only move the assumption, so the prefixes come from the
    # recorded scenario set, and the generic pattern is the fallback.
    patterns = []
    spath = os.path.join(root, "scenarios.json")
    if os.path.exists(spath):
        try:
            ids = [s["scenario_id"] for s in read_json(spath)["scenarios"]]
            patterns += [f"{sid}-a*-*-r*" for sid in ids]
        except (KeyError, TypeError, ValueError):
            pass
    patterns += ["*-a*-*-r*", "a*-*-r*"]

    dirs = []
    for pat in patterns[:-2] or [None]:
        if pat:
            dirs += sorted(glob.glob(os.path.join(root, pat)))
    if not dirs:
        for pat in patterns[-2:]:
            dirs = sorted(glob.glob(os.path.join(root, pat)))
            if dirs:
                break

    # A checker that sees nothing where branch directories plainly exist must
    # say so, not return an empty set that reads as a failed experiment.
    if not dirs:
        anylike = [d for d in sorted(glob.glob(os.path.join(root, "*-*-*")))
                   if os.path.isdir(d)]
        if anylike:
            raise SystemExit(
                f"REFUSED: {len(anylike)} branch-like directories are present in "
                f"{root} and none matched the naming this checker understands, "
                f"for example {os.path.basename(anylike[0])}. The matrix is not "
                f"being judged incomplete; the checker cannot read it.")
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
        rec = {"branch_name": name, "scenario_id": scenario, "anchor_name": anchor,
               "action": action, "repeat": repeat, "dir": directory,
               "refused": os.path.exists(os.path.join(directory, "REFUSED.txt"))}
        for kind in ("anchor", "outcome", "branch", "scenario"):
            path = os.path.join(directory, kind + ".json")
            if os.path.exists(path):
                rec[kind] = read_json(path)
        records.append(rec)
    return records


def prefix_verdict(by_cell):
    """Which cells reconstructed more than one prefix state.

    Extracted so the verdict can be tested. It used to be inline, computed into
    a `bad_prefix` flag that nothing ever read: the report printed PASS and
    returned 0 whatever it found, so a cell holding three different prefix
    states was reported as "complete and exact". The flag is the point of the
    check, so it is now both the printed finding and the exit status.

    Returns (lines_to_print, split_cells) where each split cell is
    (label, branches, distinct_states, group_sizes_descending).
    """
    lines, split_cells = [], []
    for key in sorted(by_cell):
        hashes = by_cell[key]
        distinct = len(set(hashes))
        label = "-".join(key) if key[0] != "s00" else key[1]
        marker = "" if distinct == 1 else "   <-- NOT ONE STATE"
        lines.append(f"  {label}: n={len(hashes)} distinct={distinct}{marker}")
        if distinct != 1:
            counts = collections.Counter(hashes)
            split_cells.append((label, len(hashes), distinct,
                                sorted(counts.values(), reverse=True)))
    return lines, split_cells


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
    # The anchors come from the recorded spec, which may be a list rather than a
    # range: the design needs anchors reaching past the fault onsets.
    spec = str(meta.get("anchor_spec", ""))
    if "," in spec:
        anchor_nums = [int(x) for x in spec.split(",") if x.strip()]
    else:
        anchor_nums = list(range(1, int(meta["anchors"]) + 1))
    expected = {f"{pre}a{a:02d}-{action}-r{repeat:02d}"
                for pre in prefixes
                for a in anchor_nums
                for action in actions
                for repeat in range(1, int(meta["repeats"]) + 1)}
    return meta, expected, actions


# The admission limit the THROTTLE action asks for. Named once: it appeared as a
# bare 50 in the only check that reads it, which is how that check came to be
# compared against the action alone rather than against what actually binds.
THROTTLE_ADMIT = 50


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
        expected = THROTTLE_ADMIT
        # D5 degrades the gateway's own admission capacity, and the node applies
        # whichever of the fault and the action is TIGHTER -- deliberately, since
        # a fault the operator suffers and a control the operator chose are
        # different situations and merging them would make them indistinguishable.
        # This check read the action's value alone and failed all 12 THROTTLE
        # branches of every D5 scenario for behaving exactly as designed: 40
        # against an expected 50 where the fault admits 40, 27 where it admits 27.
        scen = record.get("scenario") or {}
        fault_cap = int(scen.get("degraded_admit", -1))
        onset = int(scen.get("fault_onset", -1))
        read_epoch = (record.get("outcome") or {}).get("epoch")
        if fault_cap >= 0 and onset >= 0 and read_epoch is not None \
                and int(read_epoch) >= onset:
            expected = min(expected, fault_cap)
        if limit != expected:
            extra = ""
            if expected != THROTTLE_ADMIT:
                extra = (f" (the action asks for {THROTTLE_ADMIT}; the gateway fault"
                         f" admits {fault_cap} from epoch {onset}, and the tighter"
                         f" of the two binds)")
            return (f"outcome admission limit is {limit!r}, expected "
                    f"{expected}{extra}")
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

    # An ablation that did not ablate is the worst outcome available here,
    # because it looks exactly like a result. MODE=reset removes the per-branch
    # teardown; if every branch tore down anyway, the run is a full-protocol run
    # wearing an ablation's name. The first reset run was exactly that.
    meta = read_json(os.path.join(args.root, "matrix.json"))
    if meta.get("mode") == "reset":
        tore = 0
        total = 0
        for rec in records:
            su = os.path.join(rec["dir"], "startup.json")
            if os.path.exists(su):
                total += 1
                tore += int(read_json(su).get("tore_down_first", 1))
        if total and tore == total:
            print("", file=sys.stderr)
            print(f"VOID ABLATION: mode=reset, yet all {total} branches tore the "
                  f"topology down first.", file=sys.stderr)
            print("  Nothing was ablated. This matrix is a full-protocol run "
                  "under an ablation's name", file=sys.stderr)
            print("  and must not be read as evidence about the fresh topology.",
                  file=sys.stderr)
            return 1

    # Prefix identity is a claim about ONE cell: the repeats of an action at an
    # anchor within a scenario must reconstruct the same state. Grouped by anchor
    # alone it also demanded that different scenarios agree, which they must not
    # -- a different fault produces a different prefix by design. On the
    # three-scenario pilot that showed up as "distinct=3" and failed a correct
    # run. The grouping is per (scenario, anchor).
    by_cell = collections.defaultdict(list)
    for rec in records:
        by_cell[(rec["scenario_id"], rec["anchor_name"])].append(rec["anchor"]["hash"])
    print("PREFIX REPRODUCIBILITY (per scenario and anchor)")
    lines, split_cells = prefix_verdict(by_cell)
    for line in lines:
        print(line)
    bad_prefix = bool(split_cells)
    # Whether the fault reached the system cannot be answered from the prefix
    # hash. The node reports its degradation configuration in the structural
    # state, so the hash differs between scenarios whose CONFIGURATION differs
    # whether or not that configuration had any effect -- and it collides between
    # scenarios that share a design point and differ only by seed. An earlier
    # version of this check compared hashes across scenarios and failed a
    # complete, correct 2880-branch matrix for the second reason while being
    # blind to the first.
    #
    # The question is answered where it belongs, on observed throughput, by
    # analysis/audit_accounting.py: a degraded edge cannot have served more work
    # than its declared post-onset capacity allows.
    scenarios = sorted({k[0] for k in by_cell})
    # This sentence used to be printed unconditionally and read as a finding. It
    # is now printed only when it is true.
    if len(scenarios) > 1 and not bad_prefix:
        print(f"  {len(scenarios)} scenarios; prefix identity holds within every")
        print(f"  cell. Whether the declared fault took effect is checked on")
        print(f"  throughput by audit_accounting.py, not on this hash.")

    # A split cell is a real defect and the matrix must not be scored as if it
    # were not. It is not, however, a void matrix: PREFIX_EXCLUSION.md defines
    # what a split cell licenses, and when that decision has been frozen into
    # the matrix the gate is satisfied by it rather than by pretending the split
    # is absent. `bdg2-f-s42` completed 1296 branches with zero refusals and
    # five cells at group sizes [17, 1]; refusing the whole run would have
    # discarded 1291 good replays.
    if bad_prefix:
        import prefix_exclusion
        frozen = prefix_exclusion.load(args.root)
        if frozen is not None:
            covered = {c["cell"] for c in frozen["split_cells"]}
            found = {label for label, _, _, _ in split_cells}
            if covered == found:
                print("")
                print(f"PREFIX SPLITS COVERED BY POLICY "
                      f"{frozen['policy']}: {len(found)} cells, "
                      f"{len(frozen['excluded_branches'])} branches excluded by "
                      f"anchor state alone.")
                for rec in frozen["split_cells"]:
                    print(f"  {rec['cell']}: sizes {rec['group_sizes']} -> "
                          f"{rec['resolution']}")
                print("  The objective is computed without them; the cell-level "
                      "and A-prime readings")
                print("  are reported beside the primary one, per "
                      "PREFIX_EXCLUSION.md.")
                bad_prefix = False
            else:
                print("", file=sys.stderr)
                print(f"REFUSED: the frozen exclusion set covers {sorted(covered)} "
                      f"and the matrix splits in {sorted(found)}. A policy that "
                      f"does not match what is on disk is not a policy.",
                      file=sys.stderr)
                return 1

    if bad_prefix:
        print("", file=sys.stderr)
        print(f"PREFIX IDENTITY FAILURE: {len(split_cells)} of {len(by_cell)} "
              f"cells reconstructed more than one state.", file=sys.stderr)
        print("  Branches in such a cell did not start from the same prefix, so "
              "the actions compared", file=sys.stderr)
        print("  there were not applied to the same state and the comparison is "
              "not licensed.", file=sys.stderr)
        print("  If this is the known D5 late-anchor split, freeze the "
              "exclusion with", file=sys.stderr)
        print("  analysis/prefix_exclusion.py --write and read "
              "PREFIX_EXCLUSION.md first.", file=sys.stderr)
        for label, n, distinct, sizes in split_cells[:30]:
            print(f"    {label}: {n} branches, {distinct} states, "
                  f"group sizes {sizes}", file=sys.stderr)
        if len(split_cells) > 30:
            print(f"    ... and {len(split_cells) - 30} more", file=sys.stderr)
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
        cells[(rec["scenario_id"], rec["anchor_name"], rec["action"])].append(
            j_m2_diag(rec["outcome"]))
    within, medians = [], {}
    for cell, values in sorted(cells.items()):
        within.extend(pairwise_abs(values))
        medians[cell] = quantile(values, 0.5)
    if not within:
        print("FAIL: at least two repeats per cell are required", file=sys.stderr)
        return 1
    eta = quantile(within, 0.95)

    # Contrasts are formed inside a scenario. Across scenarios they would
    # compare two different systems.
    cell_keys = sorted({(sc, a) for sc, a, _ in medians})
    contrasts = []
    for sc, anchor in cell_keys:
        for i in range(len(actions)):
            for j in range(i + 1, len(actions)):
                left, right = (sc, anchor, actions[i]), (sc, anchor, actions[j])
                if left in medians and right in medians:
                    contrasts.append(abs(medians[left] - medians[right]))
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
        effects = [medians[(sc, a, action)] - medians[(sc, a, "NO_OP")]
                   for sc, a in cell_keys
                   if (sc, a, "NO_OP") in medians and (sc, a, action) in medians]
        if effects:
            print(f"  {action} - NO_OP median effect = {quantile(effects, 0.5):+.6g}")
    print("\nNOTE: J_m2_diag = processed - admission_backlog is a branch-mechanics")
    print("diagnostic. It must not be reported as the paper's lower-is-better J_obs.")
    if args.enforce_diagnostic_snr and (math.isnan(snr) or snr < SNR_GATE):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
