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

HIST = "lat_hist_ms_"


def suffix_sum(observed, suffix):
    return sum(v for k, v in observed.items() if k.endswith(suffix))


def audit(path, healthy, sla_ms):
    with open(os.path.join(path, "outcome.json")) as fh:
        doc = json.load(fh)
    obs = doc.get("observed") or {}
    name = os.path.basename(path)
    anchor, action, _ = name.split("-")
    bad = []

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
    # 6. Only a throttled branch defers work.
    if action != "THROTTLE" and deferred > 0:
        bad.append(f"{action} deferred {deferred:.0f} events at the gateway")
    # 7. A healthy no-action branch is not allowed to fail. If it does, the
    #    budget or the accounting is wrong, not the system.
    if anchor in healthy and action == "NO_OP":
        if eligible + residual > 0:
            bad.append(f"healthy NO_OP left {eligible + residual:.0f} events undelivered")
        if sla_viol > 0:
            bad.append(f"healthy NO_OP missed the epoch deadline {sla_viol:.0f} times")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--healthy-anchors", required=True)
    ap.add_argument("--sla-ms", type=int, required=True,
                    help="the budget frozen in the protocol, not a choice made here")
    args = ap.parse_args()
    healthy = set(args.healthy_anchors.split(","))

    dirs = sorted(glob.glob(os.path.join(args.root, "a*")))
    if not dirs:
        print(f"no branches under {args.root}", file=sys.stderr)
        return 2
    failed = {}
    for d in dirs:
        if not os.path.exists(os.path.join(d, "outcome.json")):
            failed[os.path.basename(d)] = ["no outcome.json"]
            continue
        bad = audit(d, healthy, args.sla_ms)
        if bad:
            failed[os.path.basename(d)] = bad

    print(f"ACCOUNTING AUDIT: {len(dirs)} branches, {len(failed)} with violations")
    if not failed:
        print("  every branch: one event set, histogram complete, healthy NO_OP clean")
        return 0
    kinds = {}
    for branch, bad in failed.items():
        for b in bad:
            kinds.setdefault(b.split(" ")[0] + " " + b.split(" ")[1], []).append(branch)
    for kind, branches in sorted(kinds.items()):
        print(f"  {len(branches):4d}x {kind} ... e.g. {branches[0]}")
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
