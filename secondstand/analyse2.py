"""Resolvability on RCAEval RE1, reported three ways.

The first version of this script compared the MEAN of five repetitions against a
band built from differences between SINGLE repetitions. That is a mismatch: a
mean of five is about four times less dispersed than one observation, so the
criterion was far too conservative and produced "0 of 75" for the two
competitive methods. An independent review flagged it; this script replaces it.

Three criteria are reported, because they answer three different questions:

  (A) single-observation, band      -- can ONE run of each method distinguish
                                       them? This is the regime the manuscript's
                                       own design is in: one branch per action
                                       per anchor.
  (B) paired bootstrap over the five repetitions -- can FIVE runs distinguish
                                       them? Methods are scored on the same
                                       cases, so the differences are paired.
  (C) pooled hierarchical bootstrap -- do the methods differ at all, over the
                                       whole suite?
"""
import json, itertools
import numpy as np, pandas as pd

rows = [json.loads(l) for l in open("results.jsonl")]
df = pd.DataFrame(rows)
M = ["baro", "nsigma", "e_diagnosis"]
for m in M:
    df[m + "_rr"] = df[m].apply(
        lambda p: 0.0 if p is None or (isinstance(p, float) and np.isnan(p)) else 1.0 / p)
key = ["dataset", "service", "fault"]
rng = np.random.default_rng(7)

d = np.array([abs(a - b) for _, g in df.groupby(key) for m in M
              for a, b in itertools.combinations(g[m + "_rr"].values, 2)])
eta = np.quantile(d, 0.95)
print(f"cases {len(df)}  configurations {df.groupby(key).ngroups}  repetition pairs {len(d)}")
print(f"band eta = Q0.95 of |difference between two single repetitions| = {eta:.4f}")
print(f"repetition pairs differing by more than 0.25: {(d>0.25).mean()*100:.1f}%\n")

print("(A) one run each, against the band")
a_rows = [{"pair": f"{x} vs {y}", "res": abs(r[x+"_rr"] - r[y+"_rr"]) > eta}
          for _, r in df.iterrows() for x, y in itertools.combinations(M, 2)]
A = pd.DataFrame(a_rows)
print(f"    resolvable {A.res.sum()} of {len(A)} ({A.res.mean()*100:.1f}%)")
print(A.groupby("pair").res.agg(resolvable="sum", n="size", frac="mean").to_string(), "\n")

print("(B) five repetitions, paired bootstrap CI on the mean difference")
b_rows = []
for k, g in df.groupby(key):
    for x, y in itertools.combinations(M, 2):
        v = (g[x+"_rr"] - g[y+"_rr"]).values; n = len(v)
        bs = np.array([v[rng.integers(0, n, n)].mean() for _ in range(4000)])
        lo, hi = np.quantile(bs, [0.025, 0.975])
        b_rows.append({"pair": f"{x} vs {y}", "res": lo > 0 or hi < 0})
B = pd.DataFrame(b_rows)
print(f"    resolvable {B.res.sum()} of {len(B)} ({B.res.mean()*100:.1f}%)")
print(B.groupby("pair").res.agg(resolvable="sum", n="size", frac="mean").to_string(), "\n")

print("(C) whole suite, hierarchical bootstrap over configurations and repetitions")
for x, y in itertools.combinations(M, 2):
    cfg = [g[x+"_rr"].values - g[y+"_rr"].values for _, g in df.groupby(key)]
    bs = []
    for _ in range(4000):
        idx = rng.integers(0, len(cfg), len(cfg))
        bs.append(np.mean([cfg[i][rng.integers(0, len(cfg[i]), len(cfg[i]))].mean() for i in idx]))
    lo, hi = np.quantile(bs, [0.025, 0.975])
    print(f"    {x:12s} - {y:14s} {np.mean(bs):+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]"
          f"  {'resolved' if lo>0 or hi<0 else 'NOT resolved'}")
