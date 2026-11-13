"""The C6 rules, as assertions, so the verdict cannot be chosen at reading time."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import seed_variance as sv


def rows(point_anchor_gaps, repeats=3):
    """Build jobs-like rows so that each cell has a chosen between-action gap."""
    out = []
    for (point, anchor), gap in point_anchor_gaps.items():
        for i in range(1, repeats + 1):
            out.append({"point": point, "anchor": anchor, "action": "NO_OP",
                        "J": 1.0, "fault": "D1"})
            out.append({"point": point, "anchor": anchor, "action": "REROUTE",
                        "J": 1.0 + gap, "fault": "D1"})
    return out


def test_zero_dispersion_makes_any_gap_resolvable():
    """With identical repeats the band is zero, so a positive gap resolves."""
    a = sv.analyse_arm(rows({("c01", "a02"): 0.5, ("c01", "a08"): 0.0}))
    assert a["band"] == 0.0
    assert a["cells"] == 2
    # the zero-gap cell is not resolved: the rule is strict inequality
    assert a["unresolved"] == 1
    assert a["share"] == pytest.approx(0.5)


def test_the_point_share_is_computed_over_that_point_s_cells():
    a = sv.analyse_arm(rows({("c01", "a02"): 0.0, ("c01", "a08"): 0.0,
                             ("c02", "a02"): 0.5, ("c02", "a08"): 0.5}))
    assert a["point_share"]["c01"] == pytest.approx(1.0)
    assert a["point_share"]["c02"] == pytest.approx(0.0)


def test_variance_is_the_sample_variance_and_a_single_value_gives_zero():
    assert sv.variance([1.0]) == 0.0
    assert sv.variance([1.0, 3.0]) == pytest.approx(2.0)


def test_the_frozen_thresholds_are_the_ones_in_the_contract():
    assert sv.MIN_UNRESOLVED_SHARE == 0.20
    assert sv.MAX_VARIANCE_RATIO == 4.0


def test_rule_two_ratio_is_between_seed_over_mean_within_seed():
    """The operationalisation, asserted so it cannot drift."""
    # three seeds, four points; seed means differ, within-seed spread is equal
    table = {"k1": [0.0, 0.2, 0.4, 0.6], "k2": [0.1, 0.3, 0.5, 0.7],
             "k3": [0.2, 0.4, 0.6, 0.8]}
    seed_means = [sv.mean(v) for v in table.values()]
    within = [sv.variance(v) for v in table.values()]
    s2_seed, s2_within = sv.variance(seed_means), sv.mean(within)
    assert s2_seed == pytest.approx(0.01)
    assert s2_within == pytest.approx(sv.variance([0.0, 0.2, 0.4, 0.6]))
    assert s2_seed / s2_within < sv.MAX_VARIANCE_RATIO


def test_a_seed_dominated_result_fails_rule_two():
    table = {"k1": [0.10, 0.11, 0.09, 0.10], "k2": [0.50, 0.51, 0.49, 0.50],
             "k3": [0.90, 0.91, 0.89, 0.90]}
    seed_means = [sv.mean(v) for v in table.values()]
    within = [sv.variance(v) for v in table.values()]
    ratio = sv.variance(seed_means) / sv.mean(within)
    assert ratio > sv.MAX_VARIANCE_RATIO


def test_an_arm_that_resolves_everything_fails_rule_one():
    a = sv.analyse_arm(rows({("c01", "a02"): 0.5, ("c01", "a08"): 0.5}))
    assert a["share"] == 0.0
    assert a["share"] < sv.MIN_UNRESOLVED_SHARE


def test_a_missing_jobs_csv_is_refused_with_the_command_to_make_it(tmp_path):
    (tmp_path / "bdg2-d-k1-s42").mkdir()
    with pytest.raises(SystemExit) as e:
        sv.load_arm(str(tmp_path), "bdg2-d-k1-s42")
    assert "analysis/jobs.py" in str(e.value)


def test_the_paired_across_seed_range_is_zero_when_seeds_agree():
    """The statistic that answers the question rule 2 only gestures at."""
    table = {"k1": [0.17, 1.00, 0.50], "k2": [0.17, 1.00, 0.50],
             "k3": [0.17, 1.00, 0.50]}
    ranges = [max(v) - min(v) for v in zip(*table.values())]
    assert ranges == [0.0, 0.0, 0.0]
    assert sv.mean(ranges) == 0.0


def test_rule_two_passes_on_a_design_dominated_table_that_says_nothing_about_seeds():
    """Why rule 2 is weak: between-point heterogeneity inflates its denominator."""
    # every seed identical, but points range from 0 to 1 -> huge within, zero between
    table = {f"k{i}": [0.0, 0.17, 0.5, 0.83, 1.0] for i in range(1, 6)}
    seed_means = [sv.mean(v) for v in table.values()]
    within = [sv.variance(v) for v in table.values()]
    ratio = sv.variance(seed_means) / sv.mean(within)
    assert ratio == 0.0
    assert sv.mean(within) > 0.1, "the denominator is the design, not seed noise"
