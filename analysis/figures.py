#!/usr/bin/env python3
"""Emit Figs. 3 and 4 as vector PDFs.

Figures 1 and 2 are hand-authored TikZ and are not produced here. Everything
generated is grayscale-legible: series are separated by hatch and marker, not
by colour alone, because IEEE prints in grayscale.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from common import RESULTS_LONG, SUMMARY, FIGURES, CONTROLLERS, CONTROLLER_LABELS

plt.rcParams.update({
    "font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7,
    "legend.fontsize": 6, "xtick.labelsize": 6, "ytick.labelsize": 6,
    "figure.dpi": 300, "savefig.bbox": "tight", "pdf.fonttype": 42,
    "axes.grid": True, "grid.linewidth": 0.3, "grid.alpha": 0.4,
})
COL_W, TWO_COL_W = 3.5, 7.16  # inches, IEEE journal
HATCH = ["", "///", "...", "xxx", "\\\\\\", ""]
GRAY = [0.75, 0.68, 0.60, 0.52, 0.44, 0.15]


def fig_timeline(out):
    """Cascading failure: observed vs replayed no-action counterfactual."""
    df = pd.read_csv(RESULTS_LONG)
    raise SystemExit("fig_timeline needs the F7 decision trace; implement at phase 20")


def fig_main(out):
    s = pd.read_csv(SUMMARY)
    panels = [("pfr", "Prevented failure ratio"), ("wir", "Wrong intervention rate"),
              ("p99_latency_ms", "p99 latency (ms)"), ("intervention_cost", "Mean intervention cost")]
    fig, axes = plt.subplots(2, 2, figsize=(TWO_COL_W, 3.6))
    for ax, (metric, title) in zip(axes.ravel(), panels):
        sub = s[s.metric == metric].set_index("controller").reindex(CONTROLLERS)
        err = [sub["mean"] - sub["ci_lo"], sub["ci_hi"] - sub["mean"]]
        bars = ax.bar(range(len(sub)), sub["mean"], yerr=err, capsize=1.6,
                      color=[str(g) for g in GRAY], edgecolor="black", linewidth=0.5)
        for b, h in zip(bars, HATCH):
            b.set_hatch(h)
        ax.set_xticks(range(len(sub)))
        ax.set_xticklabels([CONTROLLER_LABELS[c].replace(r"\textbf{", "").replace("}", "")
                            for c in CONTROLLERS], rotation=30, ha="right")
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig_main(FIGURES / "fig4_main.pdf")
    fig_timeline(FIGURES / "fig3_timeline.pdf")


if __name__ == "__main__":
    main()
