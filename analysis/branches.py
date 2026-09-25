"""One place that knows what a branch is.

A branch name is a label, not a record. From protocol 0.9 each branch carries a
`scenario.json` with every factor as its own field, and every analysis reads
that file rather than parsing the name — a name cannot say which fault ran, and
inferring it from position is how an analysis ends up describing something other
than what happened.

Runs recorded before 0.9 are still readable, because m2prime-903 remains a
reportable single-scenario result. Their factors are reconstructed from the
matrix manifest and the recorded node state, and the reconstruction is marked
`legacy: true` so nothing can silently mix the two.
"""
import json
import os

LEGACY_SCENARIO = "s00"


def _legacy(path, name, matrix):
    parts = name.split("-")
    if len(parts) != 3:
        raise ValueError(f"cannot read branch name {name!r}")
    anchor_s, action, repeat_s = parts
    anchor = int(anchor_s.lstrip("a"))
    horizon = int(matrix.get("horizon", 0))
    # Before 0.8 the fault was a constant compiled into the compose file, and
    # the node reported it in its capacity state, so it can be recovered.
    onset, severity = 12, 60
    try:
        with open(os.path.join(path, "anchor.json")) as fh:
            cap = json.load(fh)["state"]["edge_capacity"]
        onset = int(cap.get("edge00/degrade_at_epoch", onset))
        severity = int(cap.get("edge00/degraded_serve", severity))
    except (OSError, KeyError, ValueError):
        pass
    return {
        "scenario_id": LEGACY_SCENARIO,
        "fault_type": "D1",
        "fault_onset": onset,
        "fault_severity": severity,
        "workload_level": int(matrix.get("events_per_epoch", 100)),
        "seed": int(matrix.get("master_seed", 0)),
        "sla_ms": int(matrix.get("sla_ms", 0)) or None,
        "anchor": anchor,
        "action": action,
        "repeat": int(repeat_s.lstrip("r")),
        "horizon": horizon,
        "regime": regime_of(anchor, horizon, onset),
        "legacy": True,
    }


def regime_of(anchor, horizon, onset):
    """Which regime the branch sits in, from its own numbers.

    The branch covers epochs `anchor` through `anchor + horizon` inclusive, so
    pre-fault needs the onset strictly after the last of them. Writing this with
    `<=` made a branch whose final epoch carried the fault look pre-fault, and
    the accounting audit caught it: 10 cells of a04 lost 40 events each while
    being called fault-free.
    """
    if onset > anchor + horizon:
        return "pre-fault"
    if onset <= anchor:
        return "post-onset"
    return "spanning"


def read(path, matrix=None):
    """Return the factor record for one branch directory."""
    name = os.path.basename(path.rstrip("/"))
    manifest = os.path.join(path, "scenario.json")
    if os.path.exists(manifest):
        with open(manifest) as fh:
            rec = json.load(fh)
        rec["legacy"] = False
        rec.setdefault("regime", regime_of(rec["anchor"], rec["horizon"],
                                          rec["fault_onset"]))
        return rec
    if matrix is None:
        matrix = {}
    return _legacy(path, name, matrix)


def read_matrix(root):
    try:
        with open(os.path.join(root, "matrix.json")) as fh:
            return json.load(fh)
    except OSError:
        return {}


def cell_key(rec):
    """The replay cell: repeats of this are replays of one prefix."""
    return (rec["scenario_id"], f"a{rec['anchor']:02d}", rec["action"])
