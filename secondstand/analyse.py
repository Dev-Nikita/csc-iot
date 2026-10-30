"""Resolvability of method comparisons on RCAEval RE1.

The band is the paper's own definition, carried over unchanged: the pooled
Q0.95 of within-configuration pairwise |differences| of the SAME method across
repetitions of the SAME fault-service pair. A contrast between two methods at a
configuration counts as resolvable only if it exceeds that band.
"""
import json, itertools, sys
import numpy as np, pandas as pd

rows = [json.loads(l) for l in open("/tmp/claude-0/probe/results.jsonl")]
df = pd.DataFrame(rows)
METHODS = ["baro", "nsigma", "e_diagnosis"]
for m in METHODS:
    df[m + "_rr"] = df[m].apply(lambda p: 0.0 if p is None or (isinstance(p,float) and np.isnan(p)) else 1.0/p)

key = ["dataset", "service", "fault"]
print(f"cases analysed: {len(df)}   configurations: {df.groupby(key).ngroups}")
print()

# --- the band: within-configuration, within-method, pairwise |difference|
diffs = []
for _, g in df.groupby(key):
    for m in METHODS:
        v = g[m + "_rr"].values
        for a, b in itertools.combinations(v, 2):
            diffs.append(abs(a - b))
diffs = np.array(diffs)
eta = np.quantile(diffs, 0.95)
print(f"within-configuration repetition dispersion of reciprocal rank")
print(f"  pairs={len(diffs)}  median={np.median(diffs):.4f}  Q0.95 (band eta)={eta:.4f}")
print(f"  share of repetition pairs differing by more than 0.25: "
      f"{(diffs>0.25).mean():.3f}")
print()

# --- contrasts between methods at each configuration
res = []
for k, g in df.groupby(key):
    means = {m: g[m + "_rr"].mean() for m in METHODS}
    for m1, m2 in itertools.combinations(METHODS, 2):
        d = abs(means[m1] - means[m2])
        res.append({"dataset": k[0], "pair": f"{m1} vs {m2}", "contrast": d,
                    "resolvable": d > eta})
res = pd.DataFrame(res)
print("method-pair contrasts per configuration, against the band")
print(f"  total contrasts: {len(res)}")
print(f"  RESOLVABLE: {res.resolvable.sum()} ({res.resolvable.mean()*100:.1f}%)")
print(f"  NOT resolvable: {(~res.resolvable).sum()} ({(~res.resolvable).mean()*100:.1f}%)")
print()
print(res.groupby("pair").resolvable.agg(["sum", "size", "mean"]).to_string())
print()
print(res.groupby("dataset").resolvable.agg(["sum", "size", "mean"]).to_string())
print()

# --- leaderboard level: does the published-style ordering survive the repetitions?
print("leaderboard per dataset: mean reciprocal rank, with a repetition bootstrap")
rng = np.random.default_rng(0)
for ds, g in df.groupby("dataset"):
    line = [f"  {ds}:"]
    boots = {}
    for m in METHODS:
        line.append(f"{m}={g[m+'_rr'].mean():.3f}")
    # bootstrap: resample whole repetitions within each configuration
    order_counts = {}
    for _ in range(2000):
        samp = g.groupby(["service","fault"], group_keys=False).apply(
            lambda x: x.sample(len(x), replace=True, random_state=int(rng.integers(1e9))))
        means = tuple(sorted(METHODS, key=lambda m: -samp[m+"_rr"].mean()))
        order_counts[means] = order_counts.get(means, 0) + 1
    top = sorted(order_counts.items(), key=lambda kv: -kv[1])
    best = top[0]
    line.append(f"| most frequent ranking {'>'.join(best[0])} in {best[1]/20:.1f}% of bootstraps,"
                f" {len(order_counts)} distinct orderings")
    print(" ".join(line))
