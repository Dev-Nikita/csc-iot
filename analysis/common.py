"""Shared paths and constants for the analysis pipeline.

Single rule this package exists to enforce: no number reaches the manuscript
except through here.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
MANIFESTS = ROOT / "experiments" / "manifests"
TABLES = ROOT / "paper" / "generated_tables"
FIGURES = ROOT / "paper" / "figures"

RESULTS_LONG = PROC / "results_long.csv"
SUMMARY = PROC / "summary.csv"
TESTS = PROC / "statistical_tests.csv"

CONTROLLERS = ["B1_threshold", "B2_gru", "B3_graph", "B4_ppo",
               "B5_csc_predict", "B6_csc"]
CONTROLLER_LABELS = {
    "B1_threshold": "B1 Threshold", "B2_gru": "B2 GRU", "B3_graph": "B3 Graph",
    "B4_ppo": "B4 PPO", "B5_csc_predict": "B5 CSC-Predict", "B6_csc": r"\textbf{B6 CSC}",
}
ABLATIONS = ["A1_no_gate", "A2_no_mni", "A3_no_causal", "full_csc"]
SCENARIOS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]

# Direction of improvement per metric.
HIGHER_BETTER = {"pfr", "availability", "cra", "cra2", "flt"}
LOWER_BETTER = {"wir", "regret", "p99_latency_ms", "intervention_cost",
                "sla_violation_rate", "decision_overhead_ms"}

BOOTSTRAP_RESAMPLES = 10_000
ALPHA = 0.05


def load_config(name: str) -> dict:
    import yaml
    with open(ROOT / "experiments" / "configs" / name) as fh:
        return yaml.safe_load(fh)


def require_results():
    if not RESULTS_LONG.exists():
        raise SystemExit(
            f"{RESULTS_LONG} does not exist. No experiment has been run.\n"
            "The analysis pipeline refuses to invent one."
        )
