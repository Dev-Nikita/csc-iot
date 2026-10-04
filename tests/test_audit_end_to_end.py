"""Run audit() itself on synthetic branches.

tests/test_gateway_bound.py covers the arithmetic of the bound. It did not catch
a NameError in the function that CALLS it: extracting the bound removed the
variable the next line still used, and `python -c "import ast; ast.parse(...)"`
is happy with that. A test of a helper is not a test of the code path, and the
defect surfaced only when the audit was run against 1800 real branches.

These fixtures build the smallest branch directory audit() will accept and run
it, so every invariant in the function is at least executed.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
import audit_accounting as A


def branch(*, accepted, served, deferred, residual, by_action, by_fault,
           end_epoch, onset, gw_admit, edge_faulted, action, severity=60,
           relief=-1, regime="post-onset", eligible=0.0, lat_viol=0.0,
           nominal=150.0, edge_onset=0, edge_serve=-1):
    """A branch directory plus its factor record, as audit() expects them."""
    d = tempfile.mkdtemp()
    obs = {
        "gw00/ingress_accepted": float(accepted),
        "gw00/admission_deferred_total": float(deferred),
        "gw00/admission_deferred_by_action_total": float(by_action),
        "gw00/admission_deferred_by_fault_total": float(by_fault),
        "gw00/admission_backlog_depth": float(residual),
        "edge00/served": float(served),
        "edge00/unserved": float(eligible),
        "edge00/unserved_eligible": float(eligible),
        "edge00/sla_violations": 0.0,
        "edge00/wait_sum_epochs": 0.0,
        "edge00/lat_ms_sum": 0.0,
        "edge00/lat_ms_violations": float(lat_viol),
        "edge00/lat_hist_ms_0": float(served),
    }
    cap = {"edge00/serve_per_epoch": nominal,
           "edge00/degrade_at_epoch": edge_onset,
           "edge00/degraded_serve": edge_serve}
    if relief >= 0:
        cap["edge01/degrade_at_epoch"] = onset
        cap["edge01/degraded_serve"] = relief
    json.dump({"state": {"edge_capacity": cap},
               "observed": {"gw00/degrade_admit_at_epoch": onset if gw_admit >= 0 else 0,
                            "gw00/degraded_admit": gw_admit}},
              open(os.path.join(d, "anchor.json"), "w"))
    json.dump({"epoch": end_epoch, "observed": obs},
              open(os.path.join(d, "outcome.json"), "w"))
    rec = {"fault_type": "D5" if not edge_faulted else "D4",
           "fault_onset": onset, "fault_severity": severity,
           "workload_level": 100, "seed": 1, "sla_ms": 750, "anchor": 14,
           "action": action, "repeat": 1, "horizon": 8, "regime": regime,
           "relief_degraded_serve": relief, "degraded_admit": gw_admit,
           "edge_faulted": 1 if edge_faulted else 0,
           "legacy": False, "scenario_id": "s02"}
    return d, rec


def run(**kw):
    d, rec = branch(**kw)
    try:
        return A.audit(d, rec)
    finally:
        shutil.rmtree(d)


D5_AS_RUN = dict(accepted=2100, served=1840, deferred=260, residual=260,
                 by_action=0, by_fault=260, end_epoch=22, onset=17,
                 gw_admit=40, edge_faulted=False, action="NO_OP")


def test_the_refused_d45_matrix_branch_passes_and_the_function_runs():
    """s02-a14-NO_OP: the 228 refusals of d45-matrix-v1, and the NameError."""
    assert run(**D5_AS_RUN) == []


def test_a_dead_gateway_fault_is_still_refused():
    """The whole offered load forwarded: protocol 0.20's defect."""
    bad = run(**{**D5_AS_RUN, "accepted": 2700, "served": 2700,
                 "deferred": 0, "residual": 0, "by_fault": 0})
    assert any("gateway fault had no effect" in b for b in bad)


def test_no_op_charged_with_action_deferral_is_refused():
    bad = run(**{**D5_AS_RUN, "by_action": 260, "by_fault": 0})
    assert any("C(NO_OP) = 0 by definition" in b for b in bad)


def test_a_split_that_does_not_sum_is_refused():
    bad = run(**{**D5_AS_RUN, "by_action": 0, "by_fault": 100})
    assert any("by fault !=" in b for b in bad)


def test_deferral_with_no_limiter_at_all_is_refused():
    """No gateway fault, no THROTTLE: nothing could have deferred work."""
    bad = run(**{**D5_AS_RUN, "gw_admit": -1, "edge_faulted": True,
                 "by_fault": 0, "by_action": 0, "deferred": 260,
                 "edge_onset": 17, "edge_serve": 60})
    assert any("nothing limiting admission" in b for b in bad)


def test_more_work_accounted_for_than_accepted_is_refused():
    """Invariant 1, the one that caught protocol 0.7."""
    bad = run(**{**D5_AS_RUN, "served": 2100, "eligible": 500})
    assert any("> accepted" in b for b in bad)


def test_a_d4_branch_runs_through_the_edge_bound():
    assert run(accepted=2700, served=1860, deferred=0, residual=0,
               by_action=0, by_fault=0, end_epoch=22, onset=17, gw_admit=-1,
               edge_faulted=True, action="NO_OP", severity=40, relief=20,
               edge_onset=17, edge_serve=40, eligible=840) == []


def test_a_d4_branch_whose_edge_fault_did_nothing_is_refused():
    bad = run(accepted=2700, served=2700, deferred=0, residual=0,
              by_action=0, by_fault=0, end_epoch=22, onset=17, gw_admit=-1,
              edge_faulted=True, action="NO_OP", severity=40, relief=20,
              edge_onset=17, edge_serve=40)
    assert any("declared degradation had no effect" in b for b in bad)
