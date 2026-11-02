#!/usr/bin/env python3
"""Compare the campaign's ablation modes, under the rules frozen in
MODE_COMPARISON.md before any objective outcome of one mode was placed beside
another.

    python3 -I analysis/mode_comparison.py <raw-root> --full <F-matrix> \
        --ablated <Q-matrix> [--ablated <R-matrix> ...]

Each matrix is a directory under <raw-root> holding matrix.json and jobs.csv.
Standard library only, so the comparison runs on the published package as well
as on the analysis host.

The rules this file implements, restated so that the code and the protocol
cannot drift apart:

* the unit is a contrast cell (scenario, anchor), the statistic is the argmin of
  mean J_obs with ties broken by action name, and a cell is resolved when the
  gap to the runner-up exceeds that MODE'S OWN pooled band;
* F enters every mode comparison at three repeats, selected by index r01..r03,
  because F ran ten and the ablations ran three and a ten-against-three
  comparison measures the repeat count;
* cells unresolved in either mode are their own category and are never folded
  into agreement or into disagreement.
"""
import argparse
import collections
import csv
import glob
import itertools
import json
import os
import sys

ABLATION_REPEATS = 3
N_SPLIT = 5  # the null mode's half-split of F's ten repeats


def quantile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    h = (len(xs) - 1) * p
    lo = int(h)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (h - lo) * (xs[hi] - xs[lo])


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def refuse(msg):
    print("REFUSED: " + msg, file=sys.stderr)
    raise SystemExit(2)


def load_matrix(root, name):
    """The manifest, the rows, and every refusal that must happen before use."""
    d = os.path.join(root, name)
    if not os.path.isdir(d):
        refuse(f"{d} is not a directory")
    if os.path.exists(os.path.join(d, "VOID.txt")):
        refuse(f"{name} carries VOID.txt beside its manifest. A run marked void "
               f"was kept as evidence of a mistake, not as a measurement:\n  "
               + open(os.path.join(d, "VOID.txt"), encoding="utf-8")
               .read().strip().splitlines()[0])
    meta_path = os.path.join(d, "matrix.json")
    if not os.path.exists(meta_path):
        refuse(f"{name} has no matrix.json; the mode it ran in is unknown")
    meta = read_json(meta_path)

    # The void run's signature. m2prime_report.py refuses it too; an analysis
    # that is reached by a different path must refuse it on its own, because a
    # full-protocol run wearing an ablation's name is the one error here that
    # looks exactly like a result.
    if meta.get("mode") == "reset":
        tore = total = 0
        for su in glob.glob(os.path.join(d, "*-a*", "startup.json")):
            total += 1
            tore += int(read_json(su).get("tore_down_first", 1))
        if total and tore == total:
            refuse(f"{name} declares mode=reset, yet all {total} branches tore "
                   f"the topology down first. Nothing was ablated.")

    jobs_path = os.path.join(d, "jobs.csv")
    if not os.path.exists(jobs_path):
        refuse(f"{name} has no jobs.csv. Run scripts/analyze_matrix.sh first; "
               f"this analysis does not compute J_obs, it compares it.")
    with open(jobs_path, newline="", encoding="utf-8") as fh:
        rows = [{"scenario": r["scenario"], "anchor": r["anchor"],
                 "action": r["action"], "repeat": r["repeat"],
                 "fault_type": r["fault_type"], "regime": r["regime"],
                 "J_obs": float(r["J_obs"])}
                for r in csv.DictReader(fh)]
    if not rows:
        refuse(f"{name}/jobs.csv has no rows")
    return {"name": name, "dir": d, "meta": meta, "rows": rows,
            "mode": meta.get("mode", "unrecorded")}


def scenario_hash(m):
    p = os.path.join(m["dir"], "scenarios.json")
    if os.path.exists(p):
        doc = read_json(p)
        if isinstance(doc, dict) and doc.get("hash"):
            return doc["hash"]
    return m["meta"].get("scenario_set_hash") or m["meta"].get("scenarios_hash")


