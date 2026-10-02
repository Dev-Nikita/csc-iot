"""Verify that the fault a branch RAN is the fault its scenario DECLARED.

One module, because this rule was written twice -- once in the runner and once
in the accounting audit -- and the same defect then had to be found three times:

  * the check was edge-only, so the first branch of a mechanism that faults the
    gateway and leaves every edge healthy was refused for reporting a healthy
    edge, which is what that mechanism declares;
  * the gateway's node was looked up as 'gateway00', the compose SERVICE name,
    while the node's id is 'gw00', so both of its observables read as absent and
    were compared against a default;
  * and the two parameters introduced with D4 and D5 -- the relief path and the
    gateway admission cap -- were not checked anywhere at all.

The rule belongs in one place. A caller that wants it gets it from here.

Two principles, both learned the hard way:

  * A mechanism that declares NO fault on some component must find that
    component HEALTHY. Dropping the comparison instead of inverting it would let
    a stale compose substitution leave a previous scenario's edge fault in place,
    and a gateway mechanism would run as an edge mechanism while its manifest
    still claimed the gateway.
  * An observable the scenario declares and no node reports is a FAILURE, not a
    default. A check that cannot see its subject must say so; compared against a
    placeholder it quietly passes, which is the worse direction of the same bug.
"""

__all__ = ["verify"]


def _pair(src, node, k1, k2, label, bad):
    """The (first, second) values as the node reported them, or None.

    Resolved by key suffix over whatever node published the observable rather
    than by a node id spelled in this module.
    """
    out = []
    for k in (k1, k2):
        hits = [v for key, v in src.items()
                if key == node + "/" + k or key.endswith("/" + k)]
        if not hits:
            bad.append("%s: no node reports %s, so the fault cannot be "
                       "verified at all" % (label, k))
            return None
        out.append(int(hits[0]))
    return tuple(out)


def verify(rec, anchor):
    """Return a list of discrepancies; empty means the branch ran what it declares.

    `rec` is the branch's scenario manifest, `anchor` the parsed anchor.json.
    """
    bad = []
    try:
        cap = anchor["state"]["edge_capacity"]
    except (KeyError, TypeError):
        return ["no edge_capacity in the anchor state to verify the fault"]
    obs = anchor.get("observed") or {}
    onset = int(rec["fault_onset"])

    # The loaded edge, against the declared fault where the mechanism faults an
    # edge and against healthy where it does not.
    exp = ((onset, int(rec["fault_severity"]))
           if int(rec.get("edge_faulted", 1)) else (0, -1))
    ran = _pair(cap, "edge00", "degrade_at_epoch", "degraded_serve", "edge00", bad)
    if ran is not None and ran != exp:
        bad.append("edge00: declared %s but the node ran %s" % (exp, ran))

    # The relief path. D4 exists only because this edge ends up strictly below
    # the loaded one; without the parameter, rerouting stays beneficial and D4
    # silently becomes D1 -- the defect the mechanism was written to remove.
    relief = int(rec.get("relief_degraded_serve", -1))
    if relief >= 0:
        exp = (onset, relief)
        k1, k2 = "edge01/degrade_at_epoch", "edge01/degraded_serve"
        if k1 in cap and k2 in cap:
            ran = (int(cap[k1]), int(cap[k2]))
            if ran != exp:
                bad.append("edge01 (relief path): declared %s but the node ran %s"
                           % (exp, ran))
        else:
            bad.append("edge01 (relief path): the edge reports no degradation "
                       "parameters, so the relief path cannot be verified")

    # The gateway, read from the observed block: an admission cap the operator
    # suffers is an outcome, not structural service capacity.
    gw = int(rec.get("degraded_admit", -1))
    if gw >= 0:
        exp = (onset, gw)
        ran = _pair(obs, "gw00", "degrade_admit_at_epoch", "degraded_admit",
                    "gateway (gw00)", bad)
        if ran is not None and ran != exp:
            bad.append("gateway (gw00): declared %s but the node ran %s" % (exp, ran))

    # A branch that declares a fault nowhere is a healthy run wearing a
    # scenario id.
    if not int(rec.get("edge_faulted", 1)) and gw < 0:
        bad.append("scenario declares neither an edge fault nor a gateway fault")

    return bad
