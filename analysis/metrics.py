#!/usr/bin/env python3
"""Derive per-run metrics from raw logs into data/processed/results_long.csv.

Two rules this module exists to enforce, both of which were defects in v1:

1. The reference objective J_obs is built ONLY from what a replay branch did.
   No model prediction enters it. If it did, the reference ranking would
   contain the prediction it exists to test.
2. Every comparison between actions is resolved at the measured resolution
   eta_J from the D0 audit. Differences smaller than eta_J are ties, not wins.
"""
import json
import pandas as pd
from common import RAW, PROC, RESULTS_LONG, MANIFESTS, load_config


def load_eta_J() -> float:
    """Dispersion band frozen by the D0 audit. Refuses to guess."""
    path = PROC / "d0_audit.json"
    if not path.exists():
        raise SystemExit(
            "data/processed/d0_audit.json missing: eta_J has not been measured.\n"
            "Run the D0 determinism audit (make replay-audit) first. The analysis\n"
            "pipeline will not substitute a default -- a fabricated resolution is\n"
            "worse than no resolution."
        )
    return float(json.loads(path.read_text())["eta_J"])


def objective_observed(branch, w) -> float:
    """J_obs(a) = lF*Y^a + lL*L_tilde^a + lC*C_obs^a  -- replay outcomes only."""
    return (w["lambda_F"] * float(branch["failed"])
            + w["lambda_L"] * float(branch["latency_norm_observed"])
            + w["lambda_C"] * float(branch["cost_observed"]))


def per_run_metrics(decisions: pd.DataFrame, branches: pd.DataFrame,
                    eta: float, w: dict) -> dict:
    branches = branches.copy()
    branches["failed"] = branches["failed"].astype(bool)
    decisions = decisions.copy()
    decisions["abstained"] = decisions["abstained"].astype(bool)
    counts = branches.groupby(["decision_id", "action"]).size()
    if (counts != 1).any():
        bad = counts[counts != 1].head().to_dict()
        raise ValueError(f"each decision/action needs exactly one reference branch: {bad}")
    branches["J_obs"] = branches.apply(lambda b: objective_observed(b, w), axis=1)

    noop = branches[branches["action"] == "a0"].set_index("decision_id")
    taken = decisions.set_index("decision_id")
    jmin = branches.groupby("decision_id")["J_obs"].min()

    def branch_of(did, action):
        m = branches[(branches.decision_id == did) & (branches.action == action)]
        return m.iloc[0] if len(m) else None

    # --- PFR: preventable requires that SOME action actually averted it ------
    failed_noop = noop[noop["failed"]].index
    preventable = [
        d for d in failed_noop
        if ((branches.decision_id == d) & (branches.action != "a0")
            & (~branches.failed)).any()
    ]
    prevented = [
        d for d in preventable
        if (b := branch_of(d, taken.loc[d, "action"])) is not None and not b["failed"]
    ]

    # --- WIR: harmful is worse than no-op by MORE than the dispersion band ---
    acted = taken[taken["action"] != "a0"]
    harmful = []
    for d in acted.index:
        sel = branch_of(d, taken.loc[d, "action"])
        if sel is None or d not in noop.index:
            continue
        if sel["J_obs"] > noop.loc[d, "J_obs"] + eta:
            harmful.append(d)

    # --- tie-aware ranking accuracy and regret -------------------------------
    common = [d for d in taken.index
              if d in jmin.index and branch_of(d, taken.loc[d, "action"]) is not None]
    correct, regrets = 0, []
    for d in common:
        sel = branch_of(d, taken.loc[d, "action"])
        gap = sel["J_obs"] - jmin[d]
        correct += int(gap <= eta)
        regrets.append(max(0.0, gap - eta))

    # CRA@2: the executed action is within the two best observed objectives
    top2 = 0
    for d in common:
        ranked = branches[branches.decision_id == d].nsmallest(2, "J_obs")["action"]
        top2 += int(taken.loc[d, "action"] in set(ranked))

    return {
        "pfr": len(prevented) / len(preventable) if preventable else float("nan"),
        "wir": len(harmful) / len(acted) if len(acted) else 0.0,
        "cra_eta": correct / len(common) if common else float("nan"),
        "cra2_eta": top2 / len(common) if common else float("nan"),
        "regret_eta": float(pd.Series(regrets).mean()) if regrets else float("nan"),
        "abstention_rate": float(taken["abstained"].mean()),
        "fallback_failure_rate": float(
            taken.loc[taken["abstained"], "failed"].mean()) if taken["abstained"].any() else 0.0,
        "intervention_cost": float(acted["cost_observed"].mean()) if len(acted) else 0.0,
        "n_preventable": len(preventable),
        "n_interventions": len(acted),
        "eta_J": eta,
    }


def main() -> None:
    w = load_config("objective.yaml")
    eta = load_eta_J()
    rows = []
    for manifest_path in sorted(MANIFESTS.glob("*.json")):
        m = json.loads(manifest_path.read_text())
        if m.get("exit_status") != "ok":
            continue  # exclusions are logged by the runner, not silently dropped
        run = RAW / m["experiment_id"]
        decisions = pd.read_parquet(run / "decisions.parquet")
        branches = pd.read_parquet(run / "branches.parquet")
        row = {k: m[k] for k in ("experiment_id", "scenario", "controller", "seed",
                                 "device_count", "impairment_mode", "git_commit",
                                 "config_hash", "runtime_stack_id")}
        row.update(pd.read_json(run / "run_summary.json", typ="series").to_dict())
        row.update(per_run_metrics(decisions, branches, eta, w))
        rows.append(row)

    if not rows:
        raise SystemExit("no completed runs found under experiments/manifests/")
    PROC.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(RESULTS_LONG, index=False)
    print(f"wrote {RESULTS_LONG} ({len(rows)} runs, eta_J={eta:.4f})")


if __name__ == "__main__":
    main()
