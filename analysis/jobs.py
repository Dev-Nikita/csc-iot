#!/usr/bin/env python3
"""The manuscript's observed objective J_obs, computed per branch.

    J_obs(a) = 0.6 Y^a + 0.2 L~^a + 0.2 C_obs^a          (lower is better)

Every term is read from what a branch DID. No model output enters it; if one
did, the reference ranking would contain the prediction it exists to test.

    Y      agreement violations as a fraction of offered work
           (an event whose waiting time exceeds the declared budget violates it;
           work still unserved at the horizon violates it as well -- excluding it
           would score a controller that simply stopped serving as perfect)

    L~     mean waiting time in epochs, normalised by a declared calibration
           maximum and clipped to [0,1]. The normaliser is not inferred from the
           runs being compared: doing so would rescale the objective with every
           new data set.

    C_obs  realised cost of the action. The paper defines it over added latency,
           resource use, bandwidth and disruption. This testbed currently
           measures DISRUPTION only -- work deferred or moved by the action --
           so the value is partial and this script refuses to emit J_obs unless
           --allow-partial-cost says the caller knows it. Resource and bandwidth
           need per-container statistics that are not yet recorded; that is an
           instrumentation gap, not a term to be quietly dropped.

Weights are frozen in EXPERIMENT_PROTOCOL and are not tuned here.
"""
import argparse
import glob
import json
import os
import sys

import branches


def median(values):
    """Local, because analysis/statistics.py shadows the stdlib module here."""
    v = sorted(values)
    n = len(v)
    if n == 0:
        return 0.0
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def quantile(values, p):
    """The p-quantile by nearest rank; no interpolation, no scipy."""
    v = sorted(values)
    if not v:
        return 0.0
    i = min(int(p * (len(v) - 1) + 0.5), len(v) - 1)
    return v[i]

W_FAILURE, W_LATENCY, W_COST = 0.6, 0.2, 0.2
SNR_GATE = 3.0  # preregistered in EXPERIMENT_PROTOCOL; applied as written
# Protocol 0.25. Three of the four declared components are now measured. The
# fourth, added_latency, is deliberately NOT charged here: the latency an action
# imposes is already the L~ term of the objective, and charging it again in C
# would count one effect twice. That is an argument, not an omission, and it is
# stated rather than left as a silent zero.
COST_COMPONENTS_MEASURED = ("disruption", "resource", "bandwidth")
COST_COMPONENT_EXCLUDED_BY_ARGUMENT = ("added_latency",)

# Declared normalisers for the two new components. Neither depends on the action
# taken, which is the only property the comparison needs: C(a) must be
# comparable across the actions at ONE decision point, and `offered`, the epoch
# period and the container count are identical across them by construction. The
# absolute level is therefore a ratio to a declared reference, not a physical
# absolute, and the paper says so.
HOPS_REF = 2            # gateway -> edge, edge -> telemetry
ENVELOPE_REF_BYTES = 512

# The service tier of the declared topology: gw00, gw01, edge00, edge01, edge02.
# The resource normaliser is this FIXED count, not the number of nodes that
# happened to do work. Dividing by the nodes that reported turned the component
# into a mean utilisation, which dilutes rather than charges: recruiting a second
# edge added a node to the numerator and to the denominator at once, so the one
# action the component exists to price came out no dearer. That is the same bias
# as leaving it at zero, one floor further down, and a fixture caught it.
SERVICE_TIER_NODES = 5
COST_COMPONENTS_DECLARED = ("added_latency", "resource", "bandwidth", "disruption")


def dispersion(values):
    """Q0.95 of all pairwise absolute differences within a cell."""
    d = sorted(abs(a - b) for i, a in enumerate(values) for b in values[i + 1:])
    if not d:
        return 0.0
    idx = min(int(0.95 * (len(d) - 1) + 0.5), len(d) - 1)
    return d[idx]


