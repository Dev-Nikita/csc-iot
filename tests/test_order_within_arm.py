"""The within-arm order analysis, where reading the wrong column is silent."""
import csv
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import order_within_arm as owa


def write_jobs(path, rows, with_pos=True):
    cols = ["branch", "exec_index", "cell_exec_index", "scenario", "anchor",
            "action", "repeat", "J_obs"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            w.writerow({"branch": f"b{i}", "exec_index": i,
                        "cell_exec_index": r["pos"] if with_pos else "",
                        "scenario": r["cell"][0], "anchor": r["cell"][1],
                        "action": r["action"], "repeat": "r01",
                        "J_obs": r["J"]})


def test_a_jobs_csv_without_the_column_is_refused(tmp_path):
    p = tmp_path / "jobs.csv"
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario", "anchor", "action", "J_obs"])
        w.writerow(["c01", "a02", "NO_OP", "1.0"])
    with pytest.raises(SystemExit) as e:
        owa.load(str(p))
    assert "cell_exec_index" in str(e.value)


def test_a_fixed_order_matrix_is_sent_to_the_other_script(tmp_path):
    p = tmp_path / "jobs.csv"
    write_jobs(p, [{"cell": ("c01", "a02"), "action": "NO_OP", "pos": 1,
                    "J": 1.0}], with_pos=False)
    with pytest.raises(SystemExit) as e:
        owa.load(str(p))
    assert "order_effects.py" in str(e.value)


def test_detrend_removes_a_pure_position_trend():
    pts = [(i, 2.0 + 0.5 * i) for i in range(1, 7)]
    resid, slope = owa.detrend(pts)
    assert slope == pytest.approx(0.5)
    assert all(abs(r) < 1e-9 for r in resid)


def test_detrend_leaves_a_real_action_difference_alone():
    """A pattern balanced against position keeps its whole offset.

    The first version of this test used an alternating pattern and asserted a
    zero slope. Alternating is NOT orthogonal to position on 1..6 -- the fit
    picks up a slope of 0.0857 -- so the test was wrong and the estimator was
    right. The balanced arrangement below is the one with no positional
    information in it.
    """
    pts = [(1, 1.0), (2, 2.0), (5, 2.0), (6, 1.0)]
    resid, slope = owa.detrend(pts)
    assert abs(slope) < 1e-12
    assert max(resid) - min(resid) == pytest.approx(1.0)


def test_every_branch_at_one_position_does_not_raise():
    resid, slope = owa.detrend([(3, 1.0), (3, 2.0), (3, 3.0)])
    assert slope == 0.0
    assert resid == pytest.approx([-1.0, 0.0, 1.0])


def test_spearman_is_one_on_a_monotone_sequence():
    assert owa.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert owa.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
    assert owa.spearman([1, 1, 1], [1, 2, 3]) is None


def test_thirds_check_is_applied_to_the_reference_set():
    actions = ["A", "B", "C"]
    good = [(a, f"r{r:02d}") for r in (1, 2) for a in actions] * 3
    assert owa.thirds_ok(good, actions)
    crowded = ([("A", "r1")] * 6 + [("B", "r1")] * 6 + [("C", "r1")] * 6)
    assert not owa.thirds_ok(crowded, actions)
