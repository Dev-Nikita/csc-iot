#!/usr/bin/env python3
"""Derive per-run metrics from raw logs into data/processed/results_long.csv.

PFR and WIR are defined against replayed branches, not against model output:
a failure is preventable only if the no-action branch actually failed, and an
intervention is harmful only if its branch objective is worse than the
no-action branch by more than the measured dispersion band.
"""
import json
import pandas as pd
from common import RAW, PROC, RESULTS_LONG, MANIFESTS, load_config


def dispersion_band(branches: pd.DataFrame) -> float:
    """Resolution floor: spread of same-state/same-action replays.

    Differences smaller than this are not interpretable and are reported as
    ties rather than as wins.
    """
    ctrl = branches[branches["control_replicate"]]
    if ctrl.empty:
        raise SystemExit("no same-action control branches; run `make replay` first")
    return float(ctrl.groupby("decision_id")["objective"].std().mean())


def objective(row, w) -> float:
    return w["alpha"] * row["risk"] + w["beta"] * row["latency_norm"] + w["gamma"] * row["cost"]


def per_run_metrics(decisions: pd.DataFrame, branches: pd.DataFrame,
                    band: float, w: dict) -> dict:
    noop = branches[branches["action"] == "a0"].set_index("decision_id")
    taken = decisions.set_index("decision_id")

    preventable = noop[noop["failed"]].index
    prevented = [d for d in preventable
                 if d in taken.index and not taken.loc[d, "failed"]]

    acted = taken[taken["action"] != "a0"]
    harmful = [d for d in acted.index
               if d in noop.index
               and taken.loc[d, "objective"] > noop.loc[d, "objective"] + band]

    best = branches.loc[branches.groupby("decision_id")["objective"].idxmin()]
    best = best.set_index("decision_id")["action"]
    ranked = taken["predicted_best_action"]
    common = best.index.intersection(ranked.index)

    regret = [taken.loc[d, "objective"] - branches[branches.decision_id == d]["objective"].min()
              for d in common]

    return {
        "pfr": len(prevented) / len(preventable) if len(preventable) else float("nan"),
        "wir": len(harmful) / len(acted) if len(acted) else 0.0,
        "cra": float((best[common] == ranked[common]).mean()) if len(common) else float("nan"),
        "regret": float(pd.Series(regret).mean()) if regret else float("nan"),
        "abstention_rate": float((taken["abstained"]).mean()),
        "intervention_cost": float(acted["cost"].mean()) if len(acted) else 0.0,
        "dispersion_band": band,
    }


def main() -> None:
    w = load_config("objective.yaml")
    rows = []
    for manifest_path in sorted(MANIFESTS.glob("*.json")):
        m = json.loads(manifest_path.read_text())
        if m.get("exit_status") != "ok":
            continue  # exclusions are handled and logged by the runner
        run = RAW / m["experiment_id"]
        decisions = pd.read_parquet(run / "decisions.parquet")
        branches = pd.read_parquet(run / "branches.parquet")
        band = dispersion_band(branches)
        row = {k: m[k] for k in ("experiment_id", "scenario", "controller",
                                 "seed", "device_count", "impairment_mode",
                                 "git_commit", "config_hash")}
        row.update(pd.read_json(run / "run_summary.json", typ="series").to_dict())
        row.update(per_run_metrics(decisions, branches, band, w))
        rows.append(row)

    if not rows:
        raise SystemExit("no completed runs found under experiments/manifests/")
    PROC.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(RESULTS_LONG, index=False)
    print(f"wrote {RESULTS_LONG} ({len(rows)} runs)")


if __name__ == "__main__":
    main()
