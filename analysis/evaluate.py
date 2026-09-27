#!/usr/bin/env python3
"""Compare every decision method on common anchors, in every regime.

The unit is a DECISION POINT, not a branch: one (scenario, anchor) at which
several actions were each executed in their own replay branch. The state at that
anchor is the same for every action there by construction -- it is the state
before any action was applied -- so one feature row serves all candidates and the
action enters as an indicator. That is what makes a common-anchor comparison
possible at all: every method chooses from the same set at the same point, and the
outcome of whatever it chooses was measured rather than modelled.

Metrics, as the manuscript defines them:

  CRA_eta   the chosen action's outcome is within eta_J of the best available
  CRA@2     the chosen action is the best or the second best. With the three
            actions measured here, two of three satisfy it, so it is close to
            uninformative and is reported for completeness rather than as
            evidence. It earns its place only with a larger action set.
  Reg_eta   J_obs(chosen) - min_a J_obs(a), credited as zero inside eta_J
  PFR       N_prev / N_pre  -- of the decision points where doing nothing failed
            and some action did not, the share where the CHOSEN action did not
  WIR       N_harm / N_int  -- of the interventions taken, the share that came out
            worse than doing nothing by more than eta_J

eta_J is the preregistered pooled band: the 0.95 quantile of within-cell pairwise
|delta J|. A method is not credited for a difference the replay cannot resolve,
and it is not penalised for one either.
"""
import argparse
import csv
import itertools
import os
import sys

import numpy as np

import band_sensitivity as bs
import crc
import policies
import predictor

REGIMES = ("pre-fault", "spanning", "post-onset")
TEST_SPLITS = ("test_id", "test_param", "test_mech")


def build_points(rows, jobs, eta):
    """One record per (scenario, anchor), with per-action observed outcomes."""
    by_cell = {}
    for r in rows:
        by_cell.setdefault((r["rec"]["scenario_id"], r["rec"]["anchor"]),
                           []).append(r)
    ym = {j["branch"]: float(j["Y_ms"]) for j in jobs}
    points = []
    for (sc, anchor), group in sorted(by_cell.items()):
        per_action = {}
        for r in group:
            per_action.setdefault(r["rec"]["action"], []).append(r)
        if "NO_OP" not in per_action or len(per_action) < 2:
            continue      # a decision point with no alternative is not one
        points.append({
            "scenario": sc, "anchor": anchor,
            "regime": group[0]["rec"]["regime"],
            "point": group[0]["point"],
            "x": group[0]["x"],
            "rows": per_action,
            "j_obs": {a: bs.median([v["y"] for v in vs])
                      for a, vs in per_action.items()},
            "y_ms": {a: bs.median([ym[v["name"]] for v in vs])
                     for a, vs in per_action.items()},
        })
    return points


def attach_predictions(points, ens, actions):
    """Predict risk and uncertainty for EVERY candidate at each point.

    The prediction is made on the anchor's own state with the action indicator
    swapped, so a method is asked what it would do rather than told what happened.
    """
    for p in points:
        base = p["rows"][next(iter(p["rows"]))][0]
        probes = []
        for a in actions:
            probe = dict(base)
            probe["rec"] = dict(base["rec"])
            probe["rec"]["action"] = a
            probes.append(probe)
        yhat, unc = ens.predict(probes)
        p["risk"] = {a: float(v) for a, v in zip(actions, yhat)
                     if a in p["j_obs"]}
        p["unc"] = {a: float(v) for a, v in zip(actions, unc)
                    if a in p["j_obs"]}


def costs_from_calibration(cal_rows, jobs):
    """C(a) from the calibration split only, clipped to [0,1], NO_OP at zero.

    Only disruption is instrumented, so three of the four declared weights are
    zero. That is recorded rather than hidden: jobs.py already refuses to call
    this a complete objective, and the same reduction applies here.
    """
    disruption = {j["branch"]: float(j["disruption"]) for j in jobs}
    per_action = {}
    for r in cal_rows:
        a = r["rec"]["action"]
        if a == "NO_OP":
            continue
        per_action.setdefault(a, []).append(disruption[r["name"]])
    if not per_action:
        raise SystemExit("REFUSED: no intervention branches in the calibration "
                         "split; C(a) cannot be normalised")
    raw = {a: float(np.mean(v)) for a, v in per_action.items()}
    lo, hi = min(raw.values()), max(raw.values())
    span = hi - lo
    # With only two priced interventions, range normalisation puts one at 0 and
    # the other at 1, so the cost term collapses to a FIXED PREFERENCE ORDER and
    # the contribution of minimum-necessary intervention cannot be separated from
    # "always prefer the cheaper intervention". This is a limitation of the
    # measured action set, not of the rule, and it belongs in the paper. A third
    # priced action -- migration -- is what would make the ordering informative.
    cost = {"NO_OP": 0.0}
    for a, v in raw.items():
        # A degenerate range means the actions are indistinguishable on the one
        # component that is measured; they are then tied rather than ordered by
        # floating-point noise.
        cost[a] = 0.5 if span <= 1e-12 else min(max((v - lo) / span, 0.0), 1.0)
    return cost, raw


