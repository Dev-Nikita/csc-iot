"""The permutation test and the Holm step, where getting it wrong is silent."""
import math
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "analysis"))
import paired_comparator as pc


def test_identical_groups_give_p_one():
    p, nref, exact = pc.permutation_p([1.0] * 6, [1.0] * 6)
    assert p == 1.0 and exact and nref == math.comb(12, 6) == 924


def test_a_perfect_separation_gives_the_smallest_attainable_p():
    """Six against six is 924 splits, so the floor is 1/924, never zero."""
    p, nref, exact = pc.permutation_p([0.0] * 6, [1.0] * 6)
    assert exact and nref == 924
    # two splits are as extreme as the observed one: the labelling and its mirror
    assert p == pytest.approx(2 / 924)
    assert p > 0.0


def test_the_floor_is_reported_not_rounded_to_zero():
    for n in (5, 6):
        p, nref, _ = pc.permutation_p([0.0] * n, [1.0] * n)
        assert p >= 2 / nref > 0


def test_unequal_groups_after_a_prefix_exclusion_are_still_exact():
    p, nref, exact = pc.permutation_p([0.0] * 5, [1.0] * 6)
    assert exact and nref == math.comb(11, 5) == 462


def test_overlapping_groups_are_not_significant():
    a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    b = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
    p, _, _ = pc.permutation_p(a, b)
    assert p > 0.2


def test_a_sampled_reference_set_is_labelled_as_one():
    a, b = list(range(12)), list(range(12, 24))
    p, nref, exact = pc.permutation_p([float(x) for x in a],
                                      [float(x) for x in b], limit=500)
    assert not exact and nref == 500 and p >= 1 / 500


def test_the_test_is_symmetric_in_its_arguments():
    a = [0.1, 0.4, 0.2, 0.9, 0.3, 0.5]
    b = [0.8, 0.7, 0.6, 0.2, 0.9, 0.4]
    assert pc.permutation_p(a, b)[0] == pc.permutation_p(b, a)[0]


def test_holm_rejects_in_order_and_stops_at_the_first_failure():
    out = pc.holm([("x", 0.001), ("y", 0.03), ("z", 0.9)], 0.05)
    # 0.001 <= 0.05/3, 0.03 > 0.05/2 -> y fails and z cannot reject after it
    assert out["x"][2] is True
    assert out["y"][2] is False
    assert out["z"][2] is False


def test_holm_is_stricter_than_no_correction():
    """A p that would pass alone must not pass as one of three."""
    alone = pc.holm([("x", 0.02)], 0.05)
    among = pc.holm([("x", 0.02), ("y", 0.5), ("z", 0.6)], 0.05)
    assert alone["x"][2] is True
    assert among["x"][2] is False


def test_holm_adjusted_values_are_monotone():
    out = pc.holm([("a", 0.01), ("b", 0.02), ("c", 0.04)], 0.05)
    adj = [out[k][1] for k in ("a", "b", "c")]
    assert adj == sorted(adj)


# --- the attainable floor, and the design that cannot decide anything -------

def test_the_two_sided_floor_is_even_for_equal_groups_and_odd_for_unequal():
    """Corrected 2026-11-09: it is neither always 1/C nor always 2/C."""
    assert pc.min_two_sided_p(6, 6) == (2 / 924, 924)
    assert pc.min_two_sided_p(5, 5) == (2 / 252, 252)
    assert pc.min_two_sided_p(5, 6) == (1 / 462, 462)
    assert pc.min_two_sided_p(6, 5) == (1 / 462, 462)


def test_the_computed_floor_matches_an_actual_perfect_separation():
    for na, nb in ((6, 6), (5, 5), (5, 6), (3, 3)):
        floor, ref = pc.min_two_sided_p(na, nb)
        p, nref, exact = pc.permutation_p([0.0] * na, [1.0] * nb)
        assert exact and nref == ref
        assert p == pytest.approx(floor)


def test_three_repeats_cannot_reject_at_family_wise_five_percent():
    """Modes Q and R and every arm of part D run at three repeats."""
    floor, _ = pc.min_two_sided_p(3, 3)
    assert floor == pytest.approx(0.10)
    strictest_holm = 0.05 / 3
    assert floor > strictest_holm
    # and the test confirms it on data as separated as data can be
    p, _, _ = pc.permutation_p([0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
    assert p == pytest.approx(0.10)
    assert pc.holm([("a", p), ("b", 1.0), ("c", 1.0)], 0.05)["a"][2] is False


def test_six_repeats_can_reject_after_holm():
    p, _, _ = pc.permutation_p([0.0] * 6, [1.0] * 6)
    assert pc.holm([("a", p), ("b", 1.0), ("c", 1.0)], 0.05)["a"][2] is True
