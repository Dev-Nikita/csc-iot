#!/usr/bin/env python3
"""Does executing the alternatives change the conclusion?

Implements VALUE_OF_PROTOCOL.md exactly. Standard library only, and it reads the
published data package rather than the analysis host, so the answer is one a
reader can reproduce from the archive.

    python3 -I value_of_protocol.py <zenodo-data-dir> <matrix> [<matrix> ...]
"""
import collections
import csv
import sys

NO_OP = "NO_OP"


def quantile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    h = (len(xs) - 1) * p
    lo = int(h)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (h - lo) * (xs[hi] - xs[lo])


def load(root, matrix):
    rows = list(csv.DictReader(open(f"{root}/{matrix}/structural.csv", newline="")))
    jobs = {r["branch"]: r for r in
            csv.DictReader(open(f"{root}/{matrix}/jobs.csv", newline=""))}
    out = []
    for r in rows:
        j = jobs.get(r["branch"])
        if j is None:
            continue
        out.append({
            "scenario": r["scenario"], "anchor": r["anchor"],
            "action": r["action"], "regime": r["regime"],
            "J_hat": float(r["J_hat"]), "J_obs": float(r["J_obs"]),
            "repeat": j["repeat"], "fault_type": j["fault_type"],
        })
    return out, len(rows), len(out)


def winner(scores):
    """argmin with the frozen tie rule; returns (action, best, second, tied)."""
    ordered = sorted(scores.items(), key=lambda kv: (kv[1], kv[0]))
    best_a, best_v = ordered[0]
    if len(ordered) == 1:
        return best_a, best_v, None, False
    second_v = ordered[1][1]
    return best_a, best_v, second_v, best_v == second_v


def analyse(root, matrix):
    rows, n_struct, n_joined = load(root, matrix)
    cells = collections.defaultdict(list)
    for r in rows:
        cells[(r["scenario"], r["anchor"], r["action"])].append(r)

    diffs = []
    for v in cells.values():
        vals = [x["J_obs"] for x in v]
        for i in range(len(vals)):
            for k in range(i + 1, len(vals)):
                diffs.append(abs(vals[i] - vals[k]))
    eta = quantile(diffs, 0.95)

    anchors = collections.defaultdict(dict)
    meta = {}
    for (sc, an, ac), v in cells.items():
        first = min(v, key=lambda x: x["repeat"])
        anchors[(sc, an)][ac] = {
            "J_hat": sum(x["J_hat"] for x in v) / len(v),
            "single": first["J_obs"],
            "mean": sum(x["J_obs"] for x in v) / len(v),
            "n": len(v),
        }
        meta.setdefault((sc, an), {"fault_type": v[0]["fault_type"],
                                   "regime": v[0]["regime"]})

    labels = {c: collections.Counter() for c in ("P vs S", "P vs R", "S vs R")}
    by_fault = collections.defaultdict(lambda: collections.Counter())
    by_regime = collections.defaultdict(lambda: collections.Counter())
    confusion = collections.Counter()
    gaps, tied_any, flips = [], 0, []

    for key, acts in sorted(anchors.items()):
        if len(acts) < 2:
            for c in labels:
                labels[c]["unavailable"] += 1
            continue
        P, _, _, tP = winner({a: d["J_hat"] for a, d in acts.items()})
        S, _, _, tS = winner({a: d["single"] for a, d in acts.items()})
        R, rbest, rsecond, tR = winner({a: d["mean"] for a, d in acts.items()})
        gap = rsecond - rbest
        gaps.append(gap)
        tied_any += int(tP or tS or tR)
        unresolved = gap <= eta

        for name, (x, y) in (("P vs S", (P, S)), ("P vs R", (P, R)),
                             ("S vs R", (S, R))):
            if name != "P vs S" and unresolved:
                lab = "unresolved"
            else:
                lab = "changed" if x != y else "unchanged"
            labels[name][lab] += 1
            if name == "P vs R":
                by_fault[meta[key]["fault_type"]][lab] += 1
                by_regime[meta[key]["regime"]][lab] += 1
                confusion[(P, "unresolved" if unresolved else R)] += 1

        if NO_OP in acts:
            for a, d in acts.items():
                if a == NO_OP:
                    continue
                pred = acts[NO_OP]["J_hat"] - d["J_hat"]
                obs = acts[NO_OP]["mean"] - d["mean"]
                if pred * obs < 0 and abs(obs) > eta:
                    flips.append((key[0], key[1], a, obs, pred))

    return dict(matrix=matrix, n_struct=n_struct, n_joined=n_joined, eta=eta,
                n_pairs=len(diffs), anchors=len(anchors), labels=labels,
                by_fault=by_fault, by_regime=by_regime, confusion=confusion,
                gaps=gaps, tied=tied_any, flips=flips)


def report(r):
    print(f"\n{'='*74}\n{r['matrix']}: {r['anchors']} anchors, "
          f"{r['n_joined']} of {r['n_struct']} branches joined to jobs.csv")
    print(f"band eta_J = Q0.95 over {r['n_pairs']} within-cell repeat pairs = {r['eta']:.4f}")
    print(f"anchors with an exact tie in some evaluation: {r['tied']}")
    print("\nconclusion labels")
    order = ("changed", "unchanged", "unresolved", "unavailable")
    print(f"  {'contrast':10s} " + "".join(f"{k:>12s}" for k in order))
    for c, counts in r["labels"].items():
        print(f"  {c:10s} " + "".join(f"{counts.get(k,0):12d}" for k in order))

    g = sorted(r["gaps"])
    if g:
        print("\nR gap between best and runner-up (mean J_obs)")
        for p in (0.10, 0.25, 0.50, 0.75, 0.90):
            print(f"  Q{p:.2f} = {quantile(g,p):.4f}   "
                  f"({quantile(g,p)/r['eta']:.2f} x eta)")
        below = sum(1 for x in g if x <= r["eta"])
        print(f"  at or below the band: {below} of {len(g)} ({below/len(g):.1%})")

    print("\nP winner -> R conclusion")
    pw = sorted({k[0] for k in r["confusion"]})
    rc = sorted({k[1] for k in r["confusion"]})
    print(f"  {'':16s}" + "".join(f"{c:>14s}" for c in rc))
    for p in pw:
        print(f"  {p:16s}" + "".join(f"{r['confusion'].get((p,c),0):14d}" for c in rc))

    for title, d in (("fault family", r["by_fault"]), ("regime", r["by_regime"])):
        print(f"\nP vs R by {title}")
        print(f"  {'':14s}" + "".join(f"{k:>12s}" for k in order[:3]))
        for k in sorted(d):
            print(f"  {k:14s}" + "".join(f"{d[k].get(c,0):12d}" for c in order[:3]))

    print(f"\nsign-flipped (anchor, action) pairs: {len(r['flips'])}")
    for sc, an, a, obs, pred in sorted(r["flips"], key=lambda t: -abs(t[3])):
        print(f"  {sc:>6s} anchor {an:>3s}  {a:9s} observed {obs:+.4f}  predicted {pred:+.4f}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    root, matrices = sys.argv[1], sys.argv[2:]
    for m in matrices:
        report(analyse(root, m))


if __name__ == "__main__":
    main()
