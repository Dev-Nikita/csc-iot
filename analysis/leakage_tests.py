#!/usr/bin/env python3
"""Two of the three leakage tests, on a recorded run.

The third is the schema test, which lives in analysis/test_features.py because
it is a property of the code rather than of a dataset.

  permutation  telemetry permuted BETWEEN scenarios must destroy skill. If it
               survives, the model is reading something other than telemetry.
               Refused outright on a single-scenario run: there is nothing to
               permute between, and a test that cannot fail must not report
               success.

  time-only    a predictor given only elapsed time and the candidate action must
               be materially worse than the telemetry model. If the clock alone
               does nearly as well, the scenario confound is still there.

The model here is deliberately plain -- ridge regression on standardised
features, fitted with numpy. This file tests the data, not the architecture, and
a strong learner would make a weak confound harder to see.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

import branches
import features

MARGIN = 0.20  # the telemetry model must cut error by at least this fraction


def load(root):
    matrix = branches.read_matrix(root)
    pattern = "s*-a*" if glob.glob(os.path.join(root, "s*-a*")) else "a*"
    rows = []
    for d in sorted(glob.glob(os.path.join(root, pattern))):
        if not os.path.exists(os.path.join(d, "outcome.json")):
            continue
        rec = branches.read(d, matrix)
        rows.append({"dir": d, "rec": rec, "x": features.extract(d)})
    if not rows:
        raise SystemExit(f"no branches under {root}")
    return rows


def targets(rows, jobs_csv):
    import csv
    j = {r["branch"]: float(r["J_obs"]) for r in csv.DictReader(open(jobs_csv))}
    missing = [os.path.basename(r["dir"]) for r in rows
               if os.path.basename(r["dir"]) not in j]
    if missing:
        raise SystemExit(f"{len(missing)} branches have no J_obs in {jobs_csv}")
    for r in rows:
        r["y"] = j[os.path.basename(r["dir"])]


def design(rows, names, actions):
    x = np.array([[r["x"][n] for n in names] for r in rows], dtype=float)
    # The action enters as an indicator: the predictor is action-conditioned.
    a = np.array([[1.0 if r["rec"]["action"] == act else 0.0 for act in actions]
                  for r in rows])
    return np.hstack([x, a, np.ones((len(rows), 1))])


def ridge_cv(rows, names, actions, groups, lam=1.0):
    """Mean absolute out-of-fold error, folds held out by group."""
    y = np.array([r["y"] for r in rows])
    g = np.array(groups)
    errs = []
    for held in sorted(set(g)):
        tr, te = g != held, g == held
        xt = design([r for r, m in zip(rows, tr) if m], names, actions)
        xv = design([r for r, m in zip(rows, te) if m], names, actions)
        mu, sd = xt.mean(0), xt.std(0)
        sd[sd == 0] = 1.0
        xt_s, xv_s = (xt - mu) / sd, (xv - mu) / sd
        w = np.linalg.solve(xt_s.T @ xt_s + lam * np.eye(xt_s.shape[1]),
                            xt_s.T @ y[tr])
        errs.append(np.abs(xv_s @ w - y[te]))
    return float(np.mean(np.concatenate(errs)))


def mean_cv(rows, groups):
    """Predict the training folds' mean. Without this reference the errors above
    are unreadable: a model can look precise and still be worse than a constant."""
    y = np.array([r["y"] for r in rows])
    g = np.array(groups)
    errs = []
    for held in sorted(set(g)):
        tr, te = g != held, g == held
        errs.append(np.abs(y[te] - y[tr].mean()))
    return float(np.mean(np.concatenate(errs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("jobs_csv")
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()

    rows = load(args.root)
    targets(rows, args.jobs_csv)
    actions = sorted({r["rec"]["action"] for r in rows})
    names = sorted(rows[0]["x"])
    scenarios = sorted({r["rec"]["scenario_id"] for r in rows})
    print(f"{len(rows)} branches, {len(scenarios)} scenario(s), "
          f"{len(names)} telemetry features, actions {actions}")

    # Folds are held out by scenario when there is more than one, because a
    # random split lets a model interpolate inside a scenario it has seen.
    if len(scenarios) > 1:
        groups = [r["rec"]["scenario_id"] for r in rows]
        held_by = "scenario"
    else:
        groups = [r["rec"]["anchor"] for r in rows]
        held_by = "anchor (single-scenario run: weaker, see below)"

    full = ridge_cv(rows, names, actions, groups)
    time_only = ridge_cv(rows, list(features.TIME_ONLY), actions, groups)
    constant = mean_cv(rows, groups)
    spread = float(np.std([r["y"] for r in rows]))
    print(f"\nheld out by: {held_by}")
    print(f"  mean |error| telemetry model     {full:.4f}")
    print(f"  mean |error| time-only f(t,a)    {time_only:.4f}")
    print(f"  mean |error| predict-the-mean    {constant:.4f}")
    print(f"  standard deviation of J_obs      {spread:.4f}")
    if full >= constant:
        print("\n  NOTE: the telemetry model is no better than predicting the")
        print("  training mean. Held out this way the task is not learnable at all,")
        print("  so the comparison below says nothing about the telemetry itself.")

    # A model with no skill cannot be shown to be reading the wrong thing.
    # Reporting FAIL here would announce leakage when the real finding is that
    # there is no signal to leak, which is a different problem with a different
    # fix: more scenarios, not fewer features.
    no_skill = full >= constant
    print("\nTEST: time-only baseline")
    if no_skill:
        print("  INCONCLUSIVE: the telemetry model does not beat the training")
        print("  mean, so there is no skill whose source could be attributed.")
        ok_time = None
    elif time_only <= 0:
        print("  INCONCLUSIVE: the time-only model has zero error")
        ok_time = False
    else:
        cut = 1.0 - full / time_only
        print(f"  telemetry cuts the time-only error by {cut:+.1%} "
              f"(required: {MARGIN:.0%})")
        ok_time = cut >= MARGIN
        print("  PASS" if ok_time else
              "  FAIL: the clock alone does nearly as well, so the model is not "
              "being made to read the system's state")

    print("\nTEST: permutation across scenarios")
    if no_skill:
        print("  INCONCLUSIVE: permuting the inputs of a model that has no skill")
        print("  cannot make it worse. This test needs a model that predicts")
        print("  something first.")
        ok_perm = None
    elif len(scenarios) < 2:
        print("  REFUSED: one scenario. There is nothing to permute between, and")
        print("  a test that cannot fail must not report success. Re-run this on")
        print("  a multi-scenario matrix.")
        ok_perm = None
    else:
        rng = np.random.default_rng(args.seed)
        order = rng.permutation(len(rows))
        shuffled = [dict(r, x=rows[order[i]]["x"]) for i, r in enumerate(rows)]
        perm = ridge_cv(shuffled, names, actions, groups)
        print(f"  mean |error| with telemetry permuted {perm:.4f} "
              f"(intact {full:.4f})")
        ok_perm = perm > full * 1.2
        print("  PASS" if ok_perm else
              "  FAIL: permuting the telemetry barely hurt, so the skill was "
              "not coming from the telemetry")

    failed = (ok_time is False) or (ok_perm is False)
    if failed:
        print("\nLeakage detected. The dataset is not cleared for modelling.")
        return 1
    if ok_time is None or ok_perm is None:
        print("\nNot cleared, and not because of leakage: a test could not be")
        print("run. Fix what the message above names before training anything.")
        return 2
    print("\nBoth tests pass: skill exists and comes from the telemetry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
