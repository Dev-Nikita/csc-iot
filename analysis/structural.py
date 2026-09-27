#!/usr/bin/env python3
"""A structural predictor of J_obs(s,a): queueing arithmetic, no fitted parameters.

Written before the associative challenger was evaluated, so that it cannot be
tuned against it -- the same reason the resolvability gate and the budget rule
were fixed in advance.

It sees exactly what the challenger sees: the permitted decision-time
features, which exclude the fault schedule by construction. What it additionally
uses are things the operator knows because it configured them -- the epoch
period, the emission window, the horizon it is planning over, the frozen latency
budget, and the semantics of its own actions.

THREE ASSUMPTIONS, stated here because they belong in the paper and not only in
the code.

1. Capacity is inferred from throughput, and only where the queue is non-empty.
   With an empty queue, throughput equals the arrival rate and says nothing about
   capacity, so nominal capacity is used. This is honest and it is also weak: the
   only throughput available is cumulative, so it averages healthy and degraded
   epochs and therefore UNDER-estimates the damage of a fault that started
   recently. The bias is one-directional and is reported.

   The observable state cannot do better. With cumulative served work and the
   current queue depth, served + queued = arrivals * epochs holds identically,
   so the onset and the severity of a degradation are not separately
   identifiable. Recovering them needs a windowed throughput, which the node
   does not yet report. That is a one-line addition and a re-run, not a
   modelling problem, and it is the first thing to change if this model loses on
   magnitude rather than on ranking.

2. The shape of the per-event latency distribution is taken as observed; only its
   shift is computed, from queueing arithmetic. Service happens on epoch
   boundaries, so an event that waits w epochs is displaced by (w - observed mean
   wait) * period relative to the events already measured.

3. An edge with no history -- edge01 before anything is routed to it -- is
   assumed to behave like the edge that does have history. An operator would
   assume the same of an identically deployed node, and the alternative is to
   refuse to predict rerouting at all.
"""
import argparse
import csv
import glob
import json
import os
import sys

import branches
import features

W_FAILURE, W_LATENCY, W_COST = 0.6, 0.2, 0.2
EDGES = features.EDGES


def _hist(obs, edge=None):
    out = {}
    for k, v in obs.items():
        if features.HIST not in k:
            continue
        if edge and not k.startswith(edge + "/"):
            continue
        out[int(k.split(features.HIST)[1])] = out.get(int(k.split(features.HIST)[1]), 0) + v
    return out


def _fraction_above(hist, threshold_ms, shift_ms):
    total = sum(hist.values())
    if total == 0:
        return 0.0
    above = sum(v for b, v in hist.items() if b + shift_ms >= threshold_ms)
    return above / total


def _sum(obs, suffix):
    return sum(v for k, v in obs.items() if k.endswith(suffix))


