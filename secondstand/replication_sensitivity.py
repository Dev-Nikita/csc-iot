#!/usr/bin/env python3
"""Replication-depth sensitivity on RCAEval RE1.

The earlier A/B comparison changed both the number of repetitions and the
decision rule.  This analysis holds the unit and rule fixed: for every
configuration and method pair, enumerate every subset of n=2,3,4,5 paired
repetitions and apply the same percentile paired-bootstrap interval to the mean
difference.  The interval-exclusion rate is descriptive, not a family of
hypothesis-test discoveries.

We also report sign agreement with the full-five estimate and the exact
two-sided sign-flip p-value.  With at most five pairs the latter cannot reach
0.05 (its best possible value at n=5 is 2/2^5 = 0.0625), so it is a power
diagnostic rather than a replacement for the interval analysis.
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


METHODS = ["baro", "nsigma"]
KEY = ["dataset", "service", "fault"]
BOOTSTRAPS = 4000
SEED = 17


def reciprocal_rank(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0.0
    return 1.0 / value


def paired_bootstrap_interval(values, rng):
    n = len(values)
    indices = rng.integers(0, n, size=(BOOTSTRAPS, n))
    means = values[indices].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(lo), float(hi)


def exact_signflip_p(values):
    observed = abs(values.mean())
    signs = np.array(list(itertools.product((-1.0, 1.0), repeat=len(values))))
    null = abs((signs * values).mean(axis=1))
    return float((null >= observed - 1e-15).mean())


def main():
    source = Path(__file__).with_name("results.jsonl")
    rows = [json.loads(line) for line in source.open(encoding="utf-8")]
    frame = pd.DataFrame(rows)
    for method in METHODS:
        frame[method + "_rr"] = frame[method].apply(reciprocal_rank)

    rng = np.random.default_rng(SEED)
    records = []
    for config, group in frame.groupby(KEY, sort=True):
        if len(group) != 5:
            raise ValueError(f"{config}: expected five repetitions, found {len(group)}")
        for left, right in itertools.combinations(METHODS, 2):
            values = (group[left + "_rr"] - group[right + "_rr"]).to_numpy()
            full_mean = values.mean()
            full_sign = np.sign(full_mean)
            pair = f"{left} vs {right}"
            for n in range(2, 6):
                for subset in itertools.combinations(range(5), n):
                    sample = values[list(subset)]
                    lo, hi = paired_bootstrap_interval(sample, rng)
                    sign = np.sign(sample.mean())
                    records.append({
                        "pair": pair,
                        "n": n,
                        "resolved": lo > 0 or hi < 0,
                        "sign_agrees": sign == full_sign,
                        "abs_error_from_full": abs(sample.mean() - full_mean),
                        "ci_width": hi - lo,
                        "exact_p": exact_signflip_p(sample),
                    })

    out = pd.DataFrame(records)
    print("Replication-depth sensitivity: same paired-bootstrap rule at every n")
    print(f"bootstrap resamples={BOOTSTRAPS} seed={SEED}")
    print("Rates pool enumerated repetition subsets; they are descriptive, not FWER-controlled discoveries.\n")
    for n, group in out.groupby("n"):
        print(
            f"n={n}: subsets={len(group)}  CI excludes zero={group.resolved.mean():.4f} "
            f"({group.resolved.sum()}/{len(group)})  "
            f"sign agrees with full-five={group.sign_agrees.mean():.4f}  "
            f"median |subset-full|={group.abs_error_from_full.median():.4f}  "
            f"p90 |subset-full|={group.abs_error_from_full.quantile(.9):.4f}  "
            f"median CI width={group.ci_width.median():.4f}  "
            f"exact sign-flip p<0.05={(group.exact_p < 0.05).sum()}"
        )
        for pair, pair_group in group.groupby("pair"):
            print(
                f"    {pair:30s} CI excludes zero={pair_group.resolved.mean():.4f} "
                f"sign agreement={pair_group.sign_agrees.mean():.4f} "
                f"median |subset-full|={pair_group.abs_error_from_full.median():.4f}"
            )
    print("\nExact sign-flip minimum attainable two-sided p-values:")
    for n in range(2, 6):
        print(f"n={n}: {2/(2**n):.4f}")


if __name__ == "__main__":
    main()
