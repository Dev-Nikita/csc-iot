#!/usr/bin/env python3
"""Generate the paper's result tables from recorded runs.

No number in the manuscript is typed by hand. Each table carries the run it came
from, the stack it ran on and the protocol revision, so a table in the paper can
always be traced to the evidence that produced it.
"""
import argparse
import csv
import glob
import itertools
import json
import os
import subprocess
import sys

import branches
from band_sensitivity import boot_ci, dispersion, median, quantile


def provenance(root):
    m = branches.read_matrix(root)
    d = sorted(glob.glob(os.path.join(root, "[as]*-*")))
    commit = stack = "?"
    for b in d:
        p = os.path.join(b, "anchor.json")
        if os.path.exists(p):
            a = json.load(open(p))
            commit, stack = a.get("git_commit", "?"), a.get("runtime_stack_id", "?")
            break
    # The revision label was maintained by hand until amendment 0.18 derived it
    # from the deployment, so for runs started on or after 2026-09-25 the label
    # is stale. The recorded start date is what bounds the revision against the
    # commit history, so every table carries it beside the label.
    return {"experiment": m.get("experiment", os.path.basename(root)),
            "stack": stack, "commit": commit,
            "started": (m.get("started_utc") or "?")[:10],
            "branches": len([x for x in d if os.path.isdir(x)])}


def load_rows(jobs_csv):
    return list(csv.DictReader(open(jobs_csv)))


def bands_table(rows, gate=3.0):
    cells = {}
    for r in rows:
        cells.setdefault((r.get("scenario", "s00"), r["anchor"], r["action"]),
                         []).append(float(r["J_obs"]))
    eta = {k: dispersion(v) for k, v in cells.items()}
    pooled = quantile([abs(a - b) for v in cells.values()
                       for a, b in itertools.combinations(v, 2)], 0.95)
    worst = max(eta.values())
    actions = sorted({c for _, _, c in cells} - {"NO_OP"})
    counts = {"pooled": 0, "worst": 0, "local": 0, "ci": 0, "all": 0}
    total = 0
    for sc, a in sorted({(s, x) for s, x, _ in cells}):
        base = cells.get((sc, a, "NO_OP"))
        if not base:
            continue
        for act in actions:
            v = cells.get((sc, a, act))
            if not v:
                continue
            total += 1
            delta = abs(median(base) - median(v))
            local = max(eta[(sc, a, "NO_OP")], eta[(sc, a, act)])
            lo, hi = boot_ci(base, v, n=2000)
            ok = {"pooled": pooled and delta / pooled >= gate,
                  "worst": worst and delta / worst >= gate,
                  "local": (delta / local >= gate) if local else True,
                  "ci": lo > 0 or hi < 0}
            for k, good in ok.items():
                counts[k] += bool(good)
            counts["all"] += all(ok.values())
    return pooled, worst, counts, total


def fmt(x, nd=4):
    return f"{x:.{nd}f}"


