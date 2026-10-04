"""C(a) composed from the components that are actually measured.

Until protocol 0.25 only disruption was instrumented, and the calibration split
reported C(NO_OP) 0.000, C(REROUTE) 0.000, C(THROTTLE) 1.000 -- the objective
declared rerouting free. It is not: REROUTE recruits an edge that was idle. On
three matrices REROUTE then won almost every contrast, which is a property of
the instrumentation and not of the action.

The property that matters most here is the last test: with the new observables
absent, C must equal disruption exactly, so no figure recorded before 0.25 moves
under a definition it was not scored with.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
import jobs


def observed(*, cpu=None, bus=None, served=2000.0, unserved=700.0,
             accepted=2700.0, deferred=0.0, by_action=0.0):
    o = {
        "gw00/ingress_accepted": accepted,
        "gw00/admission_deferred_total": deferred,
        "gw00/admission_deferred_by_action_total": by_action,
        "gw00/admission_deferred_by_fault_total": deferred - by_action,
        "gw00/admission_backlog_depth": 0.0,
        "edge00/served": served, "edge00/unserved": unserved,
        "edge00/unserved_eligible": unserved, "edge00/sla_violations": 0.0,
        "edge00/wait_sum_epochs": served, "edge00/lat_ms_sum": served * 450.0,
        "edge00/lat_ms_violations": 0.0, "edge00/lat_hist_ms_00000": served,
    }
    if cpu is not None:
        for n, usec in cpu.items():
            o[f"{n}/has_cpu_accounting"] = 1.0
            o[f"{n}/cpu_usec_total"] = usec
    if bus is not None:
        for n, by in bus.items():
            o[f"{n}/has_bus_accounting"] = 1.0
            o[f"{n}/bus_bytes_out_total"] = by
    return o


def t(**kw):
    return jobs.terms(observed(**kw), 14, 750, end_epoch=22, period_ms=300.0)


def test_without_the_new_observables_cost_is_exactly_disruption():
    """No figure recorded before 0.25 moves under a definition it never had."""
    r = t()
    assert r["cost"] == r["disruption"]
    assert r["cost_components_measured"] == 1.0


def test_an_absent_component_is_nan_not_zero():
    r = t()
    assert math.isnan(r["resource"]) and math.isnan(r["bandwidth"])


def test_cpu_alone_adds_one_component():
    r = t(cpu={"gw00": 900000.0, "edge00": 1800000.0})
    assert r["cost_components_measured"] == 2.0
    # mean of disruption and resource
    assert abs(r["cost"] - (r["disruption"] + r["resource"]) / 2) < 1e-12


def test_recruiting_a_second_edge_costs_more_than_leaving_it_idle():
    """The whole point of the component.

    Under NO_OP edge01 idles at a baseline. Under REROUTE it serves, while
    edge00 still drains the queue it already holds, so the TOTAL CPU charged to
    the service tier rises. The first version of the normaliser divided by the
    number of nodes that answered, which made this case come out cheaper rather
    than dearer -- the same bias as the zero it replaced.
    """
    idle = t(cpu={"gw00": 900000.0, "edge00": 1800000.0, "edge01": 20000.0})
    busy = t(cpu={"gw00": 900000.0, "edge00": 1500000.0, "edge01": 900000.0})
    assert busy["resource"] > idle["resource"]


def test_resource_is_unmeasured_without_a_period():
    r = jobs.terms(observed(cpu={"gw00": 900000.0}), 14, 750,
                   end_epoch=22, period_ms=None)
    assert math.isnan(r["resource"])


def test_resource_is_unmeasured_without_an_end_epoch():
    r = jobs.terms(observed(cpu={"gw00": 900000.0}), 14, 750,
                   end_epoch=None, period_ms=300.0)
    assert math.isnan(r["resource"])


def test_a_silent_node_makes_the_component_unmeasured_rather_than_low():
    """Against a fixed denominator a silent node understates the total."""
    o = observed(cpu={"gw00": 900000.0})
    o["edge00/has_cpu_accounting"] = 0.0
    o["edge00/cpu_usec_total"] = 0.0
    r = jobs.terms(o, 14, 750, end_epoch=22, period_ms=300.0)
    assert math.isnan(r["resource"])


def test_every_component_stays_in_the_unit_interval():
    r = t(cpu={"gw00": 10**12}, bus={"gw00": 10**12})
    assert 0.0 <= r["resource"] <= 1.0 and 0.0 <= r["bandwidth"] <= 1.0
    assert 0.0 <= r["cost"] <= 1.0


def test_added_latency_is_excluded_by_argument_and_named_as_such():
    assert "added_latency" in jobs.COST_COMPONENT_EXCLUDED_BY_ARGUMENT
    assert "added_latency" not in jobs.COST_COMPONENTS_MEASURED
