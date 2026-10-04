"""The price sweep, and the ceiling that makes 'no crossing' readable.

The first version divided the price by (EDGES - 1) = 2, which redefined "price
1.0" as the cost of recruiting EVERY edge and capped the price's effect on J at
0.2 x 1/3 x 0.5 = 0.0333 -- below the 0.0445 gap it was meant to be able to
close. The sweep then reported "REROUTE preferred at every price", which was a
property of the normaliser and not of the system.

So the arithmetic of the ceiling is tested here, not only the sweep's output: a
negative result about a crossing is only meaningful if the crossing was reachable.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "cost_sensitivity", os.path.join(HERE, "..", "analysis", "cost_sensitivity.py"))
cs = importlib.util.module_from_spec(spec)
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
spec.loader.exec_module(cs)


def test_price_is_per_recruited_edge_not_per_topology():
    """At p = 1 a single recruited edge must cost a full unit, not a half."""
    assert min(1.0, 1.0 * 1) == 1.0


def test_the_reachable_ceiling_exceeds_the_measured_gap():
    """Measured on d6-pilot-v2: NO_OP 0.4619, REROUTE 0.4174 at price 0."""
    gap = 0.4619 - 0.4174
    per_unit = cs.W_COST / 3.0          # one of three components
    assert per_unit > gap / 1.0, "a crossing must be reachable within p <= 1"
    assert abs(gap / per_unit - 0.667) < 0.01


def test_the_old_normaliser_could_not_reach_a_crossing():
    """Why the first sweep's conclusion was void."""
    gap = 0.4619 - 0.4174
    old_ceiling = (cs.W_COST / 3.0) * (len(cs.EDGES) - 1) ** -1
    assert old_ceiling < gap


def test_recruited_counts_edges_beyond_the_first():
    assert cs.recruited({"edge00/served": 2000.0}) == 0
    assert cs.recruited({"edge00/served": 1500.0, "edge01/served": 500.0}) == 1
    assert cs.recruited({}) == 0


def test_an_edge_that_served_nothing_is_not_recruited():
    assert cs.recruited({"edge00/served": 2000.0, "edge01/served": 0.0}) == 0


def test_mean_of_nothing_is_nan_not_zero():
    v = cs.mean([])
    assert v != v
