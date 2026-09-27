#!/usr/bin/env python3
"""Conformal risk control on the set-level loss, exactly as the manuscript states.

Two things are defined here and nothing else, because both are the kind of choice
that decides a result and so must be visible in one place.

THE FAILURE INDICATOR. Equation (8) needs a binary Y^a per branch, observed by
executing a. The objective is continuous, so a rule is required, and it is
declared rather than chosen: a branch FAILS when its measured over-budget-plus-
undelivered fraction exceeds theta, where

    theta = Q0.99 of Y_ms over pre-fault no-action branches, CALIBRATION SPLIT ONLY

This mirrors the latency budget rule of protocol 0.6: the threshold comes from
what a healthy system does, measured on data set aside for calibration, and is
then frozen. It cannot be computed on validation or test rows, and this module
refuses if asked. A rule read off the test set is not a rule.

A fixed theta such as zero was rejected for a measurable reason: a healthy branch
has a non-zero violation fraction, so theta = 0 makes every branch a failure and
the loss in (8) is identically one for every threshold, which carries no
information and yields tau_hat = -inf.

THE CALIBRATION UNIT. A run, never a decision point. Anchors inside one run are
temporally dependent and are not exchangeable, so the loss is averaged within a
run first and the runs are the exchangeable sample. A run is identified by its
seed together with its design point -- not by scenario id, which two replicates
share.
"""
import argparse
import csv
import sys

import numpy as np

LOSS_BOUND = 1.0


def failure_threshold(cal_rows, jobs_rows, quantile=0.99):
    """theta, from healthy no-action branches in the calibration split only."""
    cal_names = {r["name"] for r in cal_rows}
    healthy = [float(j["Y_ms"]) for j in jobs_rows
               if j["branch"] in cal_names
               and j["action"] == "NO_OP" and j["regime"] == "pre-fault"]
    if len(healthy) < 10:
        raise SystemExit(
            f"REFUSED: {len(healthy)} pre-fault no-action branches in the "
            "calibration split. The failure threshold is a property of a healthy "
            "system and cannot be estimated from fewer than ten. Add early "
            "anchors or more calibration seeds -- do not borrow rows from "
            "another split.")
    theta = float(np.quantile(healthy, quantile))
    return theta, len(healthy)


def failed(y_ms, theta):
    return float(y_ms) > theta


def run_id(rec):
    return (rec["seed"], rec["fault_type"], rec["fault_onset"],
            rec["fault_severity"], rec["workload_level"])


def calibrate(cal_rows, risk, unc, fail, u_max, delta, grid=None):
    """tau_hat by equation (9): the LARGEST threshold whose corrected empirical
    risk is still at or below delta.

    risk, unc and fail are dicts keyed by branch name: the predicted risk of the
    action that branch executed, the ensemble's uncertainty for it, and whether
    the branch actually failed.
    """
    # Group by run, then by anchor within the run.
    runs = {}
    for r in cal_rows:
        runs.setdefault(run_id(r["rec"]), {}).setdefault(r["rec"]["anchor"],
                                                        []).append(r)
    if len(runs) < 2:
        raise SystemExit(
            f"REFUSED: {len(runs)} calibration run(s). Equation (9)'s correction "
            "is meaningless at n=1 and the guarantee would be a decoration.")

    if grid is None:
        vals = sorted({risk[r["name"]] for r in cal_rows})
        grid = [-np.inf] + vals

    def empirical(tau):
        per_run = []
        for anchors in runs.values():
            hits = 0
            for branches in anchors.values():
                # Does the admissible set at this anchor contain a
                # failure-inducing action? Admissibility is predicted; failure
                # is observed in that action's own replay branch.
                for b in branches:
                    n = b["name"]
                    if risk[n] <= tau and unc[n] <= u_max and fail[n]:
                        hits += 1
                        break
            per_run.append(hits / len(anchors))
        return float(np.mean(per_run)), len(runs)

    best, curve = -np.inf, []
    for tau in grid:
        lhat, n = empirical(tau)
        corrected = (n * lhat + LOSS_BOUND) / (n + 1)
        curve.append((tau, lhat, corrected))
        if corrected <= delta:
            best = tau
    return best, curve, len(runs)


def main():
    ap = argparse.ArgumentParser(description="calibrate tau_hat and report the "
                                             "risk curve")
    ap.add_argument("root")
    ap.add_argument("jobs_csv")
    ap.add_argument("--delta", type=float, default=0.10,
                    help="declared risk level; equation (9) makes the "
                         "calibration sample size a consequence of this, see "
                         "predictor.min_calibration_runs")
    ap.add_argument("--u-max", type=float, default=0.15)
    args = ap.parse_args()

    import predictor
    rows = predictor.load_rows(args.root, args.jobs_csv)
    jobs = list(csv.DictReader(open(args.jobs_csv)))
    sp = predictor.splits(rows)
    theta, n_healthy = failure_threshold(sp["cal"], jobs)
    print(f"failure threshold theta = {theta:.4f} "
          f"(Q0.99 of Y_ms over {n_healthy} healthy no-action calibration branches)")

    names = sorted(rows[0]["x"])
    actions = sorted({r["rec"]["action"] for r in rows})
    ens = predictor.Ensemble(names, actions).fit(sp["train"])
    yhat, unc = ens.predict(sp["cal"])
    risk = {r["name"]: float(v) for r, v in zip(sp["cal"], yhat)}
    uncd = {r["name"]: float(v) for r, v in zip(sp["cal"], unc)}
    ym = {j["branch"]: float(j["Y_ms"]) for j in jobs}
    fail = {r["name"]: failed(ym[r["name"]], theta) for r in sp["cal"]}
    print(f"observed failures in the calibration split: "
          f"{sum(fail.values())}/{len(fail)}")

    tau, curve, n = calibrate(sp["cal"], risk, uncd, fail, args.u_max, args.delta)
    print(f"\ncalibration runs n = {n}, delta = {args.delta}, "
          f"U_max = {args.u_max}")
    print(f"{'tau':>10s} {'empirical L':>12s} {'corrected':>10s}  admissible")
    for t, l, c in curve[:14]:
        print(f"{t:10.4f} {l:12.4f} {c:10.4f}  {'yes' if c <= args.delta else 'no'}")
    if tau == -np.inf:
        print("\ntau_hat = -inf: NO threshold meets the risk level on this "
              "calibration set.")
        print("  The admissible set is then always empty and the controller "
              "always abstains.")
        print("  That is a reportable outcome, not an error: at this delta the "
              "measurement cannot")
        print("  certify any action. Raise delta only by amendment, never to "
              "make a result appear.")
        return 1
    print(f"\ntau_hat = {tau:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
