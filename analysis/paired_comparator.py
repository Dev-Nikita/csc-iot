#!/usr/bin/env python3
"""The second comparator: an exact permutation test inside each contrast cell,
with Holm over the cell's three action pairs, reported beside the band.

Implements STATISTICAL_COMPARATOR.md exactly. Standard library only.

    python3 -I analysis/paired_comparator.py <matrix>/jobs.csv [--alpha 0.05]
    python3 -I analysis/paired_comparator.py <matrix>/jobs.csv --by-point

The band and this test answer different questions and both are printed. A cell
where the band says unresolvable and the test says decided is a difference the
instrument reproduces but cannot resolve against its own noise; that is a real
state and the output names it rather than hiding it.
"""
import argparse
import collections
import csv
import itertools
import math
import random
import sys

PERM_SEED = 20261109
ENUMERATION_LIMIT = 20000


def quantile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    h = (len(xs) - 1) * p
    lo = int(h)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (h - lo) * (xs[hi] - xs[lo])


def mean(xs):
    return sum(xs) / len(xs)


def permutation_p(a, b, seed=PERM_SEED, limit=ENUMERATION_LIMIT):
    """Two-sided p for |mean(a) - mean(b)| under exchangeability of the label.

    Returns (p, n_reference, exact). The observed split is counted in both the
    numerator and the denominator, which is what makes the smallest attainable
    p equal to 1 / n_reference rather than 0 -- a p-value of exactly zero from a
    finite reference set would be a statement the set cannot support.
    """
    pool = list(a) + list(b)
    n, k = len(pool), len(a)
    if n < 2 or k == 0 or k == n:
        return 1.0, 0, True
    observed = abs(mean(a) - mean(b))
    total = math.comb(n, k)
    # A tolerance, because these are floats: a split that differs from the
    # observed statistic only in the last bits is the same statistic and must
    # count as "at least as extreme", not as evidence.
    tol = 1e-12 * max(1.0, observed)
    hits = 0
    if total <= limit:
        for idx in itertools.combinations(range(n), k):
            left = [pool[i] for i in idx]
            s = sum(left)
            d = abs(s / k - (sum(pool) - s) / (n - k))
            if d >= observed - tol:
                hits += 1
        return hits / total, total, True
    rng = random.Random(seed)
    draws = limit
    for _ in range(draws - 1):
        idx = rng.sample(range(n), k)
        s = sum(pool[i] for i in idx)
        d = abs(s / k - (sum(pool) - s) / (n - k))
        if d >= observed - tol:
            hits += 1
    return (hits + 1) / draws, draws, False


def holm(pairs, alpha):
    """Holm over one family. pairs: [(label, p)] -> {label: (p, adj, reject)}."""
    ordered = sorted(pairs, key=lambda kv: kv[1])
    m = len(ordered)
    out, running = {}, 0.0
    still_rejecting = True
    for i, (label, p) in enumerate(ordered):
        thresh = alpha / (m - i)
        if still_rejecting and p <= thresh:
            reject = True
        else:
            reject = False
            still_rejecting = False
        running = max(running, min(1.0, p * (m - i)))
        out[label] = (p, running, reject)
    return out


def load(path):
    cells = collections.defaultdict(lambda: collections.defaultdict(list))
    meta = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            key = (r["scenario"], r["anchor"])
            cells[key][r["action"]].append(float(r["J_obs"]))
            meta.setdefault(key, {"fault_type": r.get("fault_type", "?"),
                                  "regime": r.get("regime", "?")})
    return cells, meta