def require_same_substrate(ms):
    """One thing is ablated at a time, or nothing is."""
    for key, label in (("runtime_stack_id", "runtime stack"),
                       ("master_seed", "master seed"),
                       ("anchor_spec", "anchor set"),
                       ("actions", "action set")):
        seen = {}
        for m in ms:
            seen.setdefault(json.dumps(m["meta"].get(key), sort_keys=True),
                            []).append(m["name"])
        if len(seen) > 1:
            lines = "; ".join(f"{v!s} -> {', '.join(n)}" for v, n in seen.items())
            refuse(f"the matrices do not share a {label}: {lines}. An ablation "
                   f"holds everything but the one step it removes.")
    hs = {scenario_hash(m) for m in ms}
    if len(hs) > 1:
        refuse(f"the matrices do not share a scenario set: {sorted(map(str, hs))}")


def subset(rows, repeats):
    """Rows whose repeat index is in `repeats`; selection by index, never value."""
    keep = {f"r{i:02d}" for i in repeats}
    return [r for r in rows if r["repeat"] in keep]


def pooled_band(rows):
    """Q0.95 of within-cell pairwise |dJ_obs|, inside this set and no other."""
    by_cell = collections.defaultdict(list)
    for r in rows:
        by_cell[(r["scenario"], r["anchor"], r["action"])].append(r["J_obs"])
    diffs = [abs(a - b) for v in by_cell.values()
             for a, b in itertools.combinations(v, 2)]
    if not diffs:
        refuse("no within-cell repeat pairs: the band cannot be measured")
    return quantile(diffs, 0.95), len(diffs)


def cells(rows, band):
    """Per contrast cell: the winner, the gap, and whether the band resolves it."""
    means = collections.defaultdict(dict)
    acc = collections.defaultdict(list)
    meta = {}
    for r in rows:
        acc[(r["scenario"], r["anchor"], r["action"])].append(r["J_obs"])
        meta.setdefault((r["scenario"], r["anchor"]),
                        {"fault_type": r["fault_type"], "regime": r["regime"]})
    for (sc, an, ac), v in acc.items():
        means[(sc, an)][ac] = sum(v) / len(v)
    out = {}
    for key, per_action in means.items():
        if len(per_action) < 2:
            continue
        order = sorted(per_action.items(), key=lambda kv: (kv[1], kv[0]))
        gap = order[1][1] - order[0][1]
        out[key] = {"winner": order[0][0], "gap": gap, "resolved": gap > band,
                    "means": per_action, "tied": gap == 0.0, **meta[key]}
    return out


def cell_keys(rows):
    """Every contrast cell a set of rows covers, regardless of any band."""
    return {(r["scenario"], r["anchor"]) for r in rows}


def prefix_split_cells(root_dir):
    """Cells whose repeats reconstructed more than one anchor state."""
    by_cell = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(root_dir, "*-a*", "anchor.json"))):
        name = os.path.basename(os.path.dirname(p))
        parts = name.split("-")
        if len(parts) != 4:
            continue
        try:
            by_cell[(parts[0], parts[1])].add(read_json(p)["hash"])
        except (KeyError, ValueError, OSError):
            continue
    return {k for k, v in by_cell.items() if len(v) != 1}


def compare(full, abl, clean_only=None):
    """One ablated mode against F at three repeats."""
    f_rows = subset(full["rows"], range(1, ABLATION_REPEATS + 1))
    a_rows = abl["rows"]
    if clean_only is not None:
        f_rows = [r for r in f_rows if (r["scenario"], r["anchor"]) in clean_only]
        a_rows = [r for r in a_rows if (r["scenario"], r["anchor"]) in clean_only]
    bf, nf = pooled_band(f_rows)
    ba, na = pooled_band(a_rows)
    cf, ca = cells(f_rows, bf), cells(a_rows, ba)
    shared = sorted(set(cf) & set(ca))

    label = collections.Counter()
    disagreements, shifts = [], []
    by_fault = collections.defaultdict(collections.Counter)
    for key in shared:
        x, y = cf[key], ca[key]
        for ac in set(x["means"]) & set(y["means"]):
            shifts.append(y["means"][ac] - x["means"][ac])
        if not (x["resolved"] and y["resolved"]):
            lab = "unresolved in one or both"
        elif x["winner"] == y["winner"]:
            lab = "agreement"
        else:
            lab = "disagreement"
            disagreements.append((key, x, y))
        label[lab] += 1
        by_fault[x["fault_type"]][lab] += 1

    return {"ablated": abl["name"], "mode": abl["mode"],
            "band_full": bf, "band_abl": ba, "pairs_full": nf, "pairs_abl": na,
            "cells_full": len(cf), "cells_abl": len(ca), "shared": len(shared),
            "resolved_full": sum(c["resolved"] for c in cf.values()),
            "resolved_abl": sum(c["resolved"] for c in ca.values()),
            "label": label, "disagreements": disagreements,
            "shifts": shifts, "by_fault": by_fault,
            "only_full": sorted(set(cf) - set(ca)),
            "only_abl": sorted(set(ca) - set(cf))}


