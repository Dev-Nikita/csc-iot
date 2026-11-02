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
import random
import sys

ABLATION_REPEATS = 3
N_SPLIT = 5  # the unmatched half-split of F's ten repeats, kept for the record
BOOT_DRAWS = 2000
BOOT_SEED = 20261102


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
    """The hash of the scenario set this matrix ran, from the set itself.

    The runner copies the declared set into the matrix as scenarios.json and
    records its `scenarios_hash` in the manifest. The copy is preferred because
    the manifest records what the runner was told and the copy records what it
    used; they agree, and if they ever do not, the comparison should refuse.
    """
    p = os.path.join(m["dir"], "scenarios.json")
    declared = (m["meta"].get("scenarios_hash")
                or m["meta"].get("scenario_set_hash"))
    if os.path.exists(p):
        doc = read_json(p)
        if isinstance(doc, dict):
            used = doc.get("scenarios_hash") or doc.get("hash")
            if used and declared and used != declared:
                refuse(f"{m['name']}: the manifest records scenarios_hash "
                       f"{declared} and its own copy of the set hashes to "
                       f"{used}. One of the two is not what ran.")
            if used:
                return used
    return declared


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


def band_pairs(rows):
    """The within-cell pairwise |dJ_obs|, grouped by contrast cell.

    Grouped, because the bootstrap resamples cells: repeats inside one cell are
    replays of one prefix and are not independent of each other, so resampling
    the pairs themselves would understate the band's own spread.
    """
    by_action = collections.defaultdict(list)
    for r in rows:
        by_action[(r["scenario"], r["anchor"], r["action"])].append(r["J_obs"])
    per_cell = collections.defaultdict(list)
    for (sc, an, _), v in by_action.items():
        per_cell[(sc, an)].extend(abs(a - b)
                                  for a, b in itertools.combinations(v, 2))
    return {k: v for k, v in per_cell.items() if v}


def pooled_band(rows):
    """Q0.95 of within-cell pairwise |dJ_obs|, inside this set and no other."""
    per_cell = band_pairs(rows)
    diffs = [d for v in per_cell.values() for d in v]
    if not diffs:
        refuse("no within-cell repeat pairs: the band cannot be measured")
    return quantile(diffs, 0.95), len(diffs)


def band_interval(rows, draws=BOOT_DRAWS, seed=BOOT_SEED):
    """A 95% percentile interval for the band, resampling contrast cells.

    The comparison between modes turns on the ratio of two bands, each a Q0.95
    of a few hundred differences from one run. Without an interval the rules
    would read any ratio away from 1 as a degraded measurement, which is not
    something a point estimate of a high quantile can support.
    """
    per_cell = band_pairs(rows)
    keys = sorted(per_cell)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    draws_out = []
    for _ in range(draws):
        pool = []
        for _ in keys:
            pool.extend(per_cell[keys[rng.randrange(len(keys))]])
        draws_out.append(quantile(pool, 0.95))
    # The percentiles need the draws sorted; the ratio needs them in DRAW ORDER.
    # Returning only the sorted list is what made the first ratio interval
    # wrong: see ratio_interval.
    ordered = sorted(draws_out)
    lo = ordered[int(0.025 * (draws - 1) + 0.5)]
    hi = ordered[int(0.975 * (draws - 1) + 0.5)]
    return lo, hi, draws_out


def ratio_interval(abl_rows, full_rows, draws=BOOT_DRAWS, seed=BOOT_SEED):
    """Interval for band(ablated)/band(F3), resampling cells in both arms.

    The arms are resampled independently -- the modes are separate runs of the
    system, not two measurements of one set of units -- and the b-th draw of one
    is divided by the b-th draw of the other.

    The first version of this function divided the two SORTED draw vectors,
    because band_interval returned its draws sorted for the percentile step. That
    pairs the k-th smallest of one arm with the k-th smallest of the other, a
    perfectly comonotonic coupling, which cancels most of the variance the
    interval exists to carry. It reported [1.043, 1.343] for Q and announced that
    the interval excluded 1, while the two band intervals themselves overlapped
    over almost their whole length -- a manufactured significance, produced by
    the one line of plumbing between the estimator and the thing being claimed.
    """
    a = band_interval(abl_rows, draws, seed)
    f = band_interval(full_rows, draws, seed + 1)
    if a is None or f is None:
        return None
    rs = sorted(x / y for x, y in zip(a[2], f[2]) if y > 0)
    if not rs:
        return None
    return (rs[int(0.025 * (len(rs) - 1) + 0.5)],
            rs[int(0.975 * (len(rs) - 1) + 0.5)])


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
    cif = band_interval(f_rows)
    cia = band_interval(a_rows)
    ratio_ci = ratio_interval(a_rows, f_rows)
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
            "ci_full": cif[:2] if cif else None,
            "ci_abl": cia[:2] if cia else None, "ratio_ci": ratio_ci,
            "cells_full": len(cf), "cells_abl": len(ca), "shared": len(shared),
            "resolved_full": sum(c["resolved"] for c in cf.values()),
            "resolved_abl": sum(c["resolved"] for c in ca.values()),
            "label": label, "disagreements": disagreements,
            "shifts": shifts, "by_fault": by_fault,
            "only_full": sorted(set(cf) - set(ca)),
            "only_abl": sorted(set(ca) - set(cf))}


