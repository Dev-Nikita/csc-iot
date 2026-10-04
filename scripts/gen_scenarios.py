#!/usr/bin/env python3
"""Draw the declared scenario factors, reproducibly, before any run.

A scenario is (mechanism, onset, severity, workload, seed). Through protocol 0.7
every branch carried one fault at one onset with one severity, which made the
anchor index an exact proxy for fault age: a predictor could score well by
memorising a schedule that never varied. The factor exists to remove that.

The draw is a pure function of the master seed, so the scenario set is part of
the declared configuration rather than something chosen after seeing results.
"""
import argparse
import hashlib
import json
import random
import sys

# Declared levels (protocol 0.9 section 11a).
ONSET_RANGE = (8, 24)          # inclusive epochs
SEVERITY_LEVELS = (40, 60, 90)  # post-onset serve-per-epoch, from 150
WORKLOAD_LEVELS = (60, 100, 140)  # events per epoch

# Mechanisms. D1 and D3 are expressible with the node flags that exist; D2 needs
# netem re-applied part-way through a branch and is not implemented, so it is
# refused here rather than quietly emitted and silently run as D1.
MECHANISMS = {
    "D1": "edge capacity degradation at onset",
    "D3": "edge stall at onset (serve rate to zero)",
    # D4 and D5 exist because of a measured defect in the design, not for
    # coverage. With only D1 and D3, rerouting is almost always the best action
    # and a one-line threshold on the per-edge service deficit attains the
    # oracle bound (b5-matrix-v2: CRA_eta 1.000 on two of three splits), which
    # leaves the common-anchor comparison with nothing to separate. In both of
    # these the correct action depends on WHERE the deficit is rather than on how
    # large it is, which the permitted features expose and a single threshold
    # cannot read.
    "D4": "correlated degradation: the loaded edge and the relief path together",
    "D5": "gateway admission capacity loss (upstream of every edge)",
    # D6 exists for the same reason D4 and D5 did: a measured defect in the
    # design. On the D4/D5 transfer set the degenerate ablation that removes the
    # gate entirely -- which then always takes the cheapest action, NO_OP --
    # scored 0.955 against CSC's 0.900 and the oracle's 1.000. Doing nothing was
    # near-optimal. On the earlier D1/D3 matrix the same ablation scored 0.254
    # and a one-line threshold attained the oracle, because rerouting was almost
    # always right. The two sets are degenerate in OPPOSITE directions, and
    # neither poses the problem of choosing among actions. What is missing is a
    # regime in which THROTTLE is the correct action; without one, C(THROTTLE)
    # is the largest cost in the objective and the action is never worth paying
    # for, so a method is never tested on the decision it exists to make.
    "D6": "correlated degradation of BOTH paths equally (nowhere to reroute)",
}
NOT_IMPLEMENTED = {
    "D2": "ingress impairment ramp: requires netem re-application mid-branch",
}


