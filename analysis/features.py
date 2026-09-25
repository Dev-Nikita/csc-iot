"""What the controller is allowed to see at decision time.

Everything here comes from `anchor.json` — the state and the observed counters as
they stood when the action was chosen. Nothing comes from `outcome.json`, which
is the future.

Two kinds of thing are forbidden, for different reasons.

*The fault schedule* — onset, severity, mechanism, and the node's reported
degradation configuration. A controller in a running system does not know when
its next fault will arrive. A model given the schedule reports the schedule, and
through protocol 0.7 every branch shared one schedule, so this was not a
hypothetical.

*The scenario's identity* — its id and its seed. They index the answer.

The nominal capacity of an edge is NOT forbidden: an operator knows the size of
the node it deployed. What it may not know is when that capacity will drop.
"""
import json
import os

FORBIDDEN = frozenset({
    "scenario_id", "seed",
    "fault_type", "fault_onset", "fault_severity",
    "degrade_at_epoch", "degraded_serve", "fault_phase",
    # The horizon and the regime are properties of the experiment design, not
    # observations. The regime in particular is computed FROM the onset.
    "regime", "horizon",
})

# Substrings that must never appear in a feature name. Checked as well as the
# exact set, because leakage arrives renamed.
FORBIDDEN_SUBSTRINGS = ("onset", "severity", "degrade", "fault", "scenario",
                        "regime", "seed")

EDGES = ("edge00", "edge01", "edge02")
GATEWAYS = ("gw00", "gw01")
HIST = "lat_hist_ms_"


def _hist_quantile(hist, q):
    """Per-event latency quantile from the 25 ms histogram, upper bin edge."""
    total = sum(hist.values())
    if total == 0:
        return 0.0
    acc = 0.0
    for b in sorted(hist):
        acc += hist[b]
        if acc >= q * total:
            return float(b + 25)
    return float(max(hist) + 25)


def extract(branch_dir):
    """Decision-time features for one branch. Reads anchor.json only."""
    with open(os.path.join(branch_dir, "anchor.json")) as fh:
        doc = json.load(fh)
    state, obs = doc["state"], doc.get("observed") or {}
    epoch = float(state.get("logical_tick", 0)) or 1.0
    f = {}

    # Elapsed logical time. Kept deliberately: the time-only baseline f(t,a) is
    # exactly this feature, and its whole purpose is to measure how much of any
    # model's skill comes from the clock. Excluding it would hide that.
    f["epoch"] = epoch

    queues = state.get("queues") or {}
    caps = state.get("edge_capacity") or {}
    for e in EDGES:
        q = queues.get(f"{e}/inbox") or {}
        f[f"{e}_inbox_len"] = float(q.get("length", 0))
        served = float(obs.get(f"{e}/served", 0.0))
        f[f"{e}_served"] = served
        f[f"{e}_served_per_epoch"] = served / epoch
        f[f"{e}_undelivered"] = float(obs.get(f"{e}/unserved_eligible", 0.0))
        f[f"{e}_lat_violations"] = float(obs.get(f"{e}/lat_ms_violations", 0.0))
        f[f"{e}_deadline_misses"] = float(obs.get(f"{e}/sla_violations", 0.0))
        lat_sum = float(obs.get(f"{e}/lat_ms_sum", 0.0))
        f[f"{e}_lat_mean_ms"] = lat_sum / served if served else 0.0
        f[f"{e}_lat_max_ms"] = float(obs.get(f"{e}/lat_ms_max", 0.0))
        wait = float(obs.get(f"{e}/wait_sum_epochs", 0.0))
        f[f"{e}_wait_mean_epochs"] = wait / served if served else 0.0
        hist = {int(k.split(HIST)[1]): v for k, v in obs.items()
                if k.startswith(f"{e}/") and HIST in k}
        for name, q_ in (("p50", 0.50), ("p90", 0.90), ("p99", 0.99)):
            f[f"{e}_lat_{name}_ms"] = _hist_quantile(hist, q_)
        # Nominal size of the node, which an operator knows. Never the schedule
        # by which it will shrink.
        f[f"{e}_nominal_serve"] = float(caps.get(f"{e}/serve_per_epoch", 0.0))
        nominal = f[f"{e}_nominal_serve"]
        # The observable trace of a capacity loss: throughput below nominal.
        f[f"{e}_serve_deficit"] = (nominal - served / epoch) / nominal if nominal else 0.0

    limits = state.get("rate_limits") or {}
    for g in GATEWAYS:
        acc = float(obs.get(f"{g}/ingress_accepted", 0.0))
        f[f"{g}_accepted"] = acc
        f[f"{g}_accepted_per_epoch"] = acc / epoch
        f[f"{g}_backlog_depth"] = float(obs.get(f"{g}/admission_backlog_depth", 0.0))
        f[f"{g}_deferred_total"] = float(obs.get(f"{g}/admission_deferred_total", 0.0))
        f[f"{g}_admit_limit"] = float(limits.get(f"{g}/admit", -1.0))

    routing = state.get("routing") or {}
    for g in GATEWAYS:
        target = routing.get(f"{g}/edge", "")
        f[f"{g}_routes_to_idx"] = float(EDGES.index(target)) if target in EDGES else -1.0

    total_acc = sum(f[f"{g}_accepted"] for g in GATEWAYS)
    total_served = sum(f[f"{e}_served"] for e in EDGES)
    f["system_undelivered_share"] = ((total_acc - total_served) / total_acc
                                     if total_acc else 0.0)
    f["system_accepted_per_epoch"] = total_acc / epoch

    _assert_clean(f)
    return f


def _assert_clean(f):
    for name in f:
        low = name.lower()
        if low in FORBIDDEN:
            raise AssertionError(f"forbidden feature emitted: {name}")
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in low:
                raise AssertionError(
                    f"feature {name!r} contains the forbidden substring {bad!r}")


def feature_names(branch_dir):
    return sorted(extract(branch_dir))


TIME_ONLY = ("epoch",)
