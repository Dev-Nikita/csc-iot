import csv
import subprocess
import sys
from pathlib import Path


def test_independent_recompute_selects_largest_feasible_threshold(tmp_path):
    ledger = tmp_path / "ledger.csv"
    fields = ["branch", "seed", "fault_type", "fault_onset",
              "fault_severity", "workload_level", "anchor", "action",
              "risk", "uncertainty", "Y_ms", "failed", "theta",
              "theta_n", "u_max", "delta", "split"]
    with ledger.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        # Twenty exchangeable run units make the correction 1/21.  The unsafe
        # action enters at tau=0.2, so tau=0.1 is the largest feasible value.
        for seed in range(20):
            for action, risk, failed in (("NO_OP", 0.1, 0),
                                         ("REROUTE", 0.2, 1)):
                w.writerow({
                    "branch": f"s{seed}-{action}", "seed": seed,
                    "fault_type": "D1", "fault_onset": 5,
                    "fault_severity": 40, "workload_level": 100,
                    "anchor": 2, "action": action, "risk": risk,
                    "uncertainty": 0.01, "Y_ms": failed,
                    "failed": failed, "theta": 0.5, "theta_n": 20,
                    "u_max": 0.15, "delta": 0.10,
                    "split": "calibration",
                })
    script = Path(__file__).parents[1] / "analysis" / "recompute_crc_independent.py"
    out = subprocess.check_output([sys.executable, str(script), str(ledger)],
                                  text=True)
    assert "runs=20" in out
    assert "tau_hat=0.1" in out
    assert "corrected_risk=0.04761904762" in out
