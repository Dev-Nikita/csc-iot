#!/usr/bin/env python3
"""The action-conditioned predictor ensemble, and the splits every layer shares.

One module owns the splits so that no later script can quietly redraw them. The
split is by DESIGN POINT, never by row and never by scenario id: two scenarios
differing only by seed are replicates, so holding one out and training on the
other tests generalisation to a scenario the model has effectively seen.

Three regimes are produced, matching what the manuscript claims:

  in-distribution   held-out SEEDS at design points the model trained on
  parameter shift   held-out onset and severity values, same mechanism
  mechanism shift   a mechanism the model never saw

A regime with no data is returned empty rather than approximated. If the
scenario set holds one mechanism, mechanism shift is empty and the paper says so
-- that is the state configs/scenarios-b5.json was in, and it is why the set was
regenerated at protocol 0.11.

Uncertainty is the quantile width of the ensemble, as declared: a 5-95 interval
rather than a standard deviation, so that a few divergent members cannot be
averaged away. Members differ by a bootstrap of the training design points and a
random feature subset -- resampling ROWS would leak, because the five repeats of
one cell are near-duplicates and every member would see every cell.
"""
import argparse
import os
import sys

import numpy as np

import leakage_tests as lt

ENSEMBLE_B = 10          # frozen; the pilot's stability choice, see protocol 11b
FEATURE_FRACTION = 0.75
KNN_K = 10
SEED = 20260927


def design_point(rec):
    return (rec["fault_type"], rec["fault_onset"], rec["fault_severity"],
            rec["workload_level"])


def load_rows(root, jobs_csv):
    rows = lt.load(root)
    lt.targets(rows, jobs_csv)
    for r in rows:
        r["point"] = design_point(r["rec"])
        r["name"] = os.path.basename(r["dir"])
        r["cell"] = (r["rec"]["scenario_id"], r["rec"]["anchor"])
    return rows


def feature_names(rows):
    return sorted(k for k in rows[0]["x"] if k not in lt.FORBIDDEN) \
        if hasattr(lt, "FORBIDDEN") else sorted(rows[0]["x"])


CAL_RUNS = 20            # see crc.py: equation (9) needs this, it is not spare capacity
VAL_RUNS = 8
TEST_ID_RUNS = 10
MIN_TRAIN_RUNS = 20


def min_calibration_runs(delta, expected_loss=0.05, bound=1.0):
    """The smallest n for which equation (9) can admit any threshold at all.

    This is arithmetic, not a convention. With the correction term bound/(n+1),
    delta = 0.10 is unreachable below n = 9 even at zero empirical risk, and
    needs about 20 once the calibration set shows a few per cent. A calibration
    split sized as whatever was left over after training produces n = 1 or 2,
    tau_hat = -inf, and a controller that abstains everywhere -- which looks like
    a finding and is an artefact of the split.
    """
    for n in range(1, 10001):
        if (n * expected_loss + bound) / (n + 1) <= delta:
            return n
    return None


