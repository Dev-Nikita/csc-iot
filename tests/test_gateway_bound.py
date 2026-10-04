"""The upper bound on what a gateway with an admission fault can forward.

The onset epoch is charged at the HEALTHY rate. That is not slack: the gateway's
fault limits arrivals, and an event tagged with epoch T can reach the gateway
before the boundary at which the fault for T is applied, because the device
simulator emits ahead of the boundary. Charging the onset epoch at the cap made
the bound one cap's worth too tight and refused 228 correct branches of
d45-matrix-v1 -- 1840 forwarded against a bound of 1800.

The edge bound keeps `onset - 1`, because an edge fault limits SERVING, which
happens at the boundary itself with the fault already in force. The two bounds
differ because the two faults act on different sides of the boundary.

The case that matters most is the last one: the bound must still catch a fault
that never bound at all, which is the defect it was written for.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
import audit_accounting as A

TOLERANCE = 1.02  # as applied in the audit: forwarded > bound * 1.02 + 1


def refuses(forwarded, offered, gw, onset, end_epoch):
    b = A.gateway_forward_bound(offered, gw, onset, end_epoch)
    return forwarded > b * TOLERANCE + 1


def test_the_228_refused_branches_of_d45_matrix_v1_now_pass():
    """s02-a14: onset 17, outcome epoch 22, 1840 forwarded of 2700 offered."""
    assert A.gateway_forward_bound(100, 40, 17, 22) == 1860
    assert not refuses(1840, 100, 40, 17, 22)


def test_a_fault_that_never_bound_is_still_refused():
    """d45-pilot-v7 before protocol 0.20: the full offered load got through."""
    assert refuses(2700, 100, 40, 19, 28)


def test_a_fault_binding_exactly_at_the_cap_passes():
    b = A.gateway_forward_bound(100, 40, 17, 22)
    assert not refuses(b, 100, 40, 17, 22)


def test_forwarding_far_less_than_the_bound_passes():
    """An action that refuses work, or an unsaturated gateway. One-sided."""
    assert not refuses(500, 100, 40, 17, 22)


def test_a_fault_at_the_first_epoch_bounds_almost_everything():
    assert A.gateway_forward_bound(100, 40, 1, 22) == 100 + 40 * 20


def test_a_fault_after_the_outcome_bounds_nothing_beyond_the_offered_rate():
    """Onset past the horizon: every serving epoch is charged at the full rate."""
    assert A.gateway_forward_bound(100, 40, 50, 22) == 100 * 21
    assert refuses(100 * 21 + 200, 100, 40, 50, 22)


def test_one_serving_epoch():
    assert A.gateway_forward_bound(100, 40, 1, 2) == 100


def test_no_serving_epochs():
    assert A.gateway_forward_bound(100, 40, 1, 0) == 0
