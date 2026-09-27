#!/usr/bin/env python3
"""The preregistered test of the structural model: does it get the DIRECTION right?

The protocol commits to this test and not to an error figure, for a reason. The
controller never needs the value of J_obs; it needs to know which action is
better, and by enough to act on. A model with a large but common bias that
orders actions correctly is useful; a model with a small error that flips signs
is not.

The test therefore restricts attention to the contrasts the measurement itself
can resolve -- those surviving ALL FOUR bands (pooled, worst-cell, local, and a
bootstrap CI of the contrast excluding zero) -- and asks whether the structural
prediction reproduces the sign of each. A contrast the measurement cannot
resolve is excluded from the test in both directions: the model is neither
rewarded nor penalised for it, because there is no ground truth to be right
about.
"""
import argparse
import csv
import itertools
import sys

import band_sensitivity as bs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_csv")
    ap.add_argument("struct_csv", help="output of analysis/structural.py --out")
    ap.add_argument("--gate", type=float, default=3.0)
    args = ap.parse_args()

    # Protocol 0.10: say up front whether the state the model read actually
    # contains the windowed observables, because on older branches the feature
    # extractor falls back to the cumulative rate and the model is then being
    # tested on the state that made it fail.
    import glob
    import os
    import features as _feat
    root = os.path.dirname(os.path.abspath(args.jobs_csv))
    dirs = sorted(glob.glob(os.path.join(root, "s*-a*"))) or \
        sorted(glob.glob(os.path.join(root, "a*")))
    have = 0
    checked = 0
    for d in dirs[:200]:
        if not os.path.exists(os.path.join(d, "anchor.json")):
            continue
        checked += 1
        have += _feat.extract(d)["system_has_windowed_arrivals"] > 0
    if checked:
        print(f"WINDOWED OBSERVABLES present in {have}/{checked} anchors sampled")
        if have == 0:
            print("  These branches predate protocol 0.10, so the model is reading")
            print("  the cumulative fallback. A failure here is expected and is")
            print("  evidence about the telemetry, not about the model.")
        elif have < checked:
            print("  Mixed. Do not compare model layers across this boundary.")
        print()

    obs_cells, hat_cells, regime = {}, {}, {}
    for r in csv.DictReader(open(args.jobs_csv)):
        obs_cells.setdefault((r.get("scenario", "s00"), r["anchor"], r["action"]),
                             []).append(float(r["J_obs"]))
    for r in csv.DictReader(open(args.struct_csv)):
        k = (r["scenario"], r["anchor"], r["action"])
        hat_cells.setdefault(k, []).append(float(r["J_hat"]))
        regime[(r["scenario"], r["anchor"])] = r["regime"]

    eta = {k: bs.dispersion(v) for k, v in obs_cells.items()}
    pooled = bs.quantile([abs(a - b) for v in obs_cells.values()
                          for a, b in itertools.combinations(v, 2)], 0.95)
    worst = max(eta.values())

    keys = sorted({(sc, a) for sc, a, _ in obs_cells})
    actions = sorted({c for _, _, c in obs_cells} - {"NO_OP"})

    resolved, agree, missing = [], 0, 0
    print(f"{'contrast':20s} {'regime':11s} {'obs delta':>10s} {'hat delta':>10s}"
          f"  sign")
    for sc, a in keys:
        base = obs_cells.get((sc, a, "NO_OP"))
        if not base:
            continue
        for act in actions:
            v = obs_cells.get((sc, a, act))
            if not v:
                continue
            # signed: positive means the action is BETTER than doing nothing
            d_obs = bs.median(base) - bs.median(v)
            local = max(eta[(sc, a, "NO_OP")], eta[(sc, a, act)])
            lo, hi = bs.boot_ci(base, v)
            survives = (abs(d_obs) / pooled >= args.gate if pooled else True) and \
                       (abs(d_obs) / worst >= args.gate if worst else True) and \
                       (abs(d_obs) / local >= args.gate if local else True) and \
                       (lo > 0 or hi < 0)
            if not survives:
                continue
            hb, hv = hat_cells.get((sc, a, "NO_OP")), hat_cells.get((sc, a, act))
            if not hb or not hv:
                missing += 1
                continue
            d_hat = bs.median(hb) - bs.median(hv)
            ok = (d_obs > 0) == (d_hat > 0)
            agree += ok
            resolved.append((f"{sc}-{a}-{act}", regime.get((sc, a), "?"),
                             d_obs, d_hat, ok))
            print(f"{sc + '-' + a + '-' + act:20s} {regime.get((sc, a), '?'):11s}"
                  f" {d_obs:+10.4f} {d_hat:+10.4f}  {'ok' if ok else 'FLIPPED'}")

    n = len(resolved)
    print(f"\nRESOLVED CONTRASTS {n}"
          + (f"   ({missing} skipped: no structural prediction)" if missing else ""))
    if n == 0:
        print("  No contrast survives all four bands, so this test says nothing")
        print("  about the model. That is a statement about the measurement.")
        return 2
    print(f"  sign reproduced {agree}/{n} = {agree / n:.3f}")
    for reg in ("pre-fault", "spanning", "post-onset"):
        sub = [r for r in resolved if r[1] == reg]
        if sub:
            k = sum(1 for r in sub if r[4])
            print(f"    {reg:11s} {k}/{len(sub)}")
    flipped = [r for r in resolved if not r[4]]
    if flipped:
        print(f"\n  FAILS the preregistered test: {len(flipped)} sign(s) flipped.")
        for name, reg, do, dh, _ in flipped:
            print(f"    {name} ({reg}) observed {do:+.4f}, predicted {dh:+.4f}")
        print("  The protocol says a flipped sign on a resolvable contrast is a")
        print("  modelling failure, to be reported and not tuned away.")
        return 1
    print("\n  PASSES: every resolvable contrast has the right direction.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
