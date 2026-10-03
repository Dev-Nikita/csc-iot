"""What the gateway's admission limit must be under THROTTLE.

D5 degrades the gateway's own admission capacity, and the node applies whichever
of the fault and the action is tighter. The check compared the observed limit
against the action's value alone and failed all 12 THROTTLE branches of every D5
scenario for behaving exactly as designed.

The fault must still be allowed to bind only once it has started, and the action
must still be checked where there is no fault at all -- that is the direction
that catches an action which never reached the gateway.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
import m2prime_report as R


def rec(action, limit, *, epoch=26, onset=-1, gw=-1, route="edge01"):
    return {
        "action": action,
        "branch": {"action_ack": {"applied": True, "action": action}},
        "outcome": {"epoch": epoch,
                    "state": {"rate_limits": {"gw00/admit": limit},
                              "routing": {"gw00/edge": route}}},
        "scenario": {"fault_onset": onset, "degraded_admit": gw},
    }


def test_no_fault_and_the_action_applied():
    assert R.mutation_error(rec("THROTTLE", 50)) is None


def test_no_fault_and_the_action_never_reached_the_gateway():
    err = R.mutation_error(rec("THROTTLE", 100))
    assert err and "expected 50" in err


def test_gateway_fault_tighter_than_the_action_binds():
    """s02: the fault admits 40, the action asks 50. 40 is correct."""
    assert R.mutation_error(rec("THROTTLE", 40, onset=19, gw=40)) is None


def test_gateway_fault_much_tighter_binds():
    """s04: the fault admits 27."""
    assert R.mutation_error(rec("THROTTLE", 27, onset=20, gw=27)) is None


def test_the_action_still_binds_when_it_is_the_tighter_one():
    """A fault admitting 80 must not excuse an action that asks 50."""
    assert R.mutation_error(rec("THROTTLE", 50, onset=19, gw=80)) is None
    err = R.mutation_error(rec("THROTTLE", 80, onset=19, gw=80))
    assert err and "expected 50" in err


def test_a_fault_before_its_onset_does_not_excuse_the_action():
    """Read at epoch 5, onset 19: the fault has not started, 50 is required."""
    err = R.mutation_error(rec("THROTTLE", 40, epoch=5, onset=19, gw=40))
    assert err and "expected 50" in err


def test_the_message_names_both_limits():
    err = R.mutation_error(rec("THROTTLE", 50, onset=19, gw=40))
    assert err and "the tighter of the two binds" in err and "40" in err


def test_reroute_is_untouched():
    assert R.mutation_error(rec("REROUTE", 100)) is None
    err = R.mutation_error(rec("REROUTE", 100, route="edge00"))
    assert err and "expected 'edge01'" in err


def test_no_op_is_untouched():
    assert R.mutation_error(rec("NO_OP", 100)) is None


def test_a_missing_acknowledgement_still_fails():
    r = rec("THROTTLE", 50)
    r["branch"]["action_ack"]["applied"] = False
    assert R.mutation_error(r) == "missing verified action acknowledgement"
