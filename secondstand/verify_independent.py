#!/usr/bin/env python3
"""Standard-library-only verification of the headline RCAEval results.

Unlike analyse2.py, criterion B enumerates all 5^5 paired bootstrap resamples for
each configuration and pair.  The reported count therefore has no Monte-Carlo
seed or resampling error.
"""
import itertools
import json
import math
from pathlib import Path


METHODS = ("baro", "nsigma")
PAIRS = tuple(itertools.combinations(METHODS, 2))


def rr(value):
    return 0.0 if value is None else 1.0 / value


def quantile(values, probability):
    values = sorted(values)
    position = (len(values) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return values[low]
    return (values[low] * (high - position)
            + values[high] * (position - low))


def main():
    source = Path(__file__).with_name("results.jsonl")
    rows = [json.loads(line) for line in source.open(encoding="utf-8")]
    configs = {}
    for row in rows:
        key = (row["dataset"], row["service"], row["fault"])
        configs.setdefault(key, []).append(row)
    if len(rows) != 375 or len(configs) != 75:
        raise SystemExit(f"REFUSED: expected 375 rows/75 configs, found "
                         f"{len(rows)}/{len(configs)}")
    if any(len(group) != 5 for group in configs.values()):
        raise SystemExit("REFUSED: every configuration must have five repetitions")

    within = []
    for group in configs.values():
        for method in METHODS:
            values = [rr(row[method]) for row in group]
            within.extend(abs(a - b) for a, b in itertools.combinations(values, 2))
    eta = quantile(within, 0.95)

    criterion_a = {pair: 0 for pair in PAIRS}
    for row in rows:
        for left, right in PAIRS:
            criterion_a[(left, right)] += abs(rr(row[left]) - rr(row[right])) > eta

    criterion_b = {pair: 0 for pair in PAIRS}
    for group in configs.values():
        for left, right in PAIRS:
            differences = [rr(row[left]) - rr(row[right]) for row in group]
            means = [sum(differences[i] for i in indices) / 5
                     for indices in itertools.product(range(5), repeat=5)]
            low, high = quantile(means, 0.025), quantile(means, 0.975)
            criterion_b[(left, right)] += low > 0 or high < 0

    print(f"rows={len(rows)} configurations={len(configs)} "
          f"within-pairs={len(within)}")
    print(f"eta_q95={eta:.10g}")
    print("criterion_A=" + str(sum(criterion_a.values())) + f"/{len(rows)*len(PAIRS)} "
          + " ".join(f"{a}-{b}:{criterion_a[(a,b)]}/375" for a, b in PAIRS))
    print("criterion_B_exact=" + str(sum(criterion_b.values())) + f"/{len(configs)*len(PAIRS)} "
          + " ".join(f"{a}-{b}:{criterion_b[(a,b)]}/75" for a, b in PAIRS))

    for n in range(2, 6):
        agreements, errors = [], []
        for group in configs.values():
            for left, right in PAIRS:
                values = [rr(row[left]) - rr(row[right]) for row in group]
                full = sum(values) / 5
                full_sign = (full > 0) - (full < 0)
                for indices in itertools.combinations(range(5), n):
                    subset = sum(values[i] for i in indices) / n
                    agreements.append(((subset > 0) - (subset < 0)) == full_sign)
                    errors.append(abs(subset - full))
        print(f"n={n} subsets={len(agreements)} "
              f"sign_agreement={sum(agreements)/len(agreements):.10g} "
              f"median_error={quantile(errors, .5):.10g} "
              f"p90_error={quantile(errors, .9):.10g}")

    expected_a = {("baro", "nsigma"): 8}
    expected_b = {("baro", "nsigma"): 43}
    if criterion_a != expected_a or criterion_b != expected_b:
        raise SystemExit("FAILED: independent counts differ from the manuscript")
    print("INDEPENDENT RCAEval VERIFICATION OK")


if __name__ == "__main__":
    main()
