#!/usr/bin/env python3
"""Paired comparisons with bootstrap intervals, effect sizes and Holm correction.

p-values are never reported alone.
"""
import itertools
import numpy as np
import pandas as pd
from scipy import stats
from common import (RESULTS_LONG, SUMMARY, TESTS, CONTROLLERS,
                    BOOTSTRAP_RESAMPLES, ALPHA, HIGHER_BETTER, LOWER_BETTER,
                    require_results)

RNG = np.random.default_rng(20260825)
PRIMARY = ["pfr", "wir", "regret", "availability", "p99_latency_ms",
           "intervention_cost", "cra"]
REFERENCE = "B6_csc"


def boot_ci(x: np.ndarray, n=BOOTSTRAP_RESAMPLES):
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    means = x[idx].mean(axis=1)
    return float(np.percentile(means, 100 * ALPHA / 2)), float(np.percentile(means, 100 * (1 - ALPHA / 2)))


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    gt = sum((x > y) for x in a for y in b)
    lt = sum((x < y) for x in a for y in b)
    return (gt - lt) / (len(a) * len(b))


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    m = len(pvals)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adjusted[i] = min(1.0, running)
    return adjusted.tolist()


def main() -> None:
    require_results()
    df = pd.read_csv(RESULTS_LONG)

    summary = []
    for (controller, metric), g in (
        df.melt(id_vars=["controller", "seed", "scenario"],
                value_vars=[m for m in PRIMARY if m in df.columns],
                var_name="metric", value_name="value")
          .groupby(["controller", "metric"])):
        x = g["value"].dropna().to_numpy()
        lo, hi = boot_ci(x)
        summary.append({"controller": controller, "metric": metric,
                        "n": len(x), "mean": x.mean(), "ci_lo": lo, "ci_hi": hi})
    pd.DataFrame(summary).to_csv(SUMMARY, index=False)

    tests, pvals = [], []
    for metric in [m for m in PRIMARY if m in df.columns]:
        pivot = df.pivot_table(index=["scenario", "seed"], columns="controller",
                               values=metric)
        for other in [c for c in CONTROLLERS if c != REFERENCE and c in pivot]:
            paired = pivot[[REFERENCE, other]].dropna()
            if len(paired) < 10:
                continue
            a = paired[REFERENCE].to_numpy()
            b = paired[other].to_numpy()
            stat, p = stats.wilcoxon(a, b)
            tests.append({"metric": metric, "reference": REFERENCE, "other": other,
                          "n_pairs": len(paired), "wilcoxon_stat": stat, "p_raw": p,
                          "cliffs_delta": cliffs_delta(a, b),
                          "direction": "higher_better" if metric in HIGHER_BETTER
                                       else "lower_better"})
            pvals.append(p)

    if tests:
        for t, p in zip(tests, holm(pvals)):
            t["p_holm"] = p
    pd.DataFrame(tests).to_csv(TESTS, index=False)
    print(f"wrote {SUMMARY} and {TESTS} ({len(tests)} primary comparisons)")


if __name__ == "__main__":
    main()
