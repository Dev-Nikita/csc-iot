#!/usr/bin/env python3
"""Emit paper/generated_tables/*.tex from summary.csv.

These files carry a do-not-edit banner because a hand-edited generated table is
the single easiest way to get an unreproducible number into a manuscript.
"""
import pandas as pd
from common import SUMMARY, TABLES, CONTROLLER_LABELS, CONTROLLERS, ABLATIONS

BANNER = ("% GENERATED FILE -- do not edit. Produced by analysis/tables.py.\n"
          "% Source: data/processed/summary.csv at commit {commit}.\n")

MAIN_COLS = [("pfr", r"PFR $\uparrow$"), ("wir", r"WIR $\downarrow$"),
             ("regret", r"Regret $\downarrow$"), ("availability", r"Avail. $\uparrow$"),
             ("p99_latency_ms", r"p99 $\downarrow$"),
             ("intervention_cost", r"Cost $\downarrow$")]


def fmt(row) -> str:
    """Mean with a bootstrap interval, at a precision the data supports."""
    if row is None or row.empty:
        return "--"
    r = row.iloc[0]
    p = 3 if abs(r["mean"]) < 10 else 1
    return f"{r['mean']:.{p}f}\\,\\tiny[{r['ci_lo']:.{p}f},{r['ci_hi']:.{p}f}]"


def render(df, rows, labels, cols, caption, label, commit) -> str:
    spec = "@{}l" + "c" * len(cols) + "@{}"
    out = [BANNER.format(commit=commit),
           r"\begin{table}[!t]", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
           r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{3.5pt}",
           f"\\begin{{tabular}}{{{spec}}}", r"\toprule",
           " & ".join(["Controller"] + [h for _, h in cols]) + r"\\", r"\midrule"]
    for key in rows:
        cells = [labels.get(key, key)]
        for metric, _ in cols:
            sel = df[(df.controller == key) & (df.metric == metric)]
            cells.append(fmt(sel))
        out.append(" & ".join(cells) + r"\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(out)


def main() -> None:
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    df = pd.read_csv(SUMMARY)
    TABLES.mkdir(parents=True, exist_ok=True)

    (TABLES / "table_main.tex").write_text(render(
        df, CONTROLLERS, CONTROLLER_LABELS, MAIN_COLS,
        "Main Results Across Scenarios and Paired Seeds", "tab:main", commit))

    (TABLES / "table_ablation.tex").write_text(render(
        df, ABLATIONS,
        {"A1_no_gate": "A1 no uncertainty gate", "A2_no_mni": "A2 no minimum intervention",
         "A3_no_causal": "A3 no causal layer", "full_csc": r"\textbf{Full CSC}"},
        [("pfr", r"PFR $\uparrow$"), ("wir", r"WIR $\downarrow$"),
         ("intervention_cost", r"Cost $\downarrow$"), ("cra", r"CRA $\uparrow$")],
        "Ablations", "tab:ablation", commit))
    print(f"wrote {TABLES}/table_main.tex and table_ablation.tex")


if __name__ == "__main__":
    main()