def metrics(points, chosen, eta):
    """CRA_eta, CRA@2, Reg_eta, PFR, WIR over a set of decision points."""
    n = len(points)
    if n == 0:
        return None
    cra = cra2 = 0
    regret = []
    n_pre = n_prev = n_int = n_harm = 0
    abstained = 0
    for p, (a, absten) in zip(points, chosen):
        j = p["j_obs"]
        best = min(j.values())
        order = sorted(j, key=lambda k: j[k])
        got = j.get(a, max(j.values()))
        cra += (got - best) <= eta
        cra2 += a in order[:2]
        regret.append(0.0 if (got - best) <= eta else got - best)
        abstained += absten

        # PFR and WIR rest on executed alternatives, never on an opinion of them.
        noop_failed = p["failed"]["NO_OP"]
        some_action_ok = any(not p["failed"][k] for k in p["failed"]
                             if k != "NO_OP")
        if noop_failed and some_action_ok:
            n_pre += 1
            if not p["failed"].get(a, True):
                n_prev += 1
        if a != "NO_OP":
            n_int += 1
            if got - j["NO_OP"] > eta:
                n_harm += 1
    return {"n": n, "CRA_eta": cra / n, "CRA@2": cra2 / n,
            "Reg_eta": float(np.mean(regret)),
            "PFR": (n_prev / n_pre) if n_pre else float("nan"),
            "WIR": (n_harm / n_int) if n_int else float("nan"),
            "N_pre": n_pre, "N_int": n_int,
            "abstention": abstained / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("jobs_csv")
    ap.add_argument("--delta", type=float, default=0.10)
    ap.add_argument("--u-max", type=float, default=0.15)
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true",
                    help="exercise every code path on a scenario set too small "
                         "to carry the guarantee. Shrinks the split counts, "
                         "prints a banner, and stamps every output row "
                         "reportable=0. For testing the pipeline before a long "
                         "run, never for a number that reaches the paper.")
    args = ap.parse_args()

    rows = predictor.load_rows(args.root, args.jobs_csv)
    jobs = list(csv.DictReader(open(args.jobs_csv)))
    if args.dry_run:
        print("=" * 72)
        print("DRY RUN. The split counts below are too small for equation (9),")
        print("so tau_hat, PFR, WIR and every rate here are pipeline output and")
        print("NOT measurements. Every row is stamped reportable=0.")
        print("=" * 72)
        sp = predictor.splits(rows, cal_runs=4, val_runs=3, test_id_runs=3)
    else:
        sp = predictor.splits(rows)
    names = sorted(rows[0]["x"])
    actions = sorted({r["rec"]["action"] for r in rows})

    need = predictor.min_calibration_runs(args.delta)
    got = len({crc.run_id(r["rec"]) for r in sp["cal"]})
    print(f"delta {args.delta}: equation (9) needs about n = {need} calibration "
          f"runs; this split has {got}")
    if got < need:
        print("  The guarantee cannot hold on this split. Reported anyway, "
              "marked as such,")
        print("  because hiding it would be worse than reporting it.")

    theta, n_healthy = crc.failure_threshold(sp["cal"], jobs)
    print(f"failure threshold theta = {theta:.4f} (Q0.99 of Y_ms over "
          f"{n_healthy} healthy no-action calibration branches)")
    eta = bs.quantile([abs(a - b) for cell in _cells(rows).values()
                       for a, b in itertools.combinations(cell, 2)], 0.95)
    print(f"eta_J (preregistered pooled band) = {eta:.4f}")

    ens = predictor.Ensemble(names, actions).fit(sp["train"])
    cost, raw_cost = costs_from_calibration(sp["cal"], jobs)
    print("C(a) from the calibration split, disruption only: "
          + ", ".join(f"{a} {cost[a]:.3f}" for a in sorted(cost)))

    # tau_hat, on the calibration split, before any test set is touched.
    yhat_cal, unc_cal = ens.predict(sp["cal"])
    risk_cal = {r["name"]: float(v) for r, v in zip(sp["cal"], yhat_cal)}
    uncd_cal = {r["name"]: float(v) for r, v in zip(sp["cal"], unc_cal)}
    ym = {j["branch"]: float(j["Y_ms"]) for j in jobs}
    fail_cal = {r["name"]: crc.failed(ym[r["name"]], theta) for r in sp["cal"]}
    tau, _, n_runs = crc.calibrate(sp["cal"], risk_cal, uncd_cal, fail_cal,
                                   args.u_max, args.delta)
    print(f"tau_hat = {tau if tau != -float('inf') else '-inf'}  "
          f"(n = {n_runs} calibration runs)")

    # B1's thresholds come from validation, never from a test split.
    val_points = build_points(sp["val"], jobs, eta)
    for p in val_points:
        p["failed"] = {a: crc.failed(v, theta) for a, v in p["y_ms"].items()}
    attach_predictions(val_points, ens, actions)
    (dt, bt), b1_val = policies.fit_b1(val_points)
    print(f"B1 thresholds chosen on validation: deficit {dt}, backlog {bt} "
          f"(mean J_obs {b1_val:.4f})")

    time_ens = predictor.Ensemble(["epoch"], actions).fit(sp["train"])

    out_rows = []
    for split in TEST_SPLITS:
        if not sp[split]:
            print(f"\n{split.upper()}: empty. Not measurable, not claimed.")
            continue
        pts = build_points(sp[split], jobs, eta)
        if not pts:
            print(f"\n{split.upper()}: no decision point with an alternative.")
            continue
        for p in pts:
            p["failed"] = {a: crc.failed(v, theta) for a, v in p["y_ms"].items()}
            p["cost"] = {a: cost[a] for a in p["j_obs"]}
        attach_predictions(pts, ens, actions)
        t_hat, t_unc = time_ens.predict(
            [dict(p["rows"][next(iter(p["rows"]))][0]) for p in pts])
        for p, _ in zip(pts, t_hat):
            p["risk_time"] = {}
        for i, p in enumerate(pts):
            probes = []
            for a in actions:
                pr = dict(p["rows"][next(iter(p["rows"]))][0])
                pr["rec"] = dict(pr["rec"])
                pr["rec"]["action"] = a
                probes.append(pr)
            th, _ = time_ens.predict(probes)
            p["risk_time"] = {a: float(v) for a, v in zip(actions, th)
                              if a in p["j_obs"]}

        methods = {
            "B1_threshold": lambda p: policies.b1_threshold(p, dt, bt),
            "B2_assoc": lambda p: policies.lowest_risk(p, "risk"),
            "B5t_time_only": lambda p: policies.lowest_risk(p, "risk_time"),
            "B6_csc": lambda p: policies.b6_csc(p, tau, args.u_max),
            "A1a_no_unc_filter": lambda p: policies.a1a_no_uncertainty_filter(
                p, tau),
            "A1b_no_gate": policies.a1b_no_gate_at_all,
            "A2_no_mni": lambda p: policies.a2_no_mni(p, tau, args.u_max),
            # Not a method: the best available action at each point, as an
            # upper bound on what any rule could reach on this matrix.
            "oracle_bound": lambda p: (
                min(p["j_obs"], key=lambda a: p["j_obs"][a]), False),
        }
        print(f"\n{split.upper()}  ({len(pts)} decision points)")
        print(f"  {'method':14s} {'n':>4s} {'CRA_eta':>8s} {'CRA@2':>7s} "
              f"{'Reg_eta':>8s} {'PFR':>7s} {'WIR':>7s} {'abst':>6s}")
        for label, fn in methods.items():
            for reg in ("all",) + REGIMES:
                sub = pts if reg == "all" else [p for p in pts
                                                if p["regime"] == reg]
                if not sub:
                    continue
                m = metrics(sub, [fn(p) for p in sub], eta)
                if reg == "all":
                    print(f"  {label:14s} {m['n']:4d} {m['CRA_eta']:8.3f} "
                          f"{m['CRA@2']:7.3f} {m['Reg_eta']:8.4f} "
                          f"{m['PFR']:7.3f} {m['WIR']:7.3f} "
                          f"{m['abstention']:6.3f}")
                out_rows.append({"split": split, "method": label,
                                 "regime": reg, "eta_J": eta, "tau": tau,
                                 "theta": theta,
                                 "reportable": 0 if args.dry_run else 1, **m})

    if args.out and out_rows:
        with open(args.out, "w") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nwrote {args.out}")
    return 0


def _cells(rows):
    cells = {}
    for r in rows:
        cells.setdefault((r["rec"]["scenario_id"], r["rec"]["anchor"],
                          r["rec"]["action"]), []).append(r["y"])
    return cells


if __name__ == "__main__":
    sys.exit(main())