def null_mode(full, left, right, band_rows, label):
    """Mode N: two disjoint sets of F's repeats, treated as two actions.

    There is no effect between them by construction, so the fraction called
    resolvable is the band procedure's false-positive rate -- but only if the
    two halves hold the SAME number of repeats as the contrasts the band is used
    on. Amendment 1: the five-against-five split compares a mean of five against
    a band built from single-repeat differences, which reports near zero
    whatever the data do. The matched split is three against three, read against
    the F3 band, which is the band the ablation comparisons use.
    """
    lo, hi = subset(full["rows"], left), subset(full["rows"], right)
    if not lo or not hi:
        return None
    band, npairs = pooled_band(band_rows)
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
    return {"label": label, "band": band, "pairs": npairs, "contrasts": total,
            "n_per_side": (len(left), len(right)),
            "resolved": resolved, "gaps": gaps,
            "rate": resolved / total if total else float("nan")}


def report_compare(r, title):
    print(f"\n{'='*78}\n{title}")
    ratio = r["band_abl"] / r["band_full"] if r["band_full"] else float("nan")
    print(f"  pooled band  F3 {r['band_full']:.6f} over {r['pairs_full']} pairs"
          + (f"  95% [{r['ci_full'][0]:.6f}, {r['ci_full'][1]:.6f}]"
             if r["ci_full"] else ""))
    print(f"               {r['mode']} {r['band_abl']:.6f} over "
          f"{r['pairs_abl']} pairs"
          + (f"  95% [{r['ci_abl'][0]:.6f}, {r['ci_abl'][1]:.6f}]"
             if r["ci_abl"] else ""))
    if r["ratio_ci"]:
        lo, hi = r["ratio_ci"]
        verdict = ("INCONCLUSIVE: the interval contains 1"
                   if lo <= 1.0 <= hi else
                   "the interval excludes 1")
        print(f"  band ratio   {ratio:.3f}  95% [{lo:.3f}, {hi:.3f}]  -- {verdict}")
    else:
        print(f"  band ratio   {ratio:.3f}  (no interval: too few cells)")
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

    # Mode N twice: the matched reading, which is the false-positive rate, and
    # the five-against-five reading specified first, which is not, kept visible
    # because amendment 1 replaced it after it had produced a flattering number.
    f3 = subset(full["rows"], range(1, ABLATION_REPEATS + 1))
    readings = [
        null_mode(full, range(1, 4), range(4, 7), f3,
                  "N3 (matched: 3 against 3, F3 band)"),
        null_mode(full, range(1, N_SPLIT + 1),
                  range(N_SPLIT + 1, 2 * N_SPLIT + 1), full["rows"],
                  "N5 (unmatched: 5 against 5, F10 band)"),
    ]
    print("\nmode N, the false-positive calibration of the band")
    print("  There is no effect in a null contrast by construction, so the "
          "fraction called\n  resolvable is the procedure's own "
          "false-positive rate -- and only the reading\n  whose halves hold as "
          "many repeats as the real contrasts measures that.")
    for nm in readings:
        if nm is None:
            print("    unavailable: F does not have the repeats this reading needs")
            continue
        g = sorted(nm["gaps"])
        print(f"\n    {nm['label']}")
        print(f"      {nm['resolved']} of {nm['contrasts']} null contrasts "
              f"exceed the band {nm['band']:.6f} = {nm['rate']:.1%}"
              f"   (expected about 5%)")
        print("      null gap quantiles: " + "  ".join(
            f"Q{p:.2f} {quantile(g,p):.6f}" for p in (0.5, 0.9, 0.95, 1.0)))
    print("\n    N5 is reported for the record only. A difference of two "
          "five-repeat means\n    against a band built from single-repeat "
          "differences reports near zero\n    whatever the data do; see "
          "MODE_COMPARISON.md amendment 1.")

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