def _resource_and_bandwidth(observed, offered, end_epoch, period_ms):
    """The measured RESOURCE and BANDWIDTH components of C(a), or None each.

    resource  mean CPU utilisation of the service tier over the branch, from each
              container's own cgroup accounting. An edge that sits idle under the
              current routing and is recruited by REROUTE shows up here and
              nowhere else -- which is why REROUTE's cost read 0.000 for every
              run up to protocol 0.24.
    bandwidth encoded envelope bytes published on the bus, against a declared
              reference. A lower bound on wire bytes: transport framing, headers
              and retransmissions are not counted, and that is stated.

    Either is None when the nodes did not report it. None is not zero: the
    caller refuses to score a component it cannot see.
    """
    nodes = {k.split("/", 1)[0] for k in observed if "/" in k}

    resource = None
    cpu_nodes = [n for n in nodes
                 if observed.get(f"{n}/has_cpu_accounting", 0.0) >= 1.0]
    silent = [n for n in nodes
              if f"{n}/has_cpu_accounting" in observed
              and observed[f"{n}/has_cpu_accounting"] < 1.0]
    # All or nothing. A node present in the report but silent about its own CPU
    # would understate the total against a fixed denominator, and a cost term
    # that is quietly low is the defect this component was added to remove.
    if cpu_nodes and not silent and end_epoch and period_ms:
        cpu_usec = sum(observed.get(f"{n}/cpu_usec_total", 0.0) for n in cpu_nodes)
        wall_usec = max(0, end_epoch - 1) * float(period_ms) * 1000.0
        if wall_usec > 0:
            resource = min(max(cpu_usec / (SERVICE_TIER_NODES * wall_usec), 0.0), 1.0)

    bandwidth = None
    bus_nodes = [n for n in nodes
                 if observed.get(f"{n}/has_bus_accounting", 0.0) >= 1.0]
    if bus_nodes and offered > 0:
        by = sum(observed.get(f"{n}/bus_bytes_out_total", 0.0) for n in bus_nodes)
        ref = offered * HOPS_REF * ENVELOPE_REF_BYTES
        bandwidth = min(max(by / ref, 0.0), 1.0)

    return resource, bandwidth