def pooled_band(cells):
    diffs = []
    for per_action in cells.values():
        for vals in per_action.values():
            diffs += [abs(x - y) for x, y in itertools.combinations(vals, 2)]
    return quantile(diffs, 0.95), len(diffs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_csv")
    ap.add_argument("--alpha", type=float, default=0.05,
                    help="family-wise level inside one cell (default 0.05)")
    ap.add_argument("--by-point", action="store_true",
                    help="also summarise by design point, the L2 unit")
    args = ap.parse_args()

    cells, meta = load(args.jobs_csv)
    if not cells:
        sys.exit(f"REFUSED: no rows in {args.jobs_csv}")
    band, npairs = pooled_band(cells)

    print("SECOND COMPARATOR: exact permutation test inside the cell, Holm over")
    print("the cell's action pairs. Rules frozen in STATISTICAL_COMPARATOR.md.")
    print(f"  cells {len(cells)}   family-wise alpha {args.alpha}   "
          f"pooled band {band:.6f} over {npairs} within-cell pairs")
    print("  The band and the test answer different questions and both are "
          "printed below.\n")

    rows, any_sampled = [], False
    decided = resolved = both = test_only = band_only = 0
    for key in sorted(cells):
        per_action = cells[key]
        actions = sorted(per_action)
        tests = []
        for a, b in itertools.combinations(actions, 2):
            p, nref, exact = permutation_p(per_action[a], per_action[b])
            any_sampled = any_sampled or not exact
            tests.append(((a, b), p, nref, exact,
                          mean(per_action[a]) - mean(per_action[b])))
        verdicts = holm([(lbl, p) for lbl, p, _, _, _ in tests], args.alpha)
        cell_decided = any(v[2] for v in verdicts.values())

        means = {a: mean(v) for a, v in per_action.items()}
        order = sorted(means.items(), key=lambda kv: (kv[1], kv[0]))
        gap = order[1][1] - order[0][1] if len(order) > 1 else 0.0
        cell_resolved = gap > band

        decided += cell_decided
        resolved += cell_resolved
        both += cell_decided and cell_resolved
        test_only += cell_decided and not cell_resolved
        band_only += cell_resolved and not cell_decided
        rows.append((key, cell_resolved, cell_decided, gap, tests, verdicts,
                     order[0][0]))

    print(f"{'cell':12s}{'band':>10s}{'test':>8s}{'gap':>11s}"
          f"{'gap/band':>10s}  winner     pairs (Delta, p, Holm)")
    for key, res, dec, gap, tests, verdicts, winner in rows:
        label = "-".join(key)
        detail = "  ".join(
            f"{a[0][:2]}/{b[0][:2]} {d:+.4f} p={p:.4f}"
            f"{'*' if verdicts[(a, b)][2] else ' '}"
            for (a, b), p, _, _, d in tests)
        print(f"{label:12s}{'res' if res else '-':>10s}{'dec' if dec else '-':>8s}"
              f"{gap:11.5f}{(gap / band if band else float('nan')):10.2f}  "
              f"{winner:10s} {detail}")

    n = len(rows)
    print(f"\n  resolved at the band      {resolved:4d} / {n}  "
          f"{resolved / n:6.1%}")
    print(f"  decided by the test       {decided:4d} / {n}  {decided / n:6.1%}")
    print(f"  both                      {both:4d} / {n}  {both / n:6.1%}")
    print(f"  test only, under the band {test_only:4d} / {n}  "
          f"{test_only / n:6.1%}")
    print(f"  band only, not decided    {band_only:4d} / {n}  "
          f"{band_only / n:6.1%}")
    print("\n  \"test only\" is not a correction of the band. It is a difference")
    print("  this instrument reproduces across replays yet cannot resolve "
          "against its own")
    print("  noise -- consistency, not magnitude, and useless for choosing an "
          "action in")
    print("  production, where one execution is all anyone gets.")
    if any_sampled:
        print(f"\n  NOTE: some reference sets exceeded {ENUMERATION_LIMIT} "
              f"splits and were sampled\n  with seed {PERM_SEED}; those "
              f"p-values are estimates and are labelled here.")

    if args.by_point:
        print("\nL2, by design point -- the independent unit for a family claim")
        by_point = collections.defaultdict(lambda: [0, 0, 0])
        for key, res, dec, *_ in rows:
            rec = by_point[key[0]]
            rec[0] += 1
            rec[1] += res
            rec[2] += dec
        print(f"  {'point':8s}{'fault':>7s}{'cells':>7s}{'resolved':>10s}"
              f"{'decided':>9s}")
        for point in sorted(by_point):
            cnt, res, dec = by_point[point]
            fault = next(meta[k]["fault_type"] for k in meta if k[0] == point)
            print(f"  {point:8s}{fault:>7s}{cnt:7d}{res:10d}{dec:9d}")
        print("  Cells inside one point share the fault schedule and the "
              "workload stream, so\n  these counts are the point's, not twelve "
              "independent observations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
