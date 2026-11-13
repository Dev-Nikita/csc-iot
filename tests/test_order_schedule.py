"""The constrained draw, and the reference set the analysis is obliged to use."""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gen_order_schedule as gos

ACTIONS = ["NO_OP", "THROTTLE", "REROUTE"]


def test_thirds_constraint_accepts_a_balanced_sequence():
    seq = [(a, r) for r in (1, 2) for a in ACTIONS] * 3
    assert gos.thirds_ok(seq, ACTIONS)


def test_thirds_constraint_rejects_one_action_crowded_early():
    seq = ([("NO_OP", r) for r in range(1, 7)]
           + [("THROTTLE", r) for r in range(1, 7)]
           + [("REROUTE", r) for r in range(1, 7)])
    assert not gos.thirds_ok(seq, ACTIONS)
    assert len(seq) == 18, "this is exactly the historical fixed order"


def test_the_seed_is_a_function_of_the_design_only():
    a, mat = gos.order_seed("c07", "a20")
    b, _ = gos.order_seed("c07", "a20")
    assert a == b
    assert mat == "csc-iot-BDG-order-c07-a20"
    assert gos.order_seed("c07", "a26")[0] != a


def test_a_drawn_cell_satisfies_the_constraint_and_covers_every_branch():
    rec = gos.draw_cell("c01", "a02", ACTIONS, 6)
    order = [tuple(x.split("|")) for x in rec["order"]]
    assert len(order) == 18
    assert len(set(order)) == 18, "every (action, repeat) exactly once"
    assert gos.thirds_ok([(a, int(r.lstrip("r"))) for a, r in order], ACTIONS)


def test_every_member_of_the_reference_sample_satisfies_the_constraint():
    """A free permutation in the reference set is a bug, not conservatism."""
    rec = gos.draw_cell("c02", "a08", ACTIONS, 6)
    assert len(rec["reference_sample"]) == gos.REFERENCE_SAMPLE
    for ref in rec["reference_sample"]:
        seq = [(x.split("|")[0], int(x.split("|")[1].lstrip("r"))) for x in ref]
        assert len(set(seq)) == 18
        assert gos.thirds_ok(seq, ACTIONS)


def test_the_historical_fixed_order_is_not_in_the_reference_set():
    rec = gos.draw_cell("c03", "a14", ACTIONS, 6)
    fixed = ["%s|r%02d" % (a, r) for a in ACTIONS for r in range(1, 7)]
    assert fixed not in rec["reference_sample"]
    assert rec["order"] != fixed


def test_a_design_that_cannot_be_split_in_thirds_is_refused(tmp_path):
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps({"scenarios_hash": "h",
                              "scenarios": [{"scenario_id": "c01"}]}))
    out = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts" / "gen_order_schedule.py"),
         "--scenarios", str(sc), "--anchors", "2", "--actions", "A B",
         "--repeats", "5", "--out", str(tmp_path / "o.json")],
        capture_output=True, text=True, cwd=ROOT)
    assert out.returncode != 0
    assert "three equal parts" in out.stdout + out.stderr
