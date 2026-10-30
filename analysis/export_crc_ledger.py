#!/usr/bin/env python3
"""Export the complete calibration evidence needed to audit CRC arithmetic."""
import argparse
import csv
import os

import predictor
import crc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("jobs_csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--delta", type=float, default=0.10)
    ap.add_argument("--u-max", type=float, default=0.15)
    args = ap.parse_args()

    rows = predictor.load_rows(args.root, args.jobs_csv)
    jobs = list(csv.DictReader(open(args.jobs_csv, newline="")))
    splits = predictor.splits(rows)
    cal = splits["cal"]
    names = sorted(rows[0]["x"])
    actions = sorted({r["rec"]["action"] for r in rows})
    ensemble = predictor.Ensemble(names, actions).fit(splits["train"])
    risk_values, uncertainty_values = ensemble.predict(cal)
    theta, theta_n = crc.failure_threshold(cal, jobs)
    y_ms = {r["branch"]: float(r["Y_ms"]) for r in jobs}

    fields = ["branch", "seed", "fault_type", "fault_onset",
              "fault_severity", "workload_level", "anchor", "action",
              "risk", "uncertainty", "Y_ms", "failed", "theta",
              "theta_n", "u_max", "delta", "split"]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row, risk, unc in zip(cal, risk_values, uncertainty_values):
            rec = row["rec"]
            branch = row["name"]
            observed = y_ms[branch]
            writer.writerow({
                "branch": branch, "seed": rec["seed"],
                "fault_type": rec["fault_type"],
                "fault_onset": rec["fault_onset"],
                "fault_severity": rec["fault_severity"],
                "workload_level": rec["workload_level"],
                "anchor": rec["anchor"], "action": rec["action"],
                "risk": f"{float(risk):.17g}",
                "uncertainty": f"{float(unc):.17g}",
                "Y_ms": f"{observed:.17g}",
                "failed": int(observed > theta),
                "theta": f"{theta:.17g}", "theta_n": theta_n,
                "u_max": f"{args.u_max:.17g}",
                "delta": f"{args.delta:.17g}", "split": "calibration",
            })
    print(f"wrote {len(cal)} calibration branches to {args.out}")


if __name__ == "__main__":
    main()
