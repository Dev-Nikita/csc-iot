#!/usr/bin/env python3
"""D0: replay-repeatability audit. Measures eta_J and freezes it.

Runs once, before the main experiments. 20 anchors x 5 actions x 30 identical
repeats. eta_J is the 0.95 quantile of |J_obs difference| between two repeats
of the SAME anchor under the SAME action -- i.e. the objective spread the
environment produces when nothing at all was changed.

Two actions are distinguishable only above this band. If eta_J is wide enough
to swallow the typical between-action spread, the replay methodology cannot
resolve what the paper needs it to, and the correct response is to fix
determinism, not to report the comparison anyway.
"""
import itertools
import json
import numpy as np
import pandas as pd
# Run under `python3 -I` the script's own directory is NOT on sys.path, so a
# sibling import fails with ModuleNotFoundError. The documented recompute
# commands use -I deliberately -- it is how a script that reads downloaded data
# is run safely -- so every analysis that imports a sibling puts its own
# directory on the path itself rather than depending on how it was invoked.
# This cost a scoring run of five part-D arms.
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from common import RAW, PROC, load_config


def main() -> None:
    w = load_config("objective.yaml")
    cfg = load_config("runs.yaml")["d0_audit"]
    df = pd.read_parquet(RAW / "d0" / "branches.parquet")
    df["J_obs"] = (w["lambda_F"] * df["failed"].astype(float)
                   + w["lambda_L"] * df["latency_norm_observed"]
                   + w["lambda_C"] * df["cost_observed"])

    diffs = []
    for (anchor, action), g in df.groupby(["state_id", "action"]):
        vals = g["J_obs"].to_numpy()
        diffs += [abs(a - b) for a, b in itertools.combinations(vals, 2)]
    diffs = np.asarray(diffs)
    eta = float(np.quantile(diffs, cfg["eta_J_quantile"]))

    # between-action spread, for the usability check
    between = df.groupby(["state_id", "action"])["J_obs"].mean().unstack()
    spread = float((between.max(axis=1) - between.min(axis=1)).median())

    out = {
        "eta_J": eta,
        "eta_J_quantile": cfg["eta_J_quantile"],
        "n_repeat_pairs": int(len(diffs)),
        "n_anchors": int(df["state_id"].nunique()),
        "median_between_action_spread": spread,
        "usable": bool(spread > 2 * eta),
    }
    PROC.mkdir(parents=True, exist_ok=True)
    (PROC / "d0_audit.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    if not out["usable"]:
        raise SystemExit(
            "\nD0 GATE FAILED: the same-action dispersion band is comparable to the\n"
            "spread between different actions. Replay cannot resolve action\n"
            "differences at this determinism level. Return to the determinism phase.\n"
            "Do not proceed to model training."
        )


if __name__ == "__main__":
    main()
