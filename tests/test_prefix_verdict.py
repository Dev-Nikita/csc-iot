"""The prefix verdict must be the exit status, not a flag nobody reads."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "analysis"))
import m2prime_report as r


def test_one_state_per_cell_is_clean():
    lines, split = r.prefix_verdict({("c01", "a02"): ["aaa"] * 30})
    assert split == []
    assert "distinct=1" in lines[0]
    assert "NOT ONE STATE" not in lines[0]


def test_a_cell_with_two_states_is_reported():
    lines, split = r.prefix_verdict({("c01", "a02"): ["aaa"] * 28 + ["bbb"] * 2})
    assert len(split) == 1
    label, n, distinct, sizes = split[0]
    assert (label, n, distinct, sizes) == ("c01-a02", 30, 2, [28, 2])
    assert "NOT ONE STATE" in lines[0]


def test_three_states_and_only_the_split_cells_are_listed():
    lines, split = r.prefix_verdict({
        ("c09", "a26"): ["a"] * 10 + ["b"] * 10 + ["c"] * 10,
        ("c11", "a02"): ["z"] * 30,
    })
    assert [s[0] for s in split] == ["c09-a26"]
    assert split[0][2] == 3 and split[0][3] == [10, 10, 10]
    assert len(lines) == 2


def test_unnamed_scenario_falls_back_to_the_anchor_label():
    lines, split = r.prefix_verdict({("s00", "a14"): ["q", "r"]})
    assert split[0][0] == "a14"