def write(path, text):
    with open(path, "w") as fh:
        fh.write(text)
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--single-scenario-root", required=True,
                    help="the audited single-scenario run (replay resolution)")
    ap.add_argument("--factored-root", required=True,
                    help="the scenario-factored matrix (prediction, generalisation)")
    ap.add_argument("--out-dir", default="paper/generated_tables")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    merged = {}
    for tag, root in (("single", args.single_scenario_root),
                      ("factored", args.factored_root)):
        prov = provenance(root)
        jobs = os.path.join(root, "jobs.csv")
        if not os.path.exists(jobs):
            sys.exit(f"{jobs} not found; run analysis/jobs.py with --out first")
        rows = load_rows(jobs)
        pooled, worst, counts, total = bands_table(rows)
        scenarios = len({r.get("scenario", "s00") for r in rows})
        caption = ("Replay dispersion and action resolvability on the audited "
                   f"single-scenario run (\\texttt{{{prov['experiment']}}}, "
                   f"{prov['branches']} branches, stack "
                   f"\\texttt{{{prov['stack'][:8]}}}, {prov['commit']}, run {prov['started']}). "
                   "The preregistered band is the pooled one; the others are "
                   "reported because a band that holds on average and fails in "
                   "one cell is not a band."
                   if tag == "single" else
                   "Action resolvability on the scenario-factored matrix "
                   f"(\\texttt{{{prov['experiment']}}}, {prov['branches']} "
                   f"branches, {scenarios} scenarios, stack "
                   f"\\texttt{{{prov['stack'][:8]}}}, {prov['commit']}, run {prov['started']}).")
        write(os.path.join(args.out_dir, f"table_bands_{tag}.tex"), f"""\
\\begin{{table}}[!t]
\\centering
\\caption{{{caption}}}
\\label{{tab:bands-{tag}}}
\\begin{{tabular}}{{lr}}
\\toprule
Quantity & Value \\\\
\\midrule
Branches & {prov['branches']} \\\\
Scenarios (distinct fault settings) & {scenarios} \\\\
$\\eta_J$, pooled (preregistered) & {fmt(pooled)} \\\\
$\\eta_J$, worst cell & {fmt(worst)} \\\\
\\midrule
Contrasts resolvable, pooled band & {counts['pooled']}/{total} \\\\
\\quad worst-cell band & {counts['worst']}/{total} \\\\
\\quad contrast-local band & {counts['local']}/{total} \\\\
\\quad bootstrap CI excludes zero & {counts['ci']}/{total} \\\\
\\quad \\textbf{{surviving all four}} & \\textbf{{{counts['all']}/{total}}} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
""")
        merged[tag] = dict(prov=prov, pooled=pooled, worst=worst,
                           counts=counts, total=total, scenarios=scenarios)

    if {"single", "factored"} <= set(merged):
        rows = []
        for tag in ("single", "factored"):
            m = merged[tag]
            rows.append(
                "\\texttt{%s} & %d & %d & %s & %s & %d/%d & \\textbf{%d/%d} \\\\"
                % (m["prov"]["experiment"], m["prov"]["branches"],
                   m["scenarios"], fmt(m["pooled"]), fmt(m["worst"]),
                   m["counts"]["pooled"], m["total"],
                   m["counts"]["all"], m["total"]))
        write(os.path.join(args.out_dir, "table_bands_merged.tex"),
              """\\begin{table}[!t]
\\caption{Replay Dispersion and Action Resolvability on the Two Matrices Whose
Dispersion Was Measured. The Preregistered Band Is the Pooled One; the Final
Column Is the Set Surviving All Four Bands.}
\\label{tab:bands}
\\centering
\\scriptsize
\\setlength{\\tabcolsep}{2.6pt}
\\begin{tabular}{@{}lrrrrrr@{}}
\\toprule
Run & Br. & Sc. & $\\eta_J$ & $\\eta_J$ & Resolv. & Robust\\\\
    &     &     & pooled & worst & pooled & all four\\\\
\\midrule
%s
\\bottomrule
\\end{tabular}
\\end{table}
""" % "\n".join(rows))

    # Prediction table. The harness writes its figures as JSON and this reads
    # that: parsing its prose broke on the first line that ended in a word.
    summary_path = os.path.join(args.out_dir, "prediction_summary.json")
    run = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "leakage_tests.py"),
         args.factored_root, os.path.join(args.factored_root, "jobs.csv"),
         "--json", summary_path], capture_output=True, text=True)
    if not os.path.exists(summary_path):
        sys.exit("the leakage harness wrote no summary:\n" + run.stdout + run.stderr)
    vals = json.load(open(summary_path))
    if not (vals.get("time_only_pass") and vals.get("permutation_pass")):
        sys.exit("REFUSED: the leakage controls did not pass on this matrix, so a "
                 "prediction table from it would be reporting a confound.")
    regimes = [(n, v["n"], fmt(v["knn"]), fmt(v["constant"]))
               for n, v in sorted((vals.get("regimes") or {}).items())]
    prov = provenance(args.factored_root)
    rl = "\n".join(f"\\quad {n} ($n={c}$) & {k} & --- & --- & {m} \\\\"
                   for n, c, k, m in regimes)
    write(os.path.join(args.out_dir, "table_prediction.tex"), f"""\
\\begin{{table}}[!t]
\\centering
\\caption{{Action-conditioned prediction of $J_{{\\mathrm{{obs}}}}$ from
decision-time telemetry, with folds held out by fault design point
(\\texttt{{{prov['experiment']}}}, {prov['branches']} branches,
{prov['commit']}, run {prov['started']}). The time-only and permutation rows are leakage controls:
the first asks how much of the skill is the clock, the second whether the
skill comes from the telemetry at all.}}
\\label{{tab:prediction}}
\\footnotesize
\\setlength{{\\tabcolsep}}{{3pt}}
\\begin{{tabular}}{{lrrrr}}
\\toprule
Predictor & MAE & Time-only & Permuted & Constant \\\\
\\midrule
Telemetry, $k$NN & \\textbf{{{fmt(vals['knn'])}}} & {fmt(vals['time_only'])}
  & {fmt(vals['permuted'])} & {fmt(vals['constant'])} \\\\
Telemetry, ridge (linear) & {fmt(vals.get('ridge', float('nan')))} & --- & --- & --- \\\\
{rl}
\\bottomrule
\\end{{tabular}}
\\end{{table}}
""")
    # Spanning-regime holdout: whether skill where the fault has not yet happened
    # transfers, or is knowledge of the onset distribution.
    span_path = os.path.join(args.out_dir, "spanning_summary.json")
    run = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "regime_holdout.py"),
         args.factored_root, os.path.join(args.factored_root, "jobs.csv"),
         "--json", span_path], capture_output=True, text=True)
    if not os.path.exists(span_path):
        sys.exit("the regime holdout wrote no summary:\n" + run.stdout + run.stderr)
    sp = json.load(open(span_path))
    write(os.path.join(args.out_dir, "table_spanning.tex"), f"""\
\\begin{{table}}[!t]
\\centering
\\caption{{Spanning-regime holdout. In this regime the fault arrives inside the
horizon and nothing in the state at the decision instant carries it. The strict
row trains on no branch that spans a fault and on no branch sharing the test
branch's fault setting; it is the leakage-resistant estimate the corresponding
claim is stated against, and the other rows show how much the looser training
sets add.
($n={sp['n_test']}$ branches, MAE in $J_{{\\mathrm{{obs}}}}$ units.)}}
\\label{{tab:spanning}}
\\begin{{tabular}}{{lr}}
\\toprule
Training set & MAE \\\\
\\midrule
Held out by fault design point (spanning allowed) & {fmt(sp['design_point_holdout'])} \\\\
No spanning branch in training & {fmt(sp['regime_holdout'])} \\\\
\\textbf{{No spanning branch, fault setting unseen}} & \\textbf{{{fmt(sp['strict_holdout'])}}} \\\\
\\midrule
Predict the training mean & {fmt(sp['constant'])} \\\\
Standard deviation of $J_{{\\mathrm{{obs}}}}$ here & {fmt(sp['spread'])} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
