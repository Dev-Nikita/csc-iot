#!/usr/bin/env python3
"""Audit the measurement itself, on every branch of a completed run.

Three full 900-branch matrices were discarded because the objective was
computed from observables that did not mean what the analysis assumed. Every
one of those defects was visible in the recorded numbers and nothing looked
at them. This does.

The invariants are properties of the accounting, not of the system's
behaviour, so a violation is always an instrumentation defect. It is checked
on real branches rather than in a unit test because that is where all three
defects lived.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import faultcheck

import branches

HIST = "lat_hist_ms_"


def suffix_sum(observed, suffix):
    return sum(v for k, v in observed.items() if k.endswith(suffix))


def audit(path, rec):
    with open(os.path.join(path, "outcome.json")) as fh:
        doc = json.load(fh)
    obs = doc.get("observed") or {}
    action = rec["action"]
    sla_ms = rec["sla_ms"]
    bad = []
    if not sla_ms:
        return ["no latency budget recorded for this branch"]

    required = ("/ingress_accepted", "/served", "/unserved_eligible",
                "/sla_violations", "/lat_ms_violations", "/lat_ms_sum",
                "/admission_deferred_total", "/admission_backlog_depth")
    for suffix in required:
        if not any(k.endswith(suffix) for k in obs):
            bad.append(f"missing observable {suffix.lstrip('/')}")
    if bad:
        return bad

    accepted = suffix_sum(obs, "/ingress_accepted")
    served = suffix_sum(obs, "/served")
    eligible = suffix_sum(obs, "/unserved_eligible")
    residual = suffix_sum(obs, "/admission_backlog_depth")
    raw_unserved = suffix_sum(obs, "/unserved")
    lat_viol = suffix_sum(obs, "/lat_ms_violations")
    sla_viol = suffix_sum(obs, "/sla_violations")
    deferred = suffix_sum(obs, "/admission_deferred_total")
    hist = sum(v for k, v in obs.items() if HIST in k)

    # 1. One set of events. This is the invariant that caught protocol 0.7:
    #    served 800 + unserved 100 against offered 800.
    if served + eligible + residual > accepted + 1e-9:
        bad.append(f"served {served:.0f} + undelivered {eligible + residual:.0f} "
                   f"> accepted {accepted:.0f}")
    # 2. The eligible count is a subset of the inbox.
    if eligible > raw_unserved + 1e-9:
        bad.append(f"unserved_eligible {eligible:.0f} > unserved {raw_unserved:.0f}")
    # 3. Every served event is in the latency histogram exactly once.
    if abs(hist - served) > 1e-9:
        bad.append(f"histogram holds {hist:.0f} events, {served:.0f} were served")
    # 4. A violation is a served event that missed the budget.
    if lat_viol > served + 1e-9:
        bad.append(f"lat_ms_violations {lat_viol:.0f} > served {served:.0f}")
    # 5. The histogram must agree with the violation count at the frozen budget.
    above = sum(v for k, v in obs.items() if HIST in k
                and int(k.split(HIST)[1]) >= sla_ms)
    if above > lat_viol + 1e-9:
        bad.append(f"{above:.0f} events binned at or above {sla_ms} ms but "
                   f"lat_ms_violations is {lat_viol:.0f}")
    # 6. Work is deferred at the gateway only where something limits admission:
    #    the THROTTLE action, or a D5 fault in the gateway's own admission
    #    capacity. Before D5 the action was the only limiter, so this read
    #    `action != "THROTTLE"` and reported 24 correct D5 branches as broken --
    #    860 events deferred under NO_OP is the fault doing exactly its job.
    #    The invariant still has teeth in the direction that matters: a branch
    #    with neither limiter must defer nothing.
    gw_limits_admission = (rec.get("degraded_admit", -1) >= 0
                           and rec["regime"] != "pre-fault")
    if action != "THROTTLE" and not gw_limits_admission and deferred > 0:
        bad.append(f"{action} deferred {deferred:.0f} events at the gateway with "
                   f"nothing limiting admission: neither the action nor a declared "
                   f"gateway fault")
    # 6b. The deferral split must account for every deferred event, and a
    #     branch with no gateway fault must attribute nothing to one. Without
    #     this the cost term could silently drop or invent displaced work.
    by_action = suffix_sum(obs, "/admission_deferred_by_action_total")
    by_fault = suffix_sum(obs, "/admission_deferred_by_fault_total")
    has_split = any(k.endswith("/admission_deferred_by_action_total") for k in obs)
    if has_split:
        if abs((by_action + by_fault) - deferred) > 1e-9:
            bad.append(f"deferral split {by_action:.0f} by action + {by_fault:.0f} "
                       f"by fault != {deferred:.0f} deferred in total")
        if not gw_limits_admission and by_fault > 0:
            bad.append(f"{by_fault:.0f} events attributed to a gateway fault on a "
                       f"branch that declares none in its window")
        if action == "NO_OP" and by_action > 0:
            bad.append(f"NO_OP is charged {by_action:.0f} deferred events: "
                       f"C(NO_OP) = 0 by definition")

    # 7a. The fault the node actually ran must be the fault the scenario
    #     declared. The parameters reach the container through compose variable
    #     substitution, which can silently fall back to its defaults: every
    #     branch would then carry the same fault while every manifest claimed
    #     otherwise, and the matrix would look like a factorial design without
    #     being one. This is the cheapest possible check against the most
    #     expensive possible mistake.
    if not rec.get("legacy"):
        try:
            with open(os.path.join(path, "anchor.json")) as fh:
                anchor = json.load(fh)
        except OSError:
            anchor = None
        if anchor is None:
            bad.append("no anchor.json to verify the fault against")
        else:
            # The rule itself lives in analysis/faultcheck.py, shared with the
            # runner. It was written twice before, and the same defect then had
            # to be found three times -- see that module's docstring.
            bad.extend(faultcheck.verify(rec, anchor))

    # 7b. The declared fault must have HAD AN EFFECT, not merely been declared.
    #     7a compares the configuration the node reports with the manifest, which
    #     catches a parameter that never reached the container. It does not catch
    #     a parameter that arrived and did nothing. Throughput does: an edge whose
    #     capacity dropped to S at epoch T cannot have served more than
    #     N*(T-1) + S*(epochs-T+1) events, whatever the action. Exceeding that
    #     bound is proof the degradation did not happen.
    #
    #     One-sided on purpose. Serving LESS is ordinary -- REROUTE moves work
    #     away, THROTTLE admits less, and an unsaturated edge serves only what
    #     arrives. Only the upper bound carries information.
    if not rec.get("legacy") and rec["fault_severity"] > 0:
        try:
            with open(os.path.join(path, "outcome.json")) as fh:
                out_doc = json.load(fh)
            end_epoch = int(out_doc["epoch"])
            nominal = float(json.load(open(os.path.join(path, "anchor.json")))
                            ["state"]["edge_capacity"]["edge00/serve_per_epoch"])
        except (OSError, KeyError, ValueError):
            end_epoch, nominal = None, None
        # A mechanism may fault the gateway and leave the edges alone (D5).
        # The edge bound then does not apply, and asserting it anyway would
        # report a correct run as broken. A separate bound is checked instead:
        # a gateway that admits at most `degraded_admit` per epoch cannot have
        # accepted more than that allows.
        edge_faulted = rec.get("edge_faulted", 1)
        gw_admit = rec.get("degraded_admit", -1)
        if end_epoch and gw_admit is not None and gw_admit >= 0:
            onset = rec["fault_onset"]
            serving = max(0, end_epoch - 1)
            # The ONSET epoch is a transition epoch and is charged at the healthy
            # rate; only epochs strictly after it are bounded by the cap.
            #
            # This is not a tolerance: it is where the fault acts. The gateway's
            # fault limits ARRIVALS, and an event tagged with epoch T can reach
            # the gateway before the epoch boundary at which the fault for T is
            # applied -- the device simulator emits ahead of the boundary. So the
            # events of the onset epoch are admitted partly under the old cap.
            # Measured overshoot on d45-matrix-v1 was exactly one cap's worth,
            # 1840 forwarded against a bound of 1800, on 228 branches.
            #
            # The edge bound below keeps `onset - 1` because an edge fault limits
            # SERVING, which happens at the boundary itself, after the fault for
            # that epoch is in force. Different bounds because the two faults act
            # on different sides of the boundary, not because one needed slack.
            #
            # The check keeps its teeth: a fault that never binds at all forwards
            # the full offered rate for every epoch, which exceeds this bound by
            # far -- that is how the dead fault of 0.20 was caught (2700 against
            # 2160) and it would still be caught here.
            bound = gateway_forward_bound(rec["workload_level"], gw_admit,
                                          onset, end_epoch)
            # What the cap bounds is what the gateway FORWARDED, not what
            # arrived at it. `ingress_accepted` counts arrivals -- deferral is
            # charged cumulatively and a deferred event is still accepted work,
            # which is what makes the denominator action-independent (0.5).
            # Bounding arrivals by an admission cap compares two different
            # quantities and would fail a working fault for admitting less than
            # it was offered. Every accepted event is either forwarded or still
            # sitting in the admission backlog, so forwarded = accepted - residual.
            forwarded = accepted - residual
            if degraded > 0 and forwarded > bound * 1.02 + 1:
                bad.append(f"the gateway forwarded {forwarded:.0f} events "
                           f"(accepted {accepted:.0f}, {residual:.0f} still in the "
                           f"admission backlog) but an admission fault at epoch "
                           f"{onset} capping it to {gw_admit} per epoch allows at "
                           f"most {bound:.0f} over {serving} epochs: the declared "
                           f"gateway fault had no effect")
        if end_epoch and nominal and edge_faulted:
            onset = rec["fault_onset"]
            serving = max(0, end_epoch - 1)          # epochs that served work
            healthy_epochs = min(serving, max(0, onset - 1))
            degraded_epochs = serving - healthy_epochs
            bound = nominal * healthy_epochs + rec["fault_severity"] * degraded_epochs
            served00 = suffix_sum(
                {k: v for k, v in obs.items() if k.startswith("edge00/")}, "/served")
            # Only informative where the bound actually binds.
            if degraded_epochs > 0 and served00 > bound * 1.02 + 1:
                bad.append(f"edge00 served {served00:.0f} but a fault at epoch "
                           f"{onset} dropping capacity to {rec['fault_severity']} "
                           f"allows at most {bound:.0f} over {serving} epochs: the "
                           f"declared degradation had no effect")

    # 7. A healthy no-action branch is not allowed to fail. If it does, the
    #    budget or the accounting is wrong, not the system.
    # A pre-fault branch spans no fault at all: nothing is wrong and nothing
    # will go wrong inside its horizon. The regime is computed from the
    # branch's own onset and horizon, not from its anchor index.
    # A gateway admission fault refuses work before it reaches an edge, so a
    # branch spanning one has undelivered work by design and the healthy-branch
    # invariant does not apply to it. The regime label still says pre-fault when
    # the fault lies beyond the horizon, and there the invariant does hold.
    gw_faulted_in_horizon = (rec.get("degraded_admit", -1) >= 0
                             and rec["regime"] != "pre-fault")
    if rec["regime"] == "pre-fault" and action == "NO_OP" and not gw_faulted_in_horizon:
        if eligible + residual > 0:
            bad.append(f"pre-fault NO_OP left {eligible + residual:.0f} events undelivered")
        if sla_viol > 0:
            bad.append(f"pre-fault NO_OP missed the epoch deadline {sla_viol:.0f} times")
    return bad



def gateway_forward_bound(offered_rate, gw_admit, onset, end_epoch):
    """Most events a gateway with an admission fault can have forwarded.

    One-sided. Forwarding LESS is ordinary: an action may refuse work and an
    unsaturated gateway forwards only what arrives. Only the upper bound carries
    information, and what it detects is a declared fault that did nothing.
    """
    serving = max(0, end_epoch - 1)
    healthy = min(serving, onset)
    return offered_rate * healthy + gw_admit * max(0, serving - onset)

def rows_are_legacy(dirs, matrix):
    for d in dirs:
        try:
            return bool(branches.read(d, matrix).get("legacy"))
        except ValueError:
            continue
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    args = ap.parse_args()

    matrix = branches.read_matrix(args.root)
    pattern = "s*-a*" if glob.glob(os.path.join(args.root, "s*-a*")) else "a*"
    dirs = sorted(glob.glob(os.path.join(args.root, pattern)))
    if not dirs:
        print(f"no branches under {args.root}", file=sys.stderr)
        return 2
    failed = {}
    for d in dirs:
        if not os.path.exists(os.path.join(d, "outcome.json")):
            failed[os.path.basename(d)] = ["no outcome.json"]
            continue
        try:
            rec = branches.read(d, matrix)
        except ValueError as exc:
            failed[os.path.basename(d)] = [str(exc)]
            continue
        bad = audit(d, rec)
        if bad:
            failed[os.path.basename(d)] = bad

    # A cell's repeats are replays of one prefix, and the actions compared at an
    # anchor must share that prefix. If the fault differed across them, the
    # replay band would measure the scenario and the action contrast would
    # compare two different systems.
    cell_faults = {}
    for d in dirs:
        try:
            rec = branches.read(d, matrix)
        except ValueError:
            continue
        key = (rec["scenario_id"], rec["anchor"])
        sig = (rec["fault_type"], rec["fault_onset"], rec["fault_severity"],
               rec["workload_level"], rec["seed"])
        cell_faults.setdefault(key, {}).setdefault(sig, []).append(
            os.path.basename(d))
    split_cells = {k: v for k, v in cell_faults.items() if len(v) > 1}
    if split_cells:
        print(f"REFUSED: {len(split_cells)} anchor cell(s) contain more than one "
              "scenario. Repeats are replays of one prefix and the actions "
              "compared at an anchor must share it.", file=sys.stderr)
        for k, v in sorted(split_cells)[:3]:
            print(f"  {k}: {len(v)} distinct fault settings, e.g. "
                  f"{[b[0] for b in v.values()]}", file=sys.stderr)
        return 1

    binding = 0
    for d in dirs:
        try:
            rec = branches.read(d, matrix)
        except ValueError:
            continue
        if rec.get("legacy") or rec["fault_severity"] <= 0:
            continue
        try:
            end_epoch = int(json.load(open(os.path.join(d, "outcome.json")))["epoch"])
        except (OSError, KeyError, ValueError):
            continue
        if max(0, end_epoch - 1) - min(max(0, end_epoch - 1),
                                       max(0, rec["fault_onset"] - 1)) > 0:
            binding += 1

    print(f"ACCOUNTING AUDIT: {len(dirs)} branches, {len(failed)} with violations")
    if not rows_are_legacy(dirs, matrix):
        print(f"  the degradation-effect bound binds on {binding}/{len(dirs)} "
              f"branches (the rest end before their onset)")
    if not failed:
        print("  every branch: one event set, histogram complete, "
              "pre-fault NO_OP clean")
        return 0
    kinds = {}
    for branch, bad in failed.items():
        for b in bad:
            kinds.setdefault(b.split(" ")[0] + " " + b.split(" ")[1], []).append(branch)
    for kind, hits in sorted(kinds.items()):
        print(f"  {len(hits):4d}x {kind} ... e.g. {hits[0]}")
    print("\nFirst five in full:")
    for branch in sorted(failed)[:5]:
        print(f"  {branch}: {'; '.join(failed[branch])}")
    print("\nThese are accounting invariants: a violation is an instrumentation",
          file=sys.stderr)
    print("defect, never a property of the system. The run is not reportable.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
