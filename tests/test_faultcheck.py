"""Every way a declared fault can fail to reach the containers.

These are the cases that cost three runs: an edge-only check refusing a healthy
edge that the mechanism declares; the gateway looked up by its compose service
name instead of its node id, so its observables read as absent and were compared
against a default; and the two parameters added with D4 and D5 not checked at
all.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
import faultcheck

D4 = dict(fault_onset=15, fault_severity=40, edge_faulted=1,
          relief_degraded_serve=20, degraded_admit=-1)
D5 = dict(fault_onset=19, fault_severity=60, edge_faulted=0,
          relief_degraded_serve=-1, degraded_admit=40)
D1 = dict(fault_onset=15, fault_severity=40, edge_faulted=1,
          relief_degraded_serve=-1, degraded_admit=-1)

E_FAULTED = {"edge00/degrade_at_epoch": 15, "edge00/degraded_serve": 40}
E_HEALTHY = {"edge00/degrade_at_epoch": 0, "edge00/degraded_serve": -1}
RELIEF_ON = {"edge01/degrade_at_epoch": 15, "edge01/degraded_serve": 20}
RELIEF_OFF = {"edge01/degrade_at_epoch": 0, "edge01/degraded_serve": -1}
GW_ON = {"gw00/degrade_admit_at_epoch": 19, "gw00/degraded_admit": 40}
GW_OFF = {"gw00/degrade_admit_at_epoch": 0, "gw00/degraded_admit": -1}


def anchor(cap, obs=None):
    return {"state": {"edge_capacity": dict(cap)}, "observed": dict(obs or {})}


def test_d4_as_declared_passes():
    assert faultcheck.verify(D4, anchor({**E_FAULTED, **RELIEF_ON})) == []


def test_d5_as_declared_passes():
    """A gateway mechanism declares a HEALTHY edge. Refusing this cost two runs."""
    assert faultcheck.verify(D5, anchor(E_HEALTHY, GW_ON)) == []


def test_d1_as_declared_passes():
    assert faultcheck.verify(D1, anchor(E_FAULTED)) == []


def test_relief_path_that_never_arrived_is_refused():
    """Without it, rerouting stays beneficial and D4 silently becomes D1."""
    bad = faultcheck.verify(D4, anchor({**E_FAULTED, **RELIEF_OFF}))
    assert any("relief path" in b for b in bad)


def test_relief_path_absent_from_the_report_is_refused():
    bad = faultcheck.verify(D4, anchor(E_FAULTED))
    assert any("relief path" in b for b in bad)


def test_gateway_fault_that_never_arrived_is_refused():
    bad = faultcheck.verify(D5, anchor(E_HEALTHY, GW_OFF))
    assert any("gw00" in b for b in bad)


def test_gateway_observable_absent_is_refused_not_defaulted():
    """The defect that produced '(-1, -1)': no node reports it, so say so."""
    bad = faultcheck.verify(D5, anchor(E_HEALTHY, {"gw00/ingress_accepted": 100.0}))
    assert any("no node reports" in b for b in bad)


def test_gateway_found_under_any_node_id():
    """Resolved by suffix: the id is 'gw00', not the compose service 'gateway00'."""
    obs = {"gateway00/degrade_admit_at_epoch": 19, "gateway00/degraded_admit": 40}
    assert faultcheck.verify(D5, anchor(E_HEALTHY, obs)) == []


def test_stale_edge_fault_under_a_gateway_mechanism_is_refused():
    """Otherwise a gateway mechanism runs as an edge mechanism, manifest unchanged."""
    bad = faultcheck.verify(D5, anchor(E_FAULTED, GW_ON))
    assert any("edge00" in b for b in bad)


def test_edge_fault_that_never_arrived_is_refused():
    bad = faultcheck.verify(D1, anchor(E_HEALTHY))
    assert any("edge00" in b for b in bad)


def test_edge_observables_absent_are_refused():
    bad = faultcheck.verify(D1, anchor({}))
    assert any("no node reports" in b for b in bad)


def test_a_fault_declared_nowhere_is_refused():
    rec = dict(fault_onset=15, fault_severity=40, edge_faulted=0,
               relief_degraded_serve=-1, degraded_admit=-1)
    bad = faultcheck.verify(rec, anchor(E_HEALTHY))
    assert any("neither an edge fault nor a gateway fault" in b for b in bad)


def test_a_missing_anchor_state_is_refused():
    assert faultcheck.verify(D1, {}) != []
