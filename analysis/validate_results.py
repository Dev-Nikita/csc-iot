#!/usr/bin/env python3
"""Gate that runs before any table or figure is produced.

Fails loudly. A quiet pipeline that emits a plausible table from broken data is
worse than no pipeline, because the table ends up in a manuscript.
"""
import sys
import pandas as pd
from common import (RESULTS_LONG, MANIFESTS, CONTROLLERS, require_results,
                    HIGHER_BETTER, LOWER_BETTER)

CHECKS = []


def check(fn):
    CHECKS.append(fn)
    return fn


@check
def missing_or_duplicate_ids(df, problems):
    if df["experiment_id"].duplicated().any():
        dupes = df.loc[df["experiment_id"].duplicated(), "experiment_id"].unique()
        problems.append(f"duplicate experiment_id: {list(dupes)[:5]}")
    ids = set(df["experiment_id"])
    on_disk = {p.stem for p in MANIFESTS.glob("*.json")}
    if on_disk and not ids <= on_disk:
        problems.append(f"{len(ids - on_disk)} rows have no run manifest")


@check
def seed_sets_match(df, problems):
    """Paired analysis is meaningless if methods saw different seeds."""
    for (scenario, devices), g in df.groupby(["scenario", "device_count"]):
        sets = {c: frozenset(gg["seed"]) for c, gg in g.groupby("controller")}
        if len(set(sets.values())) > 1:
            ref = next(iter(sets.values()))
            odd = {c: sorted(s ^ ref)[:5] for c, s in sets.items() if s != ref}
            problems.append(
                f"{scenario}/{devices}: seed sets differ between controllers {odd}")


@check
def nans_and_impossible_values(df, problems):
    for col in HIGHER_BETTER | LOWER_BETTER:
        if col not in df.columns:
            continue
        if df[col].isna().any():
            problems.append(f"NaN in {col} ({int(df[col].isna().sum())} rows)")
    for col in ("pfr", "wir", "availability", "sla_violation_rate", "cra_eta", "cra2_eta"):
        if col in df.columns:
            bad = df[(df[col] < 0) | (df[col] > 1)]
            if len(bad):
                problems.append(f"{col} outside [0,1] in {len(bad)} rows")
    for col in ("p99_latency_ms", "decision_overhead_ms", "intervention_cost"):
        if col in df.columns and (df[col] < 0).any():
            problems.append(f"negative {col}")


@check
def config_consistency(df, problems):
    """Every controller in a comparison group must share the environment."""
    for (scenario, devices), g in df.groupby(["scenario", "device_count"]):
        for col in ("impairment_mode", "warmup_s", "measure_s", "runtime_stack_id"):
            if col in g.columns and g[col].nunique() > 1:
                problems.append(
                    f"{scenario}/{devices}: mixed {col} = {sorted(g[col].unique())}")


@check
def leakage_indicators(df, problems):
    if "is_replay_branch" in df.columns and "split" in df.columns:
        leaked = df[(df["is_replay_branch"]) & (df["split"] == "train")]
        if len(leaked):
            problems.append(f"{len(leaked)} replay-branch rows in the training split")
    if "split" in df.columns and "seed" in df.columns:
        by_split = df.groupby("split")["seed"].apply(set)
        for a in by_split.index:
            for b in by_split.index:
                if a < b and by_split[a] & by_split[b]:
                    problems.append(f"seed overlap between splits {a} and {b}")


@check
def replication_depth(df, problems):
    for (scenario, controller), g in df.groupby(["scenario", "controller"]):
        n = g["seed"].nunique()
        if n < 20:
            problems.append(f"{scenario}/{controller}: only {n} paired seeds (<20)")


@check
def controllers_present(df, problems):
    missing = set(CONTROLLERS) - set(df["controller"].unique())
    if missing:
        problems.append(f"controllers missing from results: {sorted(missing)}")


def main() -> int:
    require_results()
    df = pd.read_csv(RESULTS_LONG)
    problems: list[str] = []
    for fn in CHECKS:
        fn(df, problems)
    if problems:
        print("RESULT VALIDATION FAILED", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nNothing downstream will run.", file=sys.stderr)
        return 1
    print(f"validation passed: {len(df)} rows, "
          f"{df['controller'].nunique()} controllers, "
          f"{df['seed'].nunique()} seeds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