def terms(observed, latency_max_epochs, latency_max_ms, end_epoch=None,
          period_ms=None):
    served = sum(v for k, v in observed.items() if k.endswith("/served"))
    if not any(k.endswith("/unserved_eligible") for k in observed):
        # This fallback used to exist and was silent. It cost two full 900-branch
        # runs: the edge computed the eligible count and never reported it, so
        # every branch was scored on the raw inbox length while the gateway
        # excluded the same events from the denominator. A healthy branch with
        # zero SLA violations scored Y = 0.125. A missing observable is now a
        # refusal, not a substitution.
        raise ValueError(
            "no unserved_eligible in observed: the edge binary does not report "
            "the service-opportunity rule, so the numerator and the denominator "
            "would cover different sets of events. Rebuild with protocol 0.7.")
    unserved = sum(v for k, v in observed.items() if k.endswith("/unserved_eligible"))
    violations = sum(v for k, v in observed.items() if k.endswith("/sla_violations"))
    wait_sum = sum(v for k, v in observed.items() if k.endswith("/wait_sum_epochs"))

    # The denominator is the work the SYSTEM was offered, measured at the
    # gateway, not the work that happened to reach an edge. Under THROTTLE the
    # two differ by construction: refused work never reaches an edge at all, so
    # an edge-side denominator shrinks exactly in proportion to how much the
    # action refused, and the action is scored on the subset it let through.
    accepted = sum(v for k, v in observed.items() if k.endswith("/ingress_accepted"))
    residual = sum(v for k, v in observed.items() if k.endswith("/admission_backlog_depth"))
    deferred = sum(v for k, v in observed.items() if k.endswith("/admission_deferred_total"))
    gateway_denominator = accepted > 0
    if gateway_denominator:
        offered = accepted
    else:
        # Branches recorded before the gateway reported its outcomes. Say so
        # rather than mixing two denominators inside one comparison.
        offered = served + unserved
        residual = 0.0
        deferred = 0.0
    if offered == 0:
        raise ValueError("no work was offered in this branch; J_obs is undefined")

    # Work the branch accepted and never delivered: queued at the edge, or
    # still sitting in the gateway's admission backlog when the run ended.
    undelivered = unserved + residual

    # The numerator and the denominator must cover the same events. If served
    # plus undelivered exceeds what the gateway says it accepted, they do not,
    # and every ratio built on them is meaningless.
    if gateway_denominator and served + undelivered > offered + 1e-9:
        raise ValueError(
            f"accounting is inconsistent: served {served:.0f} + undelivered "
            f"{undelivered:.0f} exceeds offered {offered:.0f}. The edge and the "
            "gateway are scoring different sets of events.")

    # Undelivered work is counted as violating: it has already waited past the
    # budget and nothing in the branch will serve it.
    y = (violations + undelivered) / offered
    mean_wait = (wait_sum / served) if served else float(latency_max_epochs)
    l_tilde = min(max(mean_wait / latency_max_epochs, 0.0), 1.0)

    # Disruption: the share of offered work the action displaced -- deferred at
    # the gateway at any point during the branch, or left queued at the edge it
    # was moved to. Deferral is counted cumulatively: work delayed and later
    # drained was still displaced, and a residual-only reading charged nothing
    # for it.
    # Only deferral the ACTION caused counts. A gateway admission fault defers
    # work under every action, NO_OP included, and C(NO_OP) = 0 by definition --
    # doing nothing disrupts nothing. Charging the fault's share to the action
    # gave a branch that intervened in no way a positive cost. The node reports
    # the split because the binding limiter is known only at the moment of
    # deferral; the totals cannot be separated afterwards.
    by_action = sum(v for k, v in observed.items()
                    if k.endswith("/admission_deferred_by_action_total"))
    has_split = any(k.endswith("/admission_deferred_by_action_total")
                    for k in observed)
    # Runs recorded before this telemetry existed keep their old reading and are
    # flagged as lacking the split, exactly as 0.10 did for the windowed rates.
    # They remain readable; they must not be mixed with split-aware runs in one
    # cost comparison, and the flag is what makes that visible.
    action_deferred = by_action if has_split else deferred
    disruption = min(max((action_deferred + undelivered) / offered, 0.0), 1.0)

    # C(a) is the MEAN of the components that are measured. With disruption
    # alone that is disruption itself, so every figure recorded before 0.25
    # keeps the value it had and the definition did not change under them -- what
    # changed is how many components can be seen.
    resource, bandwidth = _resource_and_bandwidth(observed, offered, end_epoch,
                                                  period_ms)
    measured = [disruption] + [v for v in (resource, bandwidth) if v is not None]
    cost = sum(measured) / len(measured)
    # The measured variant. Epoch-quantised waiting is exactly reproducible,
    # which is what makes it useless as an outcome: quantising to logical time
    # erases the timing variation that impairment actually causes, so replay
    # dispersion measured on it is zero by construction rather than by fact.
    lat_sum = sum(v for k, v in observed.items() if k.endswith("/lat_ms_sum"))
    lat_violations = sum(v for k, v in observed.items() if k.endswith("/lat_ms_violations"))
    mean_lat_ms = (lat_sum / served) if served else float(latency_max_ms)
    y_ms = (lat_violations + undelivered) / offered
    l_tilde_ms = min(max(mean_lat_ms / latency_max_ms, 0.0), 1.0)

    return {"Y": y, "L_tilde": l_tilde, "disruption": disruption,
            "cost": cost,
            "resource": resource if resource is not None else float("nan"),
            "bandwidth": bandwidth if bandwidth is not None else float("nan"),
            "cost_components_measured": float(len(measured)),
            "has_deferral_split": 1.0 if has_split else 0.0,
            "deferred_by_fault": (deferred - by_action) if has_split else 0.0,
            "mean_wait_epochs": mean_wait, "offered": offered,
            "served": served, "unserved": unserved, "violations": violations,
            "residual": residual, "deferred": deferred,
            "gateway_denominator": 1.0 if gateway_denominator else 0.0,
            "Y_ms": y_ms, "L_tilde_ms": l_tilde_ms, "mean_lat_ms": mean_lat_ms}