def null_mode(full):
    """Mode N: F's ten repeats split five and five, treated as two actions."""
    lo = subset(full["rows"], range(1, N_SPLIT + 1))
    hi = subset(full["rows"], range(N_SPLIT + 1, 2 * N_SPLIT + 1))
    if not hi:
        return None
    band, npairs = pooled_band(full["rows"])
    acc = collections.defaultdict(lambda: ([], []))
    for r in lo:
        acc[(r["scenario"], r["anchor"], r["action"])][0].append(r["J_obs"])
    for r in hi:
        acc[(r["scenario"], r["anchor"], r["action"])][1].append(r["J_obs"])
    resolved = total = 0
    gaps = []
    for a, b in acc.values():
        if not a or not b:
            continue
        gap = abs(sum(a) / len(a) - sum(b) / len(b))
        gaps.append(gap)
        total += 1
        resolved += gap > band
    return {"band": band, "pairs": npairs, "contrasts": total,
            "resolved": resolved, "gaps": gaps,
            "rate": resolved / total if total else float("nan")}


def report_compare(r, title):
    print(f"\n{'='*78}\n{title}")
    print(f"  pooled band  F3 {r['band_full']:.6f} over {r['pairs_full']} pairs"
          f"   {r['mode']} {r['band_abl']:.6f} over {r['pairs_abl']} pairs"
          f"   ratio {r['band_abl']/r['band_full'] if r['band_full'] else float('nan'):.3f}")
    print(f"  contrast cells  F3 {r['cells_full']}  {r['mode']} {r['cells_abl']}"
          f"  shared {r['shared']}")
    if r["only_full"] or r["only_abl"]:
        print(f"  cells in only one mode: F3-only {len(r['only_full'])}, "
              f"{r['mode']}-only {len(r['only_abl'])} (excluded from the labels)")
    rf = r["resolved_full"] / r["cells_full"] if r["cells_full"] else float("nan")
    ra = r["resolved_abl"] / r["cells_abl"] if r["cells_abl"] else float("nan")
    print(f"  resolved at own band  F3 {r['resolved_full']}/{r['cells_full']}"
          f" = {rf:.1%}   {r['mode']} {r['resolved_abl']}/{r['cells_abl']}"
          f" = {ra:.1%}")
    print("\n  conclusion labels over shared cells")
    for lab in ("agreement", "disagreement", "unresolved in one or both"):
        n = r["label"].get(lab, 0)
        share = n / r["shared"] if r["shared"] else float("nan")
        print(f"    {lab:28s} {n:4d}  {share:6.1%}")
    s = sorted(r["shifts"])
    if s:
        print(f"\n  shift in mean J_obs ({r['mode']} - F3), {len(s)} action cells")
        for p in (0.10, 0.50, 0.90):
            print(f"    Q{p:.2f} {quantile(s,p):+.6f}")
    if r["disagreements"]:
        print(f"\n  the {len(r['disagreements'])} cells resolved in both modes "
              f"that named different winners")
        for (sc, an), x, y in r["disagreements"]:
            print(f"    {sc} {an} {x['fault_type']:>3s} {x['regime']:<10s}"
                  f"  F3 {x['winner']:9s} gap {x['gap']:.6f}"
                  f"   {r['mode']} {y['winner']:9s} gap {y['gap']:.6f}")
    else:
        print("\n  no cell resolved in both modes named a different winner")
    print("\n  by fault family")
    print(f"    {'':5s}" + "".join(f"{k:>14s}" for k in
                                   ("agreement", "disagreement", "unresolved")))
    for k in sorted(r["by_fault"]):
        c = r["by_fault"][k]
        print(f"    {k:5s}{c.get('agreement',0):14d}"
              f"{c.get('disagreement',0):14d}"
              f"{c.get('unresolved in one or both',0):14d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="data/raw/<stack>")
    ap.add_argument("--full", required=True, help="the mode-F matrix")
    ap.add_argument("--ablated", action="append", default=[],
                    help="an ablated matrix; repeatable")
    args = ap.parse_args()

    full = load_matrix(args.root, args.full)
    abls = [load_matrix(args.root, n) for n in args.ablated]
    require_same_substrate([full] + abls)
    if full["mode"] not in ("full", "unrecorded"):
        refuse(f"--full names {args.full}, whose manifest says mode="
               f"{full['mode']!r}. The reference arm must be the full protocol.")
    for m in abls:
        if m["mode"] in ("full", "unrecorded"):
            refuse(f"--ablated names {m['name']}, whose manifest says mode="
                   f"{m['mode']!r}. That is not an ablation.")

    print("MODE COMPARISON")
    print("rules frozen in MODE_COMPARISON.md before any of these numbers existed")
    print(f"stack      {full['meta'].get('runtime_stack_id')}")
    print(f"reference  {full['name']}  mode={full['mode']}  "
          f"{len(full['rows'])} branches, repeats={full['meta'].get('repeats')}")
    for m in abls:
        print(f"ablated    {m['name']}  mode={m['mode']}  {len(m['rows'])} "
              f"branches, repeats={m['meta'].get('repeats')}")

    # F at ten repeats, reported and not compared: it is the better estimate of
    # F itself and the wrong thing to put against a three-repeat ablation.
    b10, n10 = pooled_band(full["rows"])
    c10 = cells(full["rows"], b10)
    res10 = sum(c["resolved"] for c in c10.values())
    print(f"\nF10 (reported, never compared): band {b10:.6f} over {n10} pairs, "
          f"{res10}/{len(c10)} cells resolved = "
          f"{res10/len(c10) if c10 else float('nan'):.1%}")

    nm = null_mode(full)
    if nm is None:
        print("\nmode N unavailable: F does not have "
              f"{2*N_SPLIT} repeats per cell")
    else:
        print(f"\nmode N, the false-positive calibration: F's repeats split "
              f"r01-r05 against r06-r10,\n  {nm['resolved']} of "
              f"{nm['contrasts']} null contrasts exceed the F10 band "
              f"{nm['band']:.6f} = {nm['rate']:.1%}")
        print("  There is no effect in a null contrast by construction, so this "
              "is the\n  procedure's own false-positive rate. The Q0.95 band "
              "expects about 5%.")
        g = sorted(nm["gaps"])
        print("  null gap quantiles: " + "  ".join(
            f"Q{p:.2f} {quantile(g,p):.6f}" for p in (0.5, 0.9, 0.95, 1.0)))

    for m in abls:
        report_compare(compare(full, m), f"{m['name']} (mode {m['mode']}) "
                                         f"against {full['name']} at three repeats")

    # Mode A': the same headline over prefix-clean cells only.
    split_f = prefix_split_cells(full["dir"])
    print(f"\n{'='*78}\nmode A': prefix identity not required")
    print(f"  F split cells: {len(split_f)}"
          + (f"  {sorted('-'.join(k) for k in split_f)}" if split_f else ""))
    for m in abls:
        split = split_f | prefix_split_cells(m["dir"])
        clean = cell_keys(m["rows"]) - split
        if not split:
            print(f"  {m['name']}: no split cells in either arm; A' is identical "
                  f"to the main reading")
            continue
        report_compare(compare(full, m, clean_only=clean),
                       f"A' {m['name']}: {len(clean)} prefix-clean cells only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