def splits(rows, seed=SEED, cal_runs=CAL_RUNS, val_runs=VAL_RUNS,
           test_id_runs=TEST_ID_RUNS):
    """train / validation / calibration / test-ID / test-param / test-mech.

    Calibration is allocated FIRST and to a declared count, because the risk
    guarantee's sample size is a requirement of the method rather than a leftover
    of the split. Deterministic in `seed` and a pure function of the scenario set,
    so the split is part of the declared configuration and not something chosen
    after looking at results.
    """
    rng = np.random.default_rng(seed)
    points = sorted({r["point"] for r in rows})
    mechs = sorted({p[0] for p in points})

    held_mech = mechs[-1] if len(mechs) > 1 else None
    in_mech = [p for p in points if p[0] != held_mech]

    # Parameter shift holds out whole LEVELS, not scenarios: a middle severity,
    # so the held-out value is interpolated rather than extrapolated, and it is
    # chosen by position rather than by which one gives a better number.
    sevs = sorted({p[2] for p in in_mech if p[2] > 0})
    held_sev = sevs[len(sevs) // 2] if len(sevs) >= 3 else None

    def is_param_shift(p):
        return held_sev is not None and p[2] == held_sev

    id_points = {p for p in in_mech if not is_param_shift(p)}
    param_points = {p for p in in_mech if is_param_shift(p)}
    mech_points = {p for p in points if p[0] == held_mech} if held_mech else set()

    # Within the in-distribution points the RUN decides the split, a run being a
    # seed at a design point. The ID test set is therefore new seeds at seen
    # design points, which is what in-distribution means here.
    id_rows = [r for r in rows if r["point"] in id_points]
    runs = sorted({(r["rec"]["seed"],) + r["point"] for r in id_rows})
    min_train = MIN_TRAIN_RUNS if cal_runs >= CAL_RUNS else 4
    need = cal_runs + val_runs + test_id_runs + min_train
    if len(runs) < need:
        per_scenario = max(1, len(runs) // max(1, len(id_points)))
        raise SystemExit(
            f"REFUSED: {len(runs)} in-distribution runs, {need} needed "
            f"({cal_runs} calibration + {val_runs} validation + "
            f"{test_id_runs} ID test + at least {min_train} training).\n"
            f"  The calibration count is set by equation (9), not by taste: at "
            f"delta = 0.10 the correction alone forbids any threshold below "
            f"n = 9, and needs about 20 once the empirical risk is non-zero. A "
            f"smaller calibration split does not give a weaker guarantee, it "
            f"gives tau_hat = -inf and a controller that abstains everywhere.\n"
            f"  This set has {len(points)} design points, of which "
            f"{len(id_points)} are in-distribution "
            f"({len(param_points)} parameter shift, {len(mech_points)} mechanism "
            f"shift). Draw about "
            f"{int(need / max(per_scenario, 1)) - len(id_points)} more "
            f"in-distribution design points and re-run.")
    order = rng.permutation(len(runs))
    shuffled = [runs[i] for i in order]
    blocks = {"cal": set(shuffled[:cal_runs]),
              "val": set(shuffled[cal_runs:cal_runs + val_runs]),
              "test_id": set(shuffled[cal_runs + val_runs:
                                      cal_runs + val_runs + test_id_runs]),
              "train": set(shuffled[cal_runs + val_runs + test_id_runs:])}

    out = {k: [] for k in ("train", "val", "cal", "test_id",
                           "test_param", "test_mech")}
    for r in rows:
        if r["point"] in mech_points:
            out["test_mech"].append(r)
        elif r["point"] in param_points:
            out["test_param"].append(r)
        else:
            key = (r["rec"]["seed"],) + r["point"]
            for k in ("cal", "val", "test_id", "train"):
                if key in blocks[k]:
                    out[k].append(r)
                    break
    return out


class Ensemble:
    """B kNN members over standardised features plus the action indicator."""

    def __init__(self, names, actions, b=ENSEMBLE_B, k=KNN_K, seed=SEED):
        self.names, self.actions, self.b, self.k = names, actions, b, k
        self.rng = np.random.default_rng(seed)
        self.members = []

    def fit(self, rows):
        if not rows:
            raise ValueError("no training rows")
        points = sorted({r["point"] for r in rows})
        by_point = {p: [r for r in rows if r["point"] == p] for p in points}
        nf = max(1, int(len(self.names) * FEATURE_FRACTION))
        for _ in range(self.b):
            # Bootstrap DESIGN POINTS, not rows: the five repeats of a cell are
            # near-duplicates, so resampling rows would put every cell in every
            # member and collapse the ensemble spread to nothing.
            drawn = self.rng.choice(len(points), len(points), replace=True)
            sub = [r for i in drawn for r in by_point[points[i]]]
            cols = np.sort(self.rng.choice(len(self.names), nf, replace=False))
            sel = [self.names[c] for c in cols]
            x = lt.design(sub, sel, self.actions)
            mu, sd = x.mean(0), x.std(0)
            sd[sd == 0] = 1.0
            self.members.append({"sel": sel, "mu": mu, "sd": sd,
                                 "x": (x - mu) / sd,
                                 "y": np.array([r["y"] for r in sub])})
        return self

    def _member_predict(self, m, rows):
        x = (lt.design(rows, m["sel"], self.actions) - m["mu"]) / m["sd"]
        d = ((x[:, None, :] - m["x"][None, :, :]) ** 2).sum(-1)
        kk = min(self.k, m["x"].shape[0])
        idx = np.argpartition(d, kk - 1, axis=1)[:, :kk]
        return m["y"][idx].mean(1)

    def predict(self, rows):
        """Returns (point estimate, uncertainty) as arrays over `rows`.

        The point estimate is the member median, not the mean: the same reason
        the interval is a quantile width.
        """
        p = np.stack([self._member_predict(m, rows) for m in self.members])
        return np.median(p, 0), (np.quantile(p, 0.95, 0) - np.quantile(p, 0.05, 0))


def main():
    ap = argparse.ArgumentParser(description="report the splits and the "
                                             "ensemble's held-out error")
    ap.add_argument("root")
    ap.add_argument("jobs_csv")
    args = ap.parse_args()

    rows = load_rows(args.root, args.jobs_csv)
    names = sorted(rows[0]["x"])
    actions = sorted({r["rec"]["action"] for r in rows})
    sp = splits(rows)

    print(f"{len(rows)} branches, {len(set(r['point'] for r in rows))} design "
          f"points, actions {', '.join(actions)}")
    print("\nSPLITS (by design point, then by seed)")
    for k in ("train", "val", "cal", "test_id", "test_param", "test_mech"):
        pts = len({r["point"] for r in sp[k]})
        sds = len({r["rec"]["seed"] for r in sp[k]})
        print(f"  {k:11s} n={len(sp[k]):5d}  design points {pts:3d}  seeds {sds:3d}")
    if not sp["test_mech"]:
        print("  test_mech is EMPTY: this scenario set holds one mechanism, so")
        print("  mechanism shift is not measurable and must not be claimed.")

    if not sp["train"]:
        sys.exit("no training rows; splits are degenerate")
    ens = Ensemble(names, actions).fit(sp["train"])
    print(f"\nENSEMBLE B={ENSEMBLE_B}, k={KNN_K}, features {FEATURE_FRACTION:.0%}")
    for k in ("val", "cal", "test_id", "test_param", "test_mech"):
        if not sp[k]:
            continue
        yhat, unc = ens.predict(sp[k])
        y = np.array([r["y"] for r in sp[k]])
        const = np.median([r["y"] for r in sp["train"]])
        print(f"  {k:11s} MAE {np.abs(yhat - y).mean():.4f}   "
              f"constant {np.abs(const - y).mean():.4f}   "
              f"mean U {unc.mean():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
