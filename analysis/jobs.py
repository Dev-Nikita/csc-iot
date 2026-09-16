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
COST_COMPONENTS_MEASURED = ("disruption",)
COST_COMPONENTS_DECLARED = ("added_latency", "resource", "bandwidth", "disruption")


def dispersion(values):
    """Q0.95 of all pairwise absolute differences within a cell."""
    d = sorted(abs(a - b) for i, a in enumerate(values) for b in values[i + 1:])
    if not d:
        return 0.0
    idx = min(int(0.95 * (len(d) - 1) + 0.5), len(d) - 1)
    return d[idx]


def terms(observed, latency_max_epochs, latency_max_ms):
    served = sum(v for k, v in observed.items() if k.endswith("/served"))
    unserved = sum(v for k, v in observed.items() if k.endswith("/unserved_eligible"))
    if not any(k.endswith("/unserved_eligible") for k in observed):
        # Older branches: fall back, and say so rather than silently mixing two
        # definitions of the denominator.
        unserved = sum(v for k, v in observed.items() if k.endswith("/unserved"))
    violations = sum(v for k, v in observed.items() if k.endswith("/sla_violations"))
    wait_sum = sum(v for k, v in observed.items() if k.endswith("/wait_sum_epochs"))
    offered = served + unserved
    if offered == 0:
        raise ValueError("no work was offered in this branch; J_obs is undefined")

    # Unserved work is counted as violating: it has already waited past the
    # budget and nothing in the branch will serve it.
    y = (violations + unserved) / offered
    mean_wait = (wait_sum / served) if served else float(latency_max_epochs)
    l_tilde = min(max(mean_wait / latency_max_epochs, 0.0), 1.0)

    # Disruption: the share of offered work the action displaced -- deferred at
    # the gateway, or left queued at the edge it was moved to.
    deferred = sum(v for k, v in observed.items() if k.endswith("/admission_backlog"))
    disruption = min(max((deferred + unserved) / offered, 0.0), 1.0)
    # The measured variant. Epoch-quantised waiting is exactly reproducible,
    # which is what makes it useless as an outcome: quantising to logical time
    # erases the timing variation that impairment actually causes, so replay
    # dispersion measured on it is zero by construction rather than by fact.
    lat_sum = sum(v for k, v in observed.items() if k.endswith("/lat_ms_sum"))
    lat_violations = sum(v for k, v in observed.items() if k.endswith("/lat_ms_violations"))
    mean_lat_ms = (lat_sum / served) if served else float(latency_max_ms)
    y_ms = (lat_violations + unserved) / offered
    l_tilde_ms = min(max(mean_lat_ms / latency_max_ms, 0.0), 1.0)

    return {"Y": y, "L_tilde": l_tilde, "disruption": disruption,
            "mean_wait_epochs": mean_wait, "offered": offered,
            "served": served, "unserved": unserved, "violations": violations,
            "Y_ms": y_ms, "L_tilde_ms": l_tilde_ms, "mean_lat_ms": mean_lat_ms}


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

    rows = []
    for d in sorted(glob.glob(os.path.join(args.root, "a*"))):
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
        t = terms(observed, args.latency_max_epochs, args.latency_max_ms)
        j = W_FAILURE * t["Y_ms"] + W_LATENCY * t["L_tilde_ms"] + W_COST * t["disruption"]
        j_q = W_FAILURE * t["Y"] + W_LATENCY * t["L_tilde"] + W_COST * t["disruption"]
        name = os.path.basename(d)
        anchor, action, repeat = name.split("-")
        rows.append({"branch": name, "anchor": anchor, "action": action,
                     "repeat": repeat, "J_obs": j, "J_obs_quantised": j_q, **t})

    if not rows:
        print(f"no branches with outcomes under {args.root}", file=sys.stderr)
        return 2

    width = max(len(r["branch"]) for r in rows)
    print(f"{'branch':{width}s}  {'J_obs':>7s}  {'Y':>6s}  {'L~':>6s}  {'lat ms':>7s}"
          f"  {'disr':>6s}  {'served':>7s} {'unserv':>7s} {'offered':>8s}")
    for r in rows:
        print(f"{r['branch']:{width}s}  {r['J_obs']:7.4f}  {r['Y_ms']:6.3f}  "
              f"{r['L_tilde_ms']:6.3f}  {r['mean_lat_ms']:7.1f}  {r['disruption']:6.3f}  "
              f"{r['served']:7.0f} {r['unserved']:7.0f} {r['offered']:8.0f}")

    # Replay dispersion, the frozen definition: Q0.95 of ALL pairwise absolute
    # differences between repeats of the same (anchor, action) cell, pooled.
    # The worst single cell is reported beside it, because a band that holds on
    # average and fails in one cell is not a band.
    import itertools
    cells = {}
    for r in rows:
        cells.setdefault((r["anchor"], r["action"]), []).append(r["J_obs"])
    cells_q = {}
    for r in rows:
        cells_q.setdefault((r["anchor"], r["action"]), []).append(r["J_obs_quantised"])
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
    anchors = sorted({a for a, _ in cells})
    actions = sorted({b for _, b in cells} - {"NO_OP"})
    print(f"\nPREREGISTERED GATE  SNR_J >= {SNR_GATE:g}   (eta_J = {eta:.4f})")
    header = "  anchor  " + "".join(f"{a:>12s}" for a in ["NO_OP"] + actions)
    print(header + "   " + "  ".join(f"SNR({a[:4]})" for a in actions))
    resolvable = total = 0
    for a in anchors:
        base = cells.get((a, "NO_OP"))
        if not base:
            continue
        med = median(base)
        line = f"  {a:6s}  {med:12.3f}"
        snrs = []
        for act in actions:
            v = cells.get((a, act))
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