def predict(branch_dir, action, horizon, period_ms, sla_ms,
            latency_max_ms, latency_max_epochs, throttle_limit=50,
            reroute_to="edge01"):
    """Predicted J_obs for taking `action` at this anchor. Lower is better.

    J_obs is cumulative over the whole branch, so the prediction starts from the
    anchor's measured totals and adds only what the horizon contributes. The
    structural content is therefore confined to the horizon; the prefix is
    measurement, identical for every action at the same anchor. This is the
    right decomposition: an action cannot change the past, and the quantity the
    controller must rank is exactly the branch-level objective the paper scores.
    """
    f = features.extract(branch_dir)
    with open(os.path.join(branch_dir, "anchor.json")) as fh:
        obs = json.load(fh)["observed"]

    lam = f["system_accepted_last_epoch"]
    if lam <= 0:
        raise ValueError("no arrival rate observable at this anchor")

    # --- measured prefix, in the units jobs.py uses -------------------------
    offered0 = _sum(obs, "/ingress_accepted")
    if offered0 <= 0:
        raise ValueError("no offered work measured at the anchor")
    served0 = _sum(obs, "/served")
    viol0 = _sum(obs, "/lat_ms_violations")
    lat_sum0 = _sum(obs, "/lat_ms_sum")
    wait_sum0 = _sum(obs, "/wait_sum_epochs")
    deferred0 = _sum(obs, "/admission_deferred_total")

    # --- where work goes, and with what capacity ---------------------------
    target = EDGES[int(f["gw00_routes_to_idx"])] if f["gw00_routes_to_idx"] >= 0 \
        else EDGES[0]
    if action == "REROUTE":
        target = reroute_to
    cap, queue = {}, {}
    for e in EDGES:
        q = f[f"{e}_inbox_len"]
        nominal = f[f"{e}_nominal_serve"] or 1.0
        rate = f[f"{e}_served_last_epoch"]
        # Assumption 1.
        cap[e] = min(nominal, rate) if q > 0 and rate > 0 else nominal
        queue[e] = [(0.0, q)] if q > 0 else []   # (epochs already waited, count)

    admit = float("inf") if action != "THROTTLE" else float(throttle_limit)
    backlog = f["gw00_backlog_depth"] + f["gw01_backlog_depth"]

    served_h = 0.0
    served_waits = []          # (wait_epochs, count) for events served in the horizon
    deferred_h = 0.0

    for _ in range(int(horizon)):
        from_backlog = min(backlog, admit)
        backlog -= from_backlog
        room = admit - from_backlog
        from_new = min(lam, room)
        deferred_now = lam - from_new
        backlog += deferred_now
        deferred_h += deferred_now
        arrivals = from_backlog + from_new

        for e in EDGES:
            queue[e] = [(w + 1.0, n) for w, n in queue[e]]
        queue[target].append((1.0, arrivals))

        for e in EDGES:
            budget = cap[e]
            kept = []
            for w, n in queue[e]:
                take = min(n, budget)
                if take > 0:
                    served_h += take
                    served_waits.append((w, take))
                    budget -= take
                if n - take > 0:
                    kept.append((w, n - take))
            queue[e] = kept

    # --- assemble the branch totals ----------------------------------------
    offered = offered0 + lam * horizon
    served = served0 + served_h
    undelivered = sum(n for e in EDGES for _, n in queue[e]) + backlog

    # Latency: observed shape, computed shift (assumption 2).
    hist = _hist(obs)
    observed_mean_wait = (wait_sum0 / served0) if served0 > 0 else 1.0
    viol_h = 0.0
    for w, n in served_waits:
        shift = (w - observed_mean_wait) * period_ms
        viol_h += n * _fraction_above(hist, sla_ms, shift)

    y = (viol0 + viol_h + undelivered) / offered
    # jobs.py scores the measured end-to-end latency, so the model must too.
    base_mean = (sum(b * v for b, v in hist.items()) / sum(hist.values())) \
        if sum(hist.values()) > 0 else 0.0
    lat_sum = lat_sum0 + sum(
        n * max(base_mean + (w - observed_mean_wait) * period_ms, 0.0)
        for w, n in served_waits)
    mean_lat_ms = (lat_sum / served) if served else float(latency_max_ms)
    l_tilde = min(max(mean_lat_ms / latency_max_ms, 0.0), 1.0)
    disruption = min(max((deferred0 + deferred_h + undelivered) / offered, 0.0), 1.0)
    return W_FAILURE * min(max(y, 0.0), 1.0) + W_LATENCY * l_tilde + W_COST * disruption


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("jobs_csv")
    ap.add_argument("--period-ms", type=float, default=300.0)
    ap.add_argument("--latency-max-ms", type=float, default=3000.0)
    ap.add_argument("--latency-max-epochs", type=float, default=14.0)
    ap.add_argument("--out")
    args = ap.parse_args()

    truth = {r["branch"]: float(r["J_obs"]) for r in csv.DictReader(open(args.jobs_csv))}
    matrix = branches.read_matrix(args.root)
    pattern = "s*-a*" if glob.glob(os.path.join(args.root, "s*-a*")) else "a*"
    rows = []
    for d in sorted(glob.glob(os.path.join(args.root, pattern))):
        name = os.path.basename(d)
        if name not in truth or not os.path.exists(os.path.join(d, "anchor.json")):
            continue
        rec = branches.read(d, matrix)
        try:
            jhat = predict(d, rec["action"], rec["horizon"], args.period_ms,
                           rec["sla_ms"], args.latency_max_ms,
                           args.latency_max_epochs)
        except ValueError as exc:
            print(f"  {name}: {exc}", file=sys.stderr)
            continue
        rows.append({"branch": name, "scenario": rec["scenario_id"],
                     "anchor": f"a{rec['anchor']:02d}", "action": rec["action"],
                     "regime": rec["regime"], "J_hat": jhat,
                     "J_obs": truth[name]})
    if not rows:
        sys.exit("no branches predicted")
    err = [abs(r["J_hat"] - r["J_obs"]) for r in rows]
    print(f"{len(rows)} branches")
    print(f"  MAE of the structural prediction {sum(err)/len(err):.4f}")
    for reg in ("pre-fault", "spanning", "post-onset"):
        sub = [r for r in rows if r["regime"] == reg]
        if sub:
            e = [abs(r["J_hat"] - r["J_obs"]) for r in sub]
            print(f"    {reg:11s} n={len(sub):4d}  MAE {sum(e)/len(e):.4f}")
    if args.out:
        with open(args.out, "w") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
