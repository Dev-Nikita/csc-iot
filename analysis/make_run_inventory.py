#!/usr/bin/env python3
"""Emit the supplement's run inventory. Nothing in it is typed by hand.

Two sources, kept apart because they are not equally strong:

  * every `matrix.json` reachable from this checkout -- authoritative, since it
    is the manifest the runner wrote at the start of the run, and the branch
    count is obtained by counting branch directories, not by reading a field;
  * the stack table in RESULTS.md -- for the three headline matrices, whose raw
    branch data is held on the analysis host and is not in this repository.

A row's `source` column says which of the two it came from. The script refuses to
emit a table if it cannot find the headline runs, rather than emitting a
plausible-looking subset that silently omits the runs the paper reports.
"""
import glob
import json
import os
import re
import sys

HEADLINE = re.compile(r"\|\s*`([0-9a-f]{8,})`\s*\|\s*`([\w.-]+)`\s*\((\d+)\s+branches")


def from_manifests(root="."):
    rows = []
    for m in sorted(glob.glob(os.path.join(root, "data/raw/*/*/matrix.json"))):
        d = json.load(open(m))
        base = os.path.dirname(m)
        n = len([x for x in glob.glob(os.path.join(base, "[as]*-*"))
                 if os.path.isdir(x)])
        rows.append({"run": d.get("experiment", os.path.basename(base)),
                     "started": (d.get("started_utc") or "?")[:10],
                     "branches": n,
                     "stack": (d.get("runtime_stack_id") or "?")[:8],
                     "source": "manifest"})
    return rows


def from_results(path="RESULTS.md"):
    rows = []
    for stack, run, n in HEADLINE.findall(open(path, encoding="utf-8").read()):
        rows.append({"run": run, "started": "---", "branches": int(n),
                     "stack": stack[:8], "source": "RESULTS.md"})
    return rows


def main():
    man, res = from_manifests(), from_results()
    if not res:
        sys.exit("REFUSED: no headline run found in RESULTS.md. Emitting the "
                 "manifest rows alone would omit the runs the paper reports.")
    seen = {r["run"] for r in man}
    rows = man + [r for r in res if r["run"] not in seen]
    rows.sort(key=lambda r: (r["source"] != "RESULTS.md", r["started"], r["run"]))
    head = sum(r["branches"] for r in rows if r["source"] == "RESULTS.md")
    total = sum(r["branches"] for r in rows)
    body = "\n".join(
        "\\texttt{%s} & %s & \\texttt{%s} & %d & %s \\\\" %
        (r["run"].replace("_", "\\_"), r["started"], r["stack"], r["branches"],
         "RESULTS.md" if r["source"] == "RESULTS.md" else "manifest")
        for r in rows)
    out = """\\begin{table}[!t]
\\caption{Every Matrix Run in This Work. The Three Rows Sourced From
\\texttt{RESULTS.md} Are the Matrices the Main Manuscript Reports; Their Branch
Data Is Held on the Analysis Host. The Remaining Rows Are Pilots, Calibration
Runs and Superseded Matrices Whose Manifests Are in the Checkout.}
\\label{tab:runs}
\\centering
\\scriptsize
\\setlength{\\tabcolsep}{3pt}
\\begin{tabular}{@{}llrrl@{}}
\\toprule
Run & Started & Stack & Branches & Source\\\\
\\midrule
%s
\\midrule
\\multicolumn{3}{@{}l}{Reported in the main manuscript} & %d & \\\\
\\multicolumn{3}{@{}l}{All runs listed here} & %d & \\\\
\\bottomrule
\\end{tabular}
\\end{table}
""" % (body, head, total)
    dest = "paper/generated_tables/table_runs.tex"
    open(dest, "w").write(out)
    print("wrote %s: %d rows, %d reported branches, %d in total"
          % (dest, len(rows), head, total))


if __name__ == "__main__":
    main()
