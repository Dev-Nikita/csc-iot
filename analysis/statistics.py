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
PRIMARY = ["pfr", "wir", "regret_eta", "availability", "p99_latency_ms",
           "intervention_cost", "cra_eta"]
REFERENCE = "B6_csc"


def boot_ci(x: np.ndarray, n=BOOTSTRAP_RESAMPLES):
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    means = x[idx].mean(axis=1)
    return float(np.percentile(means, 100 * ALPHA / 2)), float(np.percentile(means, 100 * (1 - ALPHA / 2)))


def rank_biserial_paired(a: np.ndarray, b: np.ndarray) -> float:
    """Matched-pairs rank-biserial correlation; positive means a > b."""
    d = a - b
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(d), method="average")
    positive = ranks[d > 0].sum()
    negative = ranks[d < 0].sum()
    return float((positive - negative) / (positive + negative))


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    m = len(pvals)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adjusted[i] = min(1.0, running)
    return adjusted.tolist()


def noninferiority(a: np.ndarray, b: np.ndarray, margin: float) -> dict:
    """One-sided paired non-inferiority of a against b at the declared margin.

    H0: mean(a - b) <= -margin  (a is inferior).  Rejecting H0 is the only
    thing that licenses the sentence "without a practically meaningful loss".
    A non-significant two-sided difference licenses nothing: it is equally
    consistent with an underpowered comparison.
    """
    d = a - b
    idx = RNG.integers(0, len(d), size=(BOOTSTRAP_RESAMPLES, len(d)))
    boot = d[idx].mean(axis=1)
    lower90 = float(np.percentile(boot, 5))          # one-sided 95% lower bound
    t_stat, p_two = stats.ttest_1samp(d + margin, 0.0)
    p_one = p_two / 2 if t_stat > 0 else 1 - p_two / 2
    return {"mean_diff": float(d.mean()), "lower_90ci": lower90,
            "margin": -margin, "p_noninferiority": float(p_one),
            "non_inferior": bool(lower90 > -margin)}


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
            if np.allclose(a, b, rtol=0, atol=0):
                stat, p = 0.0, 1.0
            else:
                stat, p = stats.wilcoxon(a, b)
            tests.append({"metric": metric, "reference": REFERENCE, "other": other,
                          "n_pairs": len(paired), "wilcoxon_stat": stat, "p_raw": p,
                          "rank_biserial_paired": rank_biserial_paired(a, b),
                          "direction": "higher_better" if metric in HIGHER_BETTER
                                       else "lower_better"})
            pvals.append(p)

    if tests:
        for t, p in zip(tests, holm(pvals)):
            t["p_holm"] = p
    pd.DataFrame(tests).to_csv(TESTS, index=False)

    # --- H3: availability non-inferiority of MNI against risk-argmin ---------
    import yaml
    from common import ROOT
    margin = yaml.safe_load(
        open(ROOT / "experiments" / "configs" / "objective.yaml")
    )["availability_noninferiority_margin"]
    piv = df.pivot_table(index=["scenario", "seed"], columns="controller",
                         values="availability")
    if {"B6_csc", "A2_no_mni"} <= set(piv.columns):
        paired = piv[["B6_csc", "A2_no_mni"]].dropna()
        res = noninferiority(paired["B6_csc"].to_numpy(),
                             paired["A2_no_mni"].to_numpy(), margin)
        res["n_pairs"] = len(paired)
        pd.DataFrame([res]).to_csv(TESTS.with_name("h3_noninferiority.csv"),
                                   index=False)
        print("H3 non-inferiority:", res)
    else:
        print("H3 skipped: need both B6_csc and A2_no_mni in results")

    print(f"wrote {SUMMARY} and {TESTS} ({len(tests)} primary comparisons)")


if __name__ == "__main__":
    main()
