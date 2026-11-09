"""The exclusion policy decides on anchor hashes and on nothing else.

The assertion that matters most here is the last one: negating every objective
value in the matrix leaves the decision byte-identical. An exclusion rule that
can see the outcome is not an exclusion rule.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import prefix_exclusion as px


def matrix(tmp, cells):
    """cells: {(scenario, anchor): [(action, repeat, anchor_hash, j_obs)]}"""
    for (sc, an), rows in cells.items():
        for action, rep, h, j in rows:
            d = tmp / f"{sc}-{an}-{action}-r{rep:02d}"
            d.mkdir(parents=True)
            (d / "anchor.json").write_text(json.dumps({"hash": h}))
            (d / "outcome.json").write_text(json.dumps({"observed": {"j": j}}))
    return tmp


def clean_cell(sc, an, h="aaa"):
    return {(sc, an): [(a, r, h, 1.0)
                       for a in ("NO_OP", "THROTTLE", "REROUTE")
                       for r in range(1, 7)]}


def test_a_cell_with_one_state_is_untouched(tmp_path):
    d = matrix(tmp_path, clean_cell("c01", "a02"))
    out = px.decide(px.cell_states(str(d)))
    assert out["split_cells"] == []
    assert out["excluded_branches"] == []


def test_the_minority_branch_of_a_split_cell_is_excluded(tmp_path):
    cell = clean_cell("c09", "a14")
    rows = cell[("c09", "a14")]
    rows[-1] = (rows[-1][0], rows[-1][1], "bbb", rows[-1][3])  # one odd branch
    d = matrix(tmp_path, cell)
    out = px.decide(px.cell_states(str(d)))
    assert len(out["split_cells"]) == 1
    rec = out["split_cells"][0]
    assert rec["cell"] == "c09-a14"
    assert rec["group_sizes"] == [17, 1]
    assert rec["resolution"] == "branches excluded"
    assert out["excluded_branches"] == ["c09-a14-REROUTE-r06"]
    assert out["excluded_cells"] == []


def test_a_cell_without_a_strict_majority_is_excluded_whole(tmp_path):
    rows = [("NO_OP", 1, "aaa", 1.0), ("NO_OP", 2, "bbb", 2.0)]
    d = matrix(tmp_path, {("c09", "a20"): rows})
    out = px.decide(px.cell_states(str(d)))
    rec = out["split_cells"][0]
    assert rec["group_sizes"] == [1, 1]
    assert rec["resolution"].startswith("cell excluded")
    assert out["excluded_cells"] == ["c09-a20"]
    assert len(out["excluded_branches"]) == 2


def test_an_unreadable_anchor_is_refused_not_guessed(tmp_path):
    d = matrix(tmp_path, clean_cell("c01", "a02"))
    (d / "c01-a02-NO_OP-r01" / "anchor.json").write_text("{}")
    with pytest.raises(SystemExit):
        px.cell_states(str(d))


def test_the_decision_cannot_see_the_objective(tmp_path):
    """Negate every outcome; the exclusion set must not move by one byte."""
    cell = clean_cell("c10", "a26")
    rows = cell[("c10", "a26")]
    rows[0] = (rows[0][0], rows[0][1], "zzz", rows[0][3])
    a = matrix(tmp_path / "a", {k: list(v) for k, v in cell.items()})
    first = px.decide(px.cell_states(str(a)))

    flipped = {k: [(ac, r, h, -j) for ac, r, h, j in v] for k, v in cell.items()}
    b = matrix(tmp_path / "b", flipped)
    second = px.decide(px.cell_states(str(b)))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_write_is_idempotent_and_refuses_a_moved_decision(tmp_path, capsys):
    cell = clean_cell("c09", "a26")
    rows = cell[("c09", "a26")]
    rows[-1] = (rows[-1][0], rows[-1][1], "bbb", rows[-1][3])
    d = matrix(tmp_path, cell)
    argv = sys.argv
    try:
        sys.argv = ["x", str(d), "--write"]
        assert px.main() == 0
        assert px.main() == 0            # same decision again: fine
        doc = json.loads((d / "prefix_exclusions.json").read_text())
        assert doc["excluded_branches"] == ["c09-a26-REROUTE-r06"]
        doc["excluded_branches"] = []
        (d / "prefix_exclusions.json").write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n")
        assert px.main() == 2            # a decision that moved: refused
    finally:
        sys.argv = argv


def test_load_refuses_a_foreign_policy_version(tmp_path):
    (tmp_path / "prefix_exclusions.json").write_text(
        json.dumps({"policy": "something-else", "excluded_branches": []}))
    with pytest.raises(SystemExit):
        px.load(str(tmp_path))


def test_the_spread_of_the_exclusion_set_over_actions_is_reported():
    comp = px.composition(["c09-a14-REROUTE-r06", "c09-a20-NO_OP-r06",
                           "c09-a26-NO_OP-r05", "c09-a30-THROTTLE-r03",
                           "c10-a26-THROTTLE-r01"])
    assert comp["by_action"] == {"NO_OP": 2, "REROUTE": 1, "THROTTLE": 2}
    assert comp["by_repeat"] == {"r01": 1, "r03": 1, "r05": 1, "r06": 2}
    assert comp["max_share_one_action"] == 0.4
    assert comp["single_action_only"] is False


def test_an_exclusion_set_confined_to_one_action_is_flagged():
    """The one way a decision blind to the objective can still bias it."""
    comp = px.composition(["c09-a14-REROUTE-r06", "c09-a20-REROUTE-r02",
                           "c09-a26-REROUTE-r05"])
    assert comp["single_action_only"] is True
    assert comp["max_share_one_action"] == 1.0
