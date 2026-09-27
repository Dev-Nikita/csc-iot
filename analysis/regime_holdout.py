#!/usr/bin/env python3
"""Does skill in the spanning regime transfer, or is it knowledge of the design?

In the spanning regime the fault arrives inside the horizon and nothing in the
state at the decision instant carries it. The predictor nevertheless does far
better than a constant there. Two explanations fit, and they mean opposite
things for the paper:

  transfer   the model reads what has already accumulated and the mapping from
             accumulated state to outcome is the same whether or not a fault is
             coming. Then the skill is real and the controller would have it in
             a deployment.

  design     the model has learned the distribution of onsets from training
             branches that span faults, and is applying it. Then the skill is
             knowledge of this experiment and would not exist in a system whose
             faults arrive on an unknown schedule.

Two holdouts separate them. The permissive one removes every spanning branch
from training and tests on spanning: it asks whether spanning examples are
needed at all. The strict one additionally removes the test branch's whole fault
design point, so the model has seen neither this fault setting nor any branch
that spans a fault. The strict figure is the one that supports a claim.
"""
import argparse
import json
import sys

import numpy as np

import leakage_tests as L


def design_point(rec):
    return (rec["fault_type"], rec["fault_onset"], rec["fault_severity"],
            rec["workload_level"])


def knn(xt, yt, xv, k=10):
    mu, sd = xt.mean(0), xt.std(0)
    sd[sd == 0] = 1.0
    xt, xv = (xt - mu) / sd, (xv - mu) / sd
    dist = ((xv[:, None, :] - xt[None, :, :]) ** 2).sum(-1)
    idx = np.argpartition(dist, min(k, xt.shape[0] - 1), axis=1)[:, :k]
    return yt[idx].mean(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("jobs_csv")
    ap.add_argument("--regime", default="spanning")
    ap.add_argument("--json")
    args = ap.parse_args()

    rows = L.load(args.root)
    L.targets(rows, args.jobs_csv)
    actions = sorted({r["rec"]["action"] for r in rows})
    names = sorted(rows[0]["x"])
    X = L.design(rows, names, actions)
    y = np.array([r["y"] for r in rows])
    reg = np.array([r["rec"]["regime"] for r in rows])
    dp = np.array([str(design_point(r["rec"])) for r in rows])

    test_mask = reg == args.regime
    if test_mask.sum() < 50:
        sys.exit(f"only {test_mask.sum()} {args.regime} branches; not enough")
    print(f"{len(rows)} branches, {test_mask.sum()} in the {args.regime} regime, "
          f"{len(set(dp))} fault design points")

    out = {"regime": args.regime, "n_test": int(test_mask.sum())}

    # Reference: the design-point holdout already reported, restricted to this
    # regime's rows. Training here DOES include other spanning branches.
    errs = []
    for held in sorted(set(dp)):
        te = test_mask & (dp == held)
        tr = dp != held
        if te.sum() == 0:
            continue
        errs.append(np.abs(knn(X[tr], y[tr], X[te]) - y[te]))
    out["design_point_holdout"] = float(np.mean(np.concatenate(errs)))

    # Permissive: no spanning branch in training at all.
    tr = ~test_mask
    out["regime_holdout"] = float(np.mean(np.abs(
        knn(X[tr], y[tr], X[test_mask]) - y[test_mask])))

    # Strict: no spanning branch AND not this fault design point.
    errs = []
    for held in sorted(set(dp)):
        te = test_mask & (dp == held)
        tr = (~test_mask) & (dp != held)
        if te.sum() == 0 or tr.sum() < 50:
            continue
        errs.append(np.abs(knn(X[tr], y[tr], X[te]) - y[te]))
    out["strict_holdout"] = float(np.mean(np.concatenate(errs)))

    # References that make the numbers readable.
    errs = []
    for held in sorted(set(dp)):
        te = test_mask & (dp == held)
        tr = dp != held
        if te.sum() == 0:
            continue
        errs.append(np.abs(y[tr].mean() - y[te]))
    out["constant"] = float(np.mean(np.concatenate(errs)))
    out["spread"] = float(np.std(y[test_mask]))

    print(f"\nmean |error| on the {args.regime} branches")
    print(f"  design-point holdout   {out['design_point_holdout']:.4f}   "
          f"(spanning examples allowed in training)")
    print(f"  regime holdout         {out['regime_holdout']:.4f}   "
          f"(no spanning branch in training)")
    print(f"  strict holdout         {out['strict_holdout']:.4f}   "
          f"(no spanning branch, and this fault setting unseen)")
    print(f"  predict-the-mean       {out['constant']:.4f}")
    print(f"  s.d. of J_obs here     {out['spread']:.4f}")

    ratio = (out["strict_holdout"] / out["design_point_holdout"]
             if out["design_point_holdout"] else float("inf"))
    print(f"\n  strict / design-point  {ratio:.2f}x")
    if out["strict_holdout"] >= out["constant"]:
        verdict = ("DESIGN: with no spanning branch in training and this fault "
                   "unseen, the model is no better than a constant. The skill "
                   "reported on spanning branches came from having seen the "
                   "onset distribution, not from reading the state.")
    elif ratio <= 2.0:
        verdict = ("TRANSFER: the skill survives with no spanning branch in "
                   "training and an unseen fault setting, so it comes from what "
                   "has already accumulated in the observed state.")
    else:
        verdict = ("PARTIAL: the skill survives but degrades substantially. "
                   "Part of it was knowledge of the onset distribution. Report "
                   "both figures and claim only the strict one.")
    print(f"\n  {verdict}")
    out["verdict"] = verdict.split(":")[0]
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
