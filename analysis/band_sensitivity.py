#!/usr/bin/env python3
"""How much of the gate outcome depends on which replay band is used.

The preregistered band is the POOLED Q0.95 of within-cell pairwise |delta J|.
The protocol also says a band that holds on average and fails in one cell is
not a band, so the pooled figure alone cannot decide anything: it is an average
over cells whose dispersion differs, and cells where J is constant pull it
down. This reports the gate under three bands and says which contrasts survive
all of them.

  pooled  the preregistered band; the headline number
  worst   the worst single cell in the run; the most conservative reading
  local   the larger of the two cells entering that contrast; the band that
          actually applies to it

It also bootstraps the contrast itself, which asks a different question from
the gate: not "is the effect larger than replay noise" but "is the median
difference distinguishable from zero given ten repeats".
"""
import argparse
import csv
import itertools
import random
import sys


def quantile(vals, q):
    if not vals:
        return 0.0
    v = sorted(vals)
    return v[min(int(q * (len(v) - 1) + 0.5), len(v) - 1)]


def dispersion(vals):
    return quantile([abs(a - b) for a, b in itertools.combinations(vals, 2)], 0.95)


def median(vals):
    v = sorted(vals)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def boot_ci(a, b, n=10000, seed=20260925):
    """Percentile CI for median(a) - median(b), resampling repeats in each cell."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        ra = [a[rng.randrange(len(a))] for _ in a]
        rb = [b[rng.randrange(len(b))] for _ in b]
        diffs.append(median(ra) - median(rb))
    diffs.sort()
    lo = diffs[int(0.025 * (n - 1) + 0.5)]
    hi = diffs[int(0.975 * (n - 1) + 0.5)]
    return lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_csv")
    ap.add_argument("--gate", type=float, default=3.0)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.jobs_csv)))
    cells = {}
    for r in rows:
        cells.setdefault((r["anchor"], r["action"]), []).append(float(r["J_obs"]))

    eta = {k: dispersion(v) for k, v in cells.items()}
    pooled = quantile([abs(a - b) for v in cells.values()
                       for a, b in itertools.combinations(v, 2)], 0.95)
    worst = max(eta.values())

    print(f"{len(rows)} branches, {len(cells)} cells")
    print(f"\nBAND")
    print(f"  pooled (preregistered) {pooled:.4f}")
    print(f"  worst cell             {worst:.4f}   ratio {worst / pooled:.2f}x")
    evals = sorted(eta.values())
    print(f"  per-cell band: min {evals[0]:.4f}  median {median(evals):.4f}  "
          f"max {evals[-1]:.4f}")
    flat = [k for k, v in eta.items() if v == 0.0]
    print(f"  cells with zero dispersion: {len(flat)}/{len(cells)}"
          + (f"  e.g. {', '.join('-'.join(k) for k in sorted(flat)[:4])}" if flat else ""))
    if flat:
        print("  A cell where J_obs is constant contributes no pairwise difference")
        print("  and pulls the pooled band DOWN. The pooled band is therefore not")
        print("  conservative for the cells that do vary.")

    anchors = sorted({a for a, _ in cells})
    actions = sorted({b for _, b in cells} - {"NO_OP"})
    print(f"\nGATE SNR_J >= {args.gate:g} UNDER THREE BANDS, and the bootstrap CI")
    print(f"{'contrast':18s} {'delta':>8s} {'pooled':>8s} {'worst':>8s} {'local':>8s}"
          f" {'local band':>11s}   95% CI of delta        survives")
    counts = {"pooled": 0, "worst": 0, "local": 0, "all": 0, "ci": 0}
    total = 0
    surviving = []
    for a in anchors:
        base = cells.get((a, "NO_OP"))
        if not base:
            continue
        for act in actions:
            v = cells.get((a, act))
            if not v:
                continue
            total += 1
            delta = abs(median(base) - median(v))
            local = max(eta[(a, "NO_OP")], eta[(a, act)])
            s_pool = delta / pooled if pooled else float("inf")
            s_worst = delta / worst if worst else float("inf")
            s_local = delta / local if local else float("inf")
            lo, hi = boot_ci(base, v)
            ci_excl = lo > 0 or hi < 0
            ok = {"pooled": s_pool >= args.gate, "worst": s_worst >= args.gate,
                  "local": s_local >= args.gate}
            for k, good in ok.items():
                counts[k] += good
            counts["ci"] += ci_excl
            all_ok = all(ok.values()) and ci_excl
            counts["all"] += all_ok
            if all_ok:
                surviving.append(f"{a}-{act}")
            print(f"{a + '-' + act:18s} {delta:8.3f} {s_pool:8.2f} {s_worst:8.2f}"
                  f" {s_local:8.2f} {local:11.4f}   "
                  f"[{lo:+.3f}, {hi:+.3f}]   {'yes' if all_ok else 'no'}")

    print(f"\nRESOLVABLE OUT OF {total}")
    print(f"  pooled band (preregistered) {counts['pooled']:3d}  "
          f"= {counts['pooled'] / total:.3f}")
    print(f"  worst-cell band             {counts['worst']:3d}  "
          f"= {counts['worst'] / total:.3f}")
    print(f"  local band                  {counts['local']:3d}  "
          f"= {counts['local'] / total:.3f}")
    print(f"  bootstrap CI excludes zero  {counts['ci']:3d}  "
          f"= {counts['ci'] / total:.3f}")
    print(f"  survives ALL FOUR           {counts['all']:3d}  "
          f"= {counts['all'] / total:.3f}")
    print("\n  The preregistered figure is the pooled one and is what the")
    print("  hypothesis was stated against. The 'all four' set is what can be")
    print("  claimed without depending on which band is chosen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