def draw(master_seed, n, mechanisms, workloads):
    """Unique design points. Two scenarios differing only by seed are replicates,
    not design points: holding one out and training on the other tests
    generalisation to a scenario the model has effectively seen. The draw is
    without replacement over (mechanism, onset, severity, workload)."""
    rng = random.Random(master_seed)
    out = []
    used = set()
    for i in range(1, n + 1):
        # Mechanism, severity and workload are assigned round-robin rather than
        # drawn. A random draw of 24 scenarios gave 12 at the mildest severity
        # and 4 at the strongest, which leaves the parameter-shift split of B5
        # with too few scenarios on the held-out side to say anything. Onset
        # stays random: it is the factor whose whole purpose is to stop the
        # anchor index from indexing the fault's age.
        # Severity and workload must advance on DIFFERENT strides. Indexing both
        # by (i-1) % 3 made them perfectly correlated: of the nine
        # (severity, workload) combinations only three ever appeared --- the
        # mildest fault only at the lightest load, the strongest only at the
        # heaviest. Severity and workload would then be aliased, a model could
        # not distinguish one from the other, and a parameter-shift split on
        # either would silently be a shift on both. With a single workload level
        # the defect was latent; it bites the moment workload becomes a factor,
        # which is exactly what protocol 0.9 requires.
        mech = mechanisms[(i - 1) % len(mechanisms)]
        sev = 0 if mech == "D3" else SEVERITY_LEVELS[(i - 1) % len(SEVERITY_LEVELS)]
        load = workloads[((i - 1) // len(SEVERITY_LEVELS)) % len(workloads)]
        onsets = [o for o in range(ONSET_RANGE[0], ONSET_RANGE[1] + 1)
                  if (mech, o, sev, load) not in used]
        if not onsets:
            raise SystemExit(
                f"REFUSED: the declared levels admit no further distinct design "
                f"point for ({mech}, severity {sev}, load {load}); asked for "
                f"{n} scenarios.")
        onset = rng.choice(onsets)
        used.add((mech, onset, sev, load))
        seed = rng.randrange(1, 2**31 - 1)
        rec = {
            "scenario_id": f"s{i:02d}",
            "fault_type": mech,
            "fault_onset": onset,
            "fault_severity": sev,
            "workload_level": load,
            "seed": seed,
        }
        if mech == "D4":
            # The relief path must end up WORSE than the loaded edge, not merely
            # also degraded. Scaling it to its own larger nominal left rerouting
            # beneficial, which would have reproduced the very defect this
            # mechanism exists to remove. Half the loaded edge's surviving
            # capacity puts it strictly below, so rerouting moves work from a
            # node serving `sev` to one serving `sev/2` and is actively harmful.
            rec["relief_degraded_serve"] = max(1, sev // 2)
        if mech == "D6":
            # Both routable edges degraded to the SAME surviving capacity. The
            # contrast with D4 is exactly one character of arithmetic and it is
            # the whole mechanism: D4 puts the relief path strictly BELOW the
            # loaded edge, so rerouting is harmful; D6 puts it LEVEL, so
            # rerouting is pointless rather than harmful, and there is no
            # escape by routing at all.
            #
            # PREREGISTERED EXPECTATION, written before this mechanism was ever
            # run: THROTTLE is the best of the three actions here. Admitting
            # everything lets the queue grow without bound, so waiting time
            # grows without bound and eventually every served event misses the
            # budget as well as the work left unserved; capping admission sheds
            # part of the offered work but keeps what is admitted inside the
            # budget. The objective charges the shed work twice -- once in Y as
            # undelivered and once in the cost term as displaced -- so the
            # expectation is a real risk and not a tautology: with weights
            # 0.6/0.2/0.2 the latency saving has to beat 0.2 x (shed fraction).
            # If THROTTLE does not win here, that is reported, this mechanism
            # does not deliver what it was built for, and no parameter of the
            # objective moves in response.
            rec["relief_degraded_serve"] = sev
        if mech == "D5":
            # The gateway admits less than is offered, so work is refused before
            # it reaches any edge, and THE EDGES ARE NOT FAULTED AT ALL. That is
            # the point: the per-edge service deficit stays near zero, the
            # backlog grows upstream, and the only actions available make it
            # worse -- rerouting cannot relieve a bottleneck ahead of every edge
            # and throttling tightens the same limit that is already binding.
            # Inaction is correct, which is a case the earlier mechanisms never
            # produced.
            rec["degraded_admit"] = int(round(load * sev / 150.0))
            rec["edge_faulted"] = 0
        out.append(rec)
    _refuse_aliased_factors(out)
    return out


def _refuse_aliased_factors(scenarios):
    """A scenario set in which two factors move together is not a factorial set.

    This is the guard that would have caught the severity/workload aliasing, so
    it lives in the generator rather than in a review comment. Perfect
    correlation is checked directly rather than by a coefficient: the question is
    whether each level of one factor is seen at more than one level of the other.
    """
    graded = [s for s in scenarios if s["fault_severity"] > 0]
    if len(graded) < 2:
        return
    for a, b in (("fault_severity", "workload_level"),
                 ("fault_severity", "fault_onset"),
                 ("workload_level", "fault_onset")):
        seen, count = {}, {}
        for s in graded:
            seen.setdefault(s[a], set()).add(s[b])
            count[s[a]] = count.get(s[a], 0) + 1
        # Both factors must actually vary. A draw at one workload level has
        # every severity at that single level, which is not aliasing -- it is a
        # set with one level, and the guard fired on every single-workload
        # calibration and pilot draw.
        if len(seen) < 2 or len({s[b] for s in graded}) < 2:
            continue
        # Every level of A must have had a CHANCE to show a second level of B.
        # With one scenario per level the one-to-one map is a property of the
        # sample size, not of the design, and the guard fired on every small
        # pilot draw. Aliasing is a claim about the assignment rule, so it is
        # only made where the rule had room to reveal itself.
        if min(count.values()) < 2:
            continue
        if all(len(v) == 1 for v in seen.values()):
            pairs = sorted((k, sorted(v)[0]) for k, v in seen.items())
            raise SystemExit(
                f"REFUSED: {a} and {b} are perfectly aliased in this draw --- "
                f"every level of {a} appears at exactly one level of {b}: "
                f"{pairs}. A model cannot separate them and a shift split on "
                f"one is a shift on both. Widen the levels or change the "
                f"assignment strides.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--master-seed", type=int, required=True)
    ap.add_argument("--mechanisms", default="D1",
                    help="comma list from " + ",".join(sorted(MECHANISMS)))
    ap.add_argument("--workloads", default="100",
                    help="comma list from " + ",".join(str(w) for w in WORKLOAD_LEVELS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--for-calibration", action="store_true",
                    help="the set exists only to measure a healthy latency "
                         "distribution at a workload level that has no budget "
                         "yet. Skips the budget check and stamps the file "
                         "purpose=budget-calibration, which the runner carries "
                         "into matrix.json and analysis/jobs.py refuses to "
                         "score as a reportable objective.")
    args = ap.parse_args()

    mechs = args.mechanisms.split(",")
    for m in mechs:
        if m in NOT_IMPLEMENTED:
            print(f"REFUSED: mechanism {m} is declared but not implemented "
                  f"({NOT_IMPLEMENTED[m]}). Emitting it would run something else "
                  f"under its name.", file=sys.stderr)
            return 2
        if m not in MECHANISMS:
            print(f"REFUSED: unknown mechanism {m}", file=sys.stderr)
            return 2
    loads = [int(w) for w in args.workloads.split(",")]
    for w in loads:
        if w not in WORKLOAD_LEVELS:
            print(f"REFUSED: workload {w} is not a declared level "
                  f"{WORKLOAD_LEVELS}", file=sys.stderr)
            return 2
    # A workload level cannot be calibrated from a scenario file that requires
    # its own budget to already exist. That deadlock is what --for-calibration
    # exists to break, and the escape is narrow: the file is stamped, the runner
    # carries the stamp into matrix.json, and the objective refuses to score it.
    if not args.for_calibration:
        budgets = json.load(open("configs/budgets.json"))["budgets_ms"]
        for w in loads:
            if str(w) not in budgets:
                print(f"REFUSED: workload {w} has no calibrated latency budget "
                      f"in configs/budgets.json. Calibrate it first:\n"
                      f"  python3 scripts/gen_scenarios.py --n 2 --master-seed "
                      f"<seed> --mechanisms D1 \\\n"
                      f"    --workloads {w} --for-calibration --out "
                      f"configs/scenarios-cal-L{w}.json\n"
                      f"Borrowing another level's budget would make Y measure "
                      f"the load.", file=sys.stderr)
                return 2

    scenarios = draw(args.master_seed, args.n, mechs, loads)
    doc = {
        "master_seed": args.master_seed,
        "declared_levels": {
            "onset_range": list(ONSET_RANGE),
            "severity_levels": list(SEVERITY_LEVELS),
            "workload_levels": list(WORKLOAD_LEVELS),
            "mechanisms": mechs,
        },
        "scenarios": scenarios,
    }
    if args.for_calibration:
        doc["purpose"] = "budget-calibration"
    blob = json.dumps(doc, sort_keys=True).encode()
    doc["scenarios_hash"] = hashlib.sha256(blob).hexdigest()[:16]
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print(f"wrote {args.out}: {len(scenarios)} scenarios, "
          f"hash {doc['scenarios_hash']}")
    if args.for_calibration:
        print("  purpose=budget-calibration: this set measures a healthy "
              "latency distribution")
        print("  at an uncalibrated workload level. Its J_obs is not reportable "
              "and jobs.py")
        print("  refuses it; only analysis/calibrate_budget.py reads it.")
    for s in scenarios:
        print(f"  {s['scenario_id']}  {s['fault_type']}  onset {s['fault_onset']:2d}  "
              f"severity {s['fault_severity']:3d}  load {s['workload_level']:3d}  "
              f"seed {s['seed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