def _period_ms(matrix):
    """The configured epoch period, in milliseconds, or None.

    Recorded per matrix as `period`, which the runner writes as a Go duration
    string such as "300ms". None where it is absent, and the resource component
    is then reported as unmeasured rather than scaled by a guess.
    """
    v = (matrix or {}).get("period")
    if v is None:
        return None
    text = str(v).strip()
    try:
        if text.endswith("ms"):
            return float(text[:-2])
        if text.endswith("s"):
            return float(text[:-1]) * 1000.0
        return float(text)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="data/raw/<stack>/<experiment>")
    ap.add_argument("--latency-max-ms", type=float, required=True,
                    help="declared calibration maximum for measured end-to-end "
                         "latency; frozen before the comparison, never fitted to it")
    ap.add_argument("--latency-max-epochs", type=float, required=True,
                    help="declared calibration maximum for waiting time; frozen "
                         "before the comparison, never fitted to it")
    ap.add_argument("--allow-partial-cost", action="store_true",
                    help="emit J_obs with the cost term populated from disruption "
                         "alone; the run is then not a complete J_obs measurement")
    ap.add_argument("--out", help="write per-branch rows here as CSV")
    args = ap.parse_args()

    missing = [c for c in COST_COMPONENTS_DECLARED if c not in COST_COMPONENTS_MEASURED]
    if missing and not args.allow_partial_cost:
        print("REFUSED: the cost term is incomplete.", file=sys.stderr)
        print(f"  declared components: {', '.join(COST_COMPONENTS_DECLARED)}", file=sys.stderr)
        print(f"  measured:            {', '.join(COST_COMPONENTS_MEASURED)}", file=sys.stderr)
        print(f"  not instrumented:    {', '.join(missing)}", file=sys.stderr)
        print("  Instrument them, or pass --allow-partial-cost and record in the", file=sys.stderr)
        print("  protocol that this run measures a reduced objective.", file=sys.stderr)
        return 2

    # A budget-calibration matrix ran with a placeholder budget so that a
    # workload level with no budget could be measured at all. Its Y and its cost
    # term are meaningless and it must never reach a results table.
    mpath = os.path.join(args.root, "matrix.json")
    if os.path.exists(mpath):
        with open(mpath) as fh:
            if json.load(fh).get("purpose") == "budget-calibration":
                print("REFUSED: this matrix was run for budget calibration, with "
                      "a placeholder", file=sys.stderr)
                print("  latency budget. J_obs from it is not a measurement. Use "
                      "analysis/calibrate_budget.py.", file=sys.stderr)
                return 2

    rows = []
    matrix = branches.read_matrix(args.root)
    pattern = "s*-a*" if glob.glob(os.path.join(args.root, "s*-a*")) else "a*"
    for d in sorted(glob.glob(os.path.join(args.root, pattern))):
        path = os.path.join(d, "outcome.json")
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            doc = json.load(fh)
        observed = doc.get("observed") or {}
        if not observed:
            print(f"REFUSED: {d} has no observed block; rebuild the branches with "
                  "an orchestrator that records outcomes", file=sys.stderr)
            return 2
        # The epoch the outcome was read at and the configured epoch period are
        # the normalisers for the resource component. Both come from the record,
        # never from a default: a wrong period would scale CPU utilisation
        # silently.
        t = terms(observed, args.latency_max_epochs, args.latency_max_ms,
                  end_epoch=doc.get("epoch"),
                  period_ms=_period_ms(matrix))
        j = W_FAILURE * t["Y_ms"] + W_LATENCY * t["L_tilde_ms"] + W_COST * t["cost"]
        j_q = W_FAILURE * t["Y"] + W_LATENCY * t["L_tilde"] + W_COST * t["cost"]
        name = os.path.basename(d)
        # The factors come from the branch's own manifest, never from its name.
        rec = branches.read(d, matrix)
        rows.append({"branch": name,
                     "scenario": rec["scenario_id"],
                     "anchor": f"a{rec['anchor']:02d}",
                     "action": rec["action"],
                     "repeat": f"r{rec['repeat']:02d}",
                     "regime": rec["regime"],
                     "fault_type": rec["fault_type"],
                     "fault_onset": rec["fault_onset"],
                     "fault_severity": rec["fault_severity"],
                     "workload_level": rec["workload_level"],
                     "legacy": int(rec["legacy"]),
                     "J_obs": j, "J_obs_quantised": j_q, **t})

    if not rows:
        print(f"no branches with outcomes under {args.root}", file=sys.stderr)
        return 2

    # A set that mixes reconstructed legacy factors with recorded ones is not a
    # set: the legacy reconstruction assumes the single fault of protocol 0.7.
    if len({r["legacy"] for r in rows}) > 1:
        print("REFUSED: this root mixes branches with recorded scenario "
              "manifests and branches whose factors were reconstructed from a "
              "pre-0.9 matrix. Analyse them separately.", file=sys.stderr)
        return 2

    # A comparison whose branches do not share a denominator is not a
    # comparison. Mixing gateway-measured offered work with edge-measured
    # offered work would put NO_OP and THROTTLE on different scales, which is
    # precisely the defect this denominator was changed to remove.
    gw = {r["gateway_denominator"] for r in rows}
    if len(gw) > 1:
        n_old = sum(1 for r in rows if r["gateway_denominator"] == 0.0)
        print(f"REFUSED: {n_old} of {len(rows)} branches predate the gateway-measured "
              "denominator; the set mixes two definitions of offered work. Re-run "
              "the whole matrix on one binary.", file=sys.stderr)
        return 2
    if 0.0 in gw:
        print("WARNING: offered work is measured at the edge, not the gateway. Work "
              "refused admission is invisible, so actions that refuse work are "
              "scored only on what they let through. These numbers are not "
              "comparable across actions.", file=sys.stderr)

    width = max(len(r["branch"]) for r in rows)
    print(f"{'branch':{width}s}  {'J_obs':>7s}  {'Y':>6s}  {'L~':>6s}  {'lat ms':>7s}"
          f"  {'disr':>6s}  {'served':>7s} {'unserv':>7s} {'defer':>7s} {'offered':>8s}")
    for r in rows:
        print(f"{r['branch']:{width}s}  {r['J_obs']:7.4f}  {r['Y_ms']:6.3f}  "
              f"{r['L_tilde_ms']:6.3f}  {r['mean_lat_ms']:7.1f}  {r['disruption']:6.3f}  "
              f"{r['served']:7.0f} {r['unserved']:7.0f} {r['deferred']:7.0f} "
              f"{r['offered']:8.0f}")

    # Replay dispersion, the frozen definition: Q0.95 of ALL pairwise absolute
    # differences between repeats of the same (anchor, action) cell, pooled.
    # The worst single cell is reported beside it, because a band that holds on
    # average and fails in one cell is not a band.
    import itertools
    cells = {}
    for r in rows:
        cells.setdefault((r["scenario"], r["anchor"], r["action"]), []).append(r["J_obs"])
    cells_q = {}
    for r in rows:
        cells_q.setdefault((r["scenario"], r["anchor"], r["action"]),
                           []).append(r["J_obs_quantised"])
    pooled = [abs(a - b) for v in cells.values() for a, b in itertools.combinations(v, 2)]
    pooled_q = [abs(a - b) for v in cells_q.values() for a, b in itertools.combinations(v, 2)]
    eta = quantile(pooled, 0.95)
    eta_q = quantile(pooled_q, 0.95)
    worst = max((quantile([abs(a - b) for a, b in itertools.combinations(v, 2)], 0.95)
                 for v in cells.values()), default=0.0)

    print(f"\nREPLAY DISPERSION ({len(pooled)} same-cell pairs)")
    print(f"  eta_J   measured latency  = {eta:.4f}   (worst cell {worst:.4f})")
    print(f"  eta_J   epoch-quantised   = {eta_q:.4f}")
    if eta_q < eta / 2:
        print("  The quantised observable understates the dispersion: it cannot")
        print("  represent variation finer than an epoch, so a band measured on it")
        print("  is a property of the units, not of the system.")

    # The preregistered gate, applied as written and not adjusted afterwards.
    keys = sorted({(sc, a) for sc, a, _ in cells})
    actions = sorted({c for _, _, c in cells} - {"NO_OP"})
    print(f"\nPREREGISTERED GATE  SNR_J >= {SNR_GATE:g}   (eta_J = {eta:.4f})")
    header = "  cell        " + "".join(f"{a:>12s}" for a in ["NO_OP"] + actions)
    print(header + "   " + "  ".join(f"SNR({a[:4]})" for a in actions))
    resolvable = total = 0
    for sc, a in keys:
        base = cells.get((sc, a, "NO_OP"))
        if not base:
            continue
        med = median(base)
        line = f"  {sc + '-' + a:10s}  {med:12.3f}"
        snrs = []
        for act in actions:
            v = cells.get((sc, a, act))
            if not v:
                line += f"{'-':>12s}"
                snrs.append("-")
                continue
            eff = median(v) - med
            snr = abs(eff) / eta if eta > 0 else float("inf")
            total += 1
            if snr >= SNR_GATE:
                resolvable += 1
            line += f"{median(v):12.3f}"
            snrs.append(f"{snr:9.2f}")
        print(line + "   " + "  ".join(snrs))
    p_res = resolvable / total if total else 0.0
    print(f"\n  contrasts resolvable at the gate: {resolvable}/{total} = {p_res:.3f}")
    if resolvable < total:
        print("  Contrasts below the gate are NOT null effects. They are effects this")
        print("  design cannot separate from replay dispersion, and reporting them as")
        print("  differences would be reporting the dispersion.")

    if args.out:
        import csv
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {args.out}")
    if missing:
        print("\nNOTE: cost term populated from disruption only; "
              f"{', '.join(missing)} are not instrumented. This is a reduced "
              "objective and must be described as one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
