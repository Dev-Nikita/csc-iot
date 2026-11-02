"""The frozen rules of the mode comparison, as assertions.

Three of these exist because the corresponding mistake was available and cheap:
selecting F's three repeats by value rather than by index, pooling the band
across modes, and letting an unresolved cell count as agreement.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import mode_comparison as mc


def rows(spec):
    """spec: {(scenario, anchor, action, repeat): J_obs}"""
    return [{"scenario": s, "anchor": a, "action": c, "repeat": r,
             "fault_type": "D1", "regime": "post-onset", "J_obs": j}
            for (s, a, c, r), j in spec.items()]


def test_f_three_repeats_are_chosen_by_index_not_by_value():
    # r01..r03 are the three WORST; a selection by value would take r08..r10.
    spec = {("c01", "a02", "NO_OP", f"r{i:02d}"): (1.0 if i <= 3 else 0.0)
            for i in range(1, 11)}
    got = sorted(r["repeat"] for r in mc.subset(rows(spec), range(1, 4)))
    assert got == ["r01", "r02", "r03"]
    assert {r["J_obs"] for r in mc.subset(rows(spec), range(1, 4))} == {1.0}


def test_the_band_of_a_mode_is_measured_inside_that_mode():
    quiet = rows({("c01", "a02", "NO_OP", f"r{i:02d}"): 0.0 for i in (1, 2, 3)})
    noisy = rows({("c01", "a02", "NO_OP", "r01"): 0.0,
                  ("c01", "a02", "NO_OP", "r02"): 1.0,
                  ("c01", "a02", "NO_OP", "r03"): 2.0})
    assert mc.pooled_band(quiet)[0] == 0.0
    assert mc.pooled_band(noisy)[0] > 1.0
    # and pooling the two would give neither
    assert mc.pooled_band(quiet + noisy)[0] != mc.pooled_band(noisy)[0]


def test_a_gap_at_the_band_is_not_resolved():
    spec = {}
    for i in (1, 2, 3):
        spec[("c01", "a02", "NO_OP", f"r{i:02d}")] = 0.0
        spec[("c01", "a02", "REROUTE", f"r{i:02d}")] = 0.5
    c = mc.cells(rows(spec), band=0.5)
    assert c[("c01", "a02")]["gap"] == pytest.approx(0.5)
    assert c[("c01", "a02")]["resolved"] is False
    assert mc.cells(rows(spec), band=0.49)[("c01", "a02")]["resolved"] is True


def test_ties_break_by_action_name():
    spec = {}
    for i in (1, 2):
        spec[("c01", "a02", "THROTTLE", f"r{i:02d}")] = 1.0
        spec[("c01", "a02", "REROUTE", f"r{i:02d}")] = 1.0
    c = mc.cells(rows(spec), band=0.0)[("c01", "a02")]
    assert c["winner"] == "REROUTE" and c["tied"] and not c["resolved"]


def _matrix(tmp, name, mode, spec, repeats, extra=None):
    d = tmp / name
    d.mkdir(parents=True)
    meta = {"mode": mode, "runtime_stack_id": "stack0", "master_seed": 42,
            "anchor_spec": "1,2", "actions": "NO_OP REROUTE", "repeats": repeats,
            "scenario_set_hash": "hash0"}
    meta.update(extra or {})
    (d / "matrix.json").write_text(json.dumps(meta))
    hdr = "branch,scenario,anchor,action,repeat,regime,fault_type,J_obs\n"
    body = "".join(
        f"{s}-{a}-{c}-{r},{s},{a},{c},{r},post-onset,D1,{j}\n"
        for (s, a, c, r), j in spec.items())
    (d / "jobs.csv").write_text(hdr + body)
    return d


def _two_action_spec(reroute_j, n):
    return {k: v for i in range(1, n + 1) for k, v in (
        (("c01", "a01", "NO_OP", f"r{i:02d}"), 1.0),
        (("c01", "a01", "REROUTE", f"r{i:02d}"), reroute_j))}


def test_an_unresolved_cell_is_neither_agreement_nor_disagreement(tmp_path):
    # identical winners, but both modes have a zero gap: unresolved, not agreed.
    full = mc.load_matrix(str(tmp_path), _matrix(
        tmp_path, "f", "full", _two_action_spec(1.0, 3), 3).name)
    abl = mc.load_matrix(str(tmp_path), _matrix(
        tmp_path, "q", "quiescence", _two_action_spec(1.0, 3), 3).name)
    r = mc.compare(full, abl)
    assert r["label"]["unresolved in one or both"] == 1
    assert r["label"].get("agreement", 0) == 0
    assert r["label"].get("disagreement", 0) == 0


def test_a_real_winner_change_is_a_disagreement(tmp_path):
    full = mc.load_matrix(str(tmp_path), _matrix(
        tmp_path, "f", "full", _two_action_spec(0.0, 3), 3).name)
    abl = mc.load_matrix(str(tmp_path), _matrix(
        tmp_path, "q", "quiescence", _two_action_spec(2.0, 3), 3).name)
    r = mc.compare(full, abl)
    assert r["label"]["disagreement"] == 1
    (_, x, y), = r["disagreements"]
    assert (x["winner"], y["winner"]) == ("REROUTE", "NO_OP")


def test_a_void_run_is_refused(tmp_path):
    d = _matrix(tmp_path, "r", "reset", _two_action_spec(0.0, 3), 3)
    (d / "VOID.txt").write_text("the reset ablation ablated nothing\nsee amendment 5")
    with pytest.raises(SystemExit):
        mc.load_matrix(str(tmp_path), "r")


def test_a_reset_matrix_that_tore_down_every_branch_is_refused(tmp_path):
    d = _matrix(tmp_path, "r", "reset", _two_action_spec(0.0, 3), 3)
    for b in ("c01-a01-NO_OP-r01", "c01-a01-REROUTE-r01"):
        (d / b).mkdir()
        (d / b / "startup.json").write_text('{"tore_down_first": 1}')
    with pytest.raises(SystemExit):
        mc.load_matrix(str(tmp_path), "r")


def test_a_different_substrate_is_refused(tmp_path):
    _matrix(tmp_path, "f", "full", _two_action_spec(0.0, 3), 3)
    _matrix(tmp_path, "q", "quiescence", _two_action_spec(0.0, 3), 3,
            extra={"runtime_stack_id": "stack1"})
    ms = [mc.load_matrix(str(tmp_path), "f"), mc.load_matrix(str(tmp_path), "q")]
    with pytest.raises(SystemExit):
        mc.require_same_substrate(ms)
