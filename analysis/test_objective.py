"""Tests for the objective, on branches whose answer is known by construction.

Written after three 900-branch matrices were discarded to defects in this
arithmetic. Each test states the property in terms of what the system did, so
a failure names the meaning that broke, not the line that changed.

Run: pytest analysis/test_objective.py
"""
import pytest

from jobs import W_COST, W_FAILURE, W_LATENCY, terms

LMAX_EPOCHS, LMAX_MS = 14, 3000.0


def branch(accepted, served, eligible=0.0, residual=0.0, deferred=0.0,
           lat_viol=0.0, sla_viol=0.0, mean_lat=400.0, mean_wait=1.0):
    return {
        "gw00/ingress_accepted": accepted,
        "gw00/admission_deferred_total": deferred,
        "gw00/admission_backlog_depth": residual,
        "edge00/served": served,
        "edge00/unserved": eligible,
        "edge00/unserved_eligible": eligible,
        "edge00/sla_violations": sla_viol,
        "edge00/wait_sum_epochs": mean_wait * served,
        "edge00/lat_ms_sum": mean_lat * served,
        "edge00/lat_ms_violations": lat_viol,
    }


def j(t):
    return W_FAILURE * t["Y_ms"] + W_LATENCY * t["L_tilde_ms"] + W_COST * t["disruption"]


def test_a_healthy_branch_scores_no_failure_and_no_cost():
    """Everything offered was served inside the budget: Y and cost are zero.

    This is the case that protocol 0.7 got wrong. It scored Y = 0.125.
    """
    t = terms(branch(accepted=800, served=800), LMAX_EPOCHS, LMAX_MS)
    assert t["offered"] == 800
    assert t["Y_ms"] == 0.0
    assert t["disruption"] == 0.0
    assert j(t) == pytest.approx(W_LATENCY * 400.0 / LMAX_MS)


def test_work_never_delivered_counts_as_failure():
    t = terms(branch(accepted=800, served=700, eligible=100), LMAX_EPOCHS, LMAX_MS)
    assert t["Y_ms"] == pytest.approx(100 / 800)


def test_a_gateway_backlog_left_standing_counts_as_failure():
    """Undelivered is undelivered wherever it was stranded."""
    t = terms(branch(accepted=800, served=700, residual=100), LMAX_EPOCHS, LMAX_MS)
    assert t["Y_ms"] == pytest.approx(100 / 800)


def test_refusing_work_does_not_shrink_the_denominator():
    """The defect fixed in protocol 0.5.

    A throttled branch that refused 300 of 800 events and served the rest on
    time must be scored over all 800, not over the 500 it let through. Scored
    on the subset, it would look identical to doing nothing.
    """
    throttled = terms(branch(accepted=800, served=800, deferred=300),
                      LMAX_EPOCHS, LMAX_MS)
    idle = terms(branch(accepted=800, served=800), LMAX_EPOCHS, LMAX_MS)
    assert throttled["offered"] == 800
    assert throttled["disruption"] == pytest.approx(300 / 800)
    assert j(throttled) > j(idle)


def test_deferral_is_charged_even_when_the_work_is_later_drained():
    """Work delayed and then served was still displaced."""
    t = terms(branch(accepted=800, served=800, deferred=200, residual=0),
              LMAX_EPOCHS, LMAX_MS)
    assert t["disruption"] == pytest.approx(200 / 800)


def test_a_missing_observable_is_refused_not_substituted():
    obs = branch(accepted=800, served=800)
    del obs["edge00/unserved_eligible"]
    with pytest.raises(ValueError, match="unserved_eligible"):
        terms(obs, LMAX_EPOCHS, LMAX_MS)


def test_inconsistent_accounting_is_refused():
    """served + undelivered may not exceed what the gateway accepted."""
    with pytest.raises(ValueError, match="inconsistent"):
        terms(branch(accepted=800, served=800, eligible=100),
              LMAX_EPOCHS, LMAX_MS)


def test_the_objective_is_lower_is_better_and_bounded():
    best = j(terms(branch(accepted=800, served=800, mean_lat=0.0),
                   LMAX_EPOCHS, LMAX_MS))
    worst = j(terms(branch(accepted=800, served=0, eligible=800,
                           deferred=800, mean_lat=LMAX_MS),
                    LMAX_EPOCHS, LMAX_MS))
    assert best == pytest.approx(0.0)
    assert worst == pytest.approx(1.0)
    assert best < worst


def test_a_branch_offered_nothing_is_undefined_rather_than_perfect():
    with pytest.raises(ValueError, match="no work"):
        terms(branch(accepted=0, served=0), LMAX_EPOCHS, LMAX_MS)
