#!/usr/bin/env bash
# Reportable M2' runner: Docker/NATS, one fresh topology per branch, fixed netem.
# A fresh topology is mandatory because run_id isolates protocol messages but
# does not reset gateway counters, backlogs, routing, or edge processed state.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.nats.yml}"
BIN="${BIN:-bin}"
# Derived here when it is not already in the environment, exactly as
# scripts/run_nightly.sh does it. Before this, a direct invocation required the
# caller to export STACK_ID by hand, and setting a similarly named shell variable
# instead -- STACK=... -- failed with "STACK_ID is required (run make stack-nats
# first)" on a stack that was up and validated. An error that names the wrong
# cause costs more than the check saves.
# Same guard as scripts/run_nightly.sh: a stale STACK_ID in the environment was
# believed and stamped a run with a five-day-old stack id.
LIVE_STACK="$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)"
if [ -n "${STACK_ID:-}" ] && [ -n "$LIVE_STACK" ] && [ "$STACK_ID" != "$LIVE_STACK" ]; then
  echo "FAIL: STACK_ID=$STACK_ID in the environment, but the validated stack is"
  echo "      $LIVE_STACK. Do not set STACK_ID by hand; it is derived."
  echo "      Clear it and try again:  unset STACK_ID"
  exit 2
fi
STACK_ID="${STACK_ID:-$LIVE_STACK}"
# The experiment name is accepted as the first positional argument as well as
# through the environment. Only the environment worked before, so
#   bash scripts/m2prime_nats_matrix.sh windowed-pilot-v1
# silently used the default name and the append-only guard refused, naming a
# directory nobody had asked for. scripts/run_nightly.sh takes the name
# positionally, so the two interfaces disagreed; they no longer do.
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
  EXPERIMENT="$1"
  shift
fi
EXPERIMENT="${EXPERIMENT:-m2prime-nats}"
ANCHORS="${ANCHORS:-30}"
# An anchor LIST, when the anchors must reach past the fault onsets. With onsets
# drawn from 8-24, anchors 1..8 put 115 of 192 scenario-anchor pairs before the
# fault and exactly 1 after it, so the post-onset regime -- where the value of
# intervening decays with delay -- would be absent from the design. A spread
# list covers all three regimes at the same branch count.
ANCHOR_LIST="${ANCHOR_LIST:-}"
REPEATS="${REPEATS:-10}"
ACTIONS="${ACTIONS:-NO_OP THROTTLE REROUTE}"
HORIZON="${HORIZON:-3}"
PERIOD="${PERIOD:-300ms}"
# 100 events/epoch against edge00's 150 leaves headroom: the system meets its
# agreement until the fault. At 200 it was saturated from the first epoch, there
# was no healthy state, and no action could prevent anything -- every anchor sat
# on the same overload ramp. This default is part of the declared configuration.
EVENTS="${EVENTS:-100}"
# Emission is paced across the epoch rather than burst: a burst gives a whole
# batch the same latency, so the violated fraction moves in steps of one batch
# and that step becomes the measured replay dispersion.
EMIT_SPREAD="${EMIT_SPREAD:-200ms}"
# The latency budget is a declared parameter: it must sit ABOVE the healthy
# distribution, and it is recorded in the matrix manifest so a run can never be
# compared with one that promised something else.
# The budget is no longer a runner parameter. It is looked up per workload level
# from configs/budgets.json, because the healthy per-event latency distribution
# depends on load and one budget across levels would make Y measure the load.
if [ -n "${SLA_MS:-}" ]; then
  echo "FAIL: SLA_MS is set in the environment."
  echo "      The budget comes from configs/budgets.json for the scenario's"
  echo "      workload level, not from a variable. Changing it needs an amendment."
  exit 2
fi
# The scenario set is declared before the run by scripts/gen_scenarios.py.
SCENARIOS="${SCENARIOS:-}"
SEED="${SEED:-42}"
NETEM_SEED="${NETEM_SEED:-424242}"
ROOT="${ROOT:-data/raw}"
GIT_COMMIT="${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || sed -n '1p' SOURCE_REVISION 2>/dev/null || echo unknown)}"

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

[ -x "$BIN/csc-orchestrator" ] || { echo "FAIL: build bin/ with -tags=nats first"; exit 2; }
[ -x "$BIN/csc-stackstamp" ] || { echo "FAIL: build bin/csc-stackstamp first"; exit 2; }
[ -n "$STACK_ID" ] || {
  echo "FAIL: no reportable stack. The id is derived from"
  echo "      check_reportable_stack.py, which found none validated."
  echo "      Run: make up-nats && make stack-nats"
  exit 2
}

[ -n "$SCENARIOS" ] || {
  echo "FAIL: SCENARIOS=<file> is required."
  echo "      Generate it first, e.g.:"
  echo "        python3 scripts/gen_scenarios.py --n 3 --master-seed 20260926 \\"
  echo "          --mechanisms D1 --workloads 100 --out configs/scenarios-pilot.json"
  echo "      A run with one fixed fault cannot support a generalisation claim."
  exit 2
}
[ -f "$SCENARIOS" ] || { echo "FAIL: $SCENARIOS not found"; exit 2; }
[ -f configs/budgets.json ] || { echo "FAIL: configs/budgets.json not found"; exit 2; }
# Every workload level in the scenario set must have a calibrated budget.
python3 - "$SCENARIOS" <<'GUARD' || exit 2
import json, sys
sc = json.load(open(sys.argv[1]))
budgets = json.load(open("configs/budgets.json"))["budgets_ms"]
# A budget-calibration set exists precisely to measure a level that has no
# budget yet: requiring one would be a deadlock. The escape is narrow -- the
# stamp travels into matrix.json and analysis/jobs.py refuses to score it.
if sc.get("purpose") == "budget-calibration":
    print("NOTE: purpose=budget-calibration. Running with a placeholder budget; "
          "this matrix", file=sys.stderr)
    print("      is not reportable and jobs.py will refuse it.", file=sys.stderr)
    raise SystemExit(0)
missing = sorted({str(s["workload_level"]) for s in sc["scenarios"]} - set(budgets))
if missing:
    print("FAIL: no calibrated latency budget for workload level(s) "
          + ", ".join(missing), file=sys.stderr)
    print("      Run the calibration first; borrowing another level's budget "
          "would make Y measure the load.", file=sys.stderr)
    raise SystemExit(2)
GUARD

# A stale binary produces a plausible-looking matrix that is missing whatever
# the newest code records. It happened: 27 branches completed cleanly and every
# outcome.json lacked the observed block, because bin/ predated the orchestrator
# that writes it. Newer source than binary is a hard stop.
if [ -n "$(find cmd internal -name '*.go' -newer "$BIN/csc-orchestrator" -print -quit 2>/dev/null)" ]; then
  echo "FAIL: $BIN/csc-orchestrator is older than the Go sources."
  echo "      Run: make build TAGS=nats"
  exit 2
fi

# Heterogeneous edge capacity is part of the declared configuration, not an
# optimisation. Without it REROUTE moves work to an identical node and measures
# zero effect however many branches are run.
if ! grep -q 'serve-per-epoch' "$COMPOSE_FILE"; then
  echo "FAIL: $COMPOSE_FILE does not configure -serve-per-epoch on the edges."
  echo "      With equal capacity REROUTE cannot change any outcome."
  exit 2
fi
[ "$GIT_COMMIT" != unknown ] || { echo "FAIL: GIT_COMMIT or SOURCE_REVISION is required"; exit 2; }

# The latency budget is frozen in EXPERIMENT_PROTOCOL.md section 2a and is the
# same promise on every edge. It was not: edge01 and edge02 carried a hardcoded
# 500 while only edge00 read the variable, so an action that moves work between
# edges would have been scored against a different budget than the baseline.
if grep -o '\-sla-ms", "[^"]*"' "$COMPOSE_FILE" | sort -u | grep -qv "SLA_MS"; then
  echo "FAIL: $COMPOSE_FILE hardcodes a latency budget on some edge."
  echo "      Every edge must read \${SLA_MS}, or the budget differs by path."
  exit 2
fi

python3 check_reportable_stack.py --expect-stack-id "$STACK_ID" >/dev/null

if [ -n "$ANCHOR_LIST" ]; then
  ANCHOR_SPEC="$(echo "$ANCHOR_LIST" | tr -d ' ')"
  ANCHOR_SEQ="$(echo "$ANCHOR_SPEC" | tr ',' ' ')"
else
  ANCHOR_SPEC="1..$ANCHORS"
  ANCHOR_SEQ="$(seq 1 "$ANCHORS")"
fi
ANCHOR_COUNT="$(echo "$ANCHOR_SEQ" | wc -w)"
SCENARIOS_HASH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["scenarios_hash"])' "$SCENARIOS")"
SCENARIO_COUNT="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["scenarios"]))' "$SCENARIOS")"
OUT="$ROOT/$STACK_ID/$EXPERIMENT"
[ ! -e "$OUT" ] || { echo "FAIL: $OUT exists; experiments are append-only"; exit 2; }
mkdir -p "$OUT"
CONFIG_HASH="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16])' \
  "$ANCHOR_SPEC|$REPEATS|$ACTIONS|$HORIZON|$PERIOD|$EMIT_SPREAD|$SEED|$NETEM_SEED|$SCENARIOS_HASH")"

cat > "$OUT/matrix.json" <<JSON
{
  "experiment": "$EXPERIMENT",
  "runtime_stack_id": "$STACK_ID",
  "git_commit": "$GIT_COMMIT",
  "config_hash": "$CONFIG_HASH",
  "anchors": $ANCHORS,
  "anchor_spec": "$ANCHOR_SPEC",
  "anchor_count": $ANCHOR_COUNT,
  "repeats": $REPEATS,
  "actions": "$ACTIONS",
  "horizon": $HORIZON,
  "period": "$PERIOD",
  "emit_spread": "$EMIT_SPREAD",
  "scenarios_file": "$SCENARIOS",
  "scenarios_hash": "$SCENARIOS_HASH",
  "scenario_count": $SCENARIO_COUNT,
  "purpose": "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("purpose","reportable"))' "$SCENARIOS")",
  "master_seed": $SEED,
  "netem_seed": $NETEM_SEED,
  "bus_impl": "nats",
  "fresh_topology_per_branch": true,
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

cp "$SCENARIOS" "$OUT/scenarios.json"
export EMIT_SPREAD COMPOSE_FILE
cleanup() { compose down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

run_branch() {
  local sidx="$1" anchor="$2" action="$3" repeat="$4" branch dir version transport_hash
  # Every factor of the scenario is read from the declared set, never inferred
  # from the branch name, and every one is written into the branch's own
  # manifest so no analysis has to parse a name to know what it ran.
  local sid mech onset sev load sseed sla relief gwadmit edgefault
  eval "$(python3 - "$SCENARIOS" "$sidx" <<'ENV'
import json, sys
sc = json.load(open(sys.argv[1]))["scenarios"][int(sys.argv[2]) - 1]
budgets = json.load(open("configs/budgets.json"))["budgets_ms"]
print(f"sid={sc['scenario_id']}")
print(f"mech={sc['fault_type']}")
print(f"onset={sc['fault_onset']}")
print(f"sev={sc['fault_severity']}")
print(f"load={sc['workload_level']}")
print(f"sseed={sc['seed']}")
# D4 degrades the relief path too; D5 degrades the gateway's admission. Both
# default to "no fault" so every other mechanism is bit-identical to before.
print(f"relief={sc.get('relief_degraded_serve', -1)}")
print(f"gwadmit={sc.get('degraded_admit', -1)}")
print(f"edgefault={sc.get('edge_faulted', 1)}")
# PLACEHOLDER_SLA_MS is deliberately absurd rather than plausible: a
# calibration run must not carry a number anyone could mistake for a promise,
# and the per-event histogram the calibration reads does not depend on it.
doc = json.load(open(sys.argv[1]))
if doc.get("purpose") == "budget-calibration":
    print("sla=999999")
else:
    print(f"sla={budgets[str(sc['workload_level'])]['sla_ms']}")
ENV
)"
  branch="$sid-a$(printf %02d "$anchor")-$action-r$(printf %02d "$repeat")"
  dir="$OUT/$branch"
  mkdir -p "$dir"
  # The scenario is fixed within a cell and across the actions compared at an
  # anchor: repeats are replays of one prefix, and actions must share that
  # prefix to be comparable at all.
  # A mechanism may declare that the EDGE is not faulted -- D5 faults only the
  # gateway, and degrading an edge as well would hide the thing it tests.
  if [ "$edgefault" -eq 0 ]; then
    export DEGRADE_AT=0 DEGRADED_SERVE=-1
  else
    export DEGRADE_AT="$onset" DEGRADED_SERVE="$sev"
  fi
  export EVENTS_PER_EPOCH="$load" MASTER_SEED="$sseed" SLA_MS="$sla"
  # The relief path and the gateway are faulted only where the mechanism says
  # so. A -1 leaves the container at its default, which is no fault at all.
  if [ "$relief" -ge 0 ]; then
    export DEGRADE_AT_E01="$onset" DEGRADED_SERVE_E01="$relief"
  else
    export DEGRADE_AT_E01=0 DEGRADED_SERVE_E01=-1
  fi
  if [ "$gwadmit" -ge 0 ]; then
    export DEGRADE_ADMIT_AT="$onset" DEGRADED_ADMIT="$gwadmit"
  else
    export DEGRADE_ADMIT_AT=0 DEGRADED_ADMIT=-1
  fi
  python3 - "$dir/scenario.json" "$sid" "$mech" "$onset" "$sev" "$load" \
           "$sseed" "$sla" "$anchor" "$action" "$repeat" "$HORIZON" \
           "$relief" "$gwadmit" "$edgefault" <<'MANIFEST'
import json, sys
(out, sid, mech, onset, sev, load, seed, sla, anchor, action, repeat, horizon,
 relief, gwadmit, edgefault) = sys.argv[1:]
onset, anchor, horizon = int(onset), int(anchor), int(horizon)
# The regime is a property of the branch's own numbers, not of its anchor index.
if onset > anchor + horizon:
    regime = "pre-fault"
elif onset <= anchor:
    regime = "post-onset"
else:
    regime = "spanning"
json.dump({
    "scenario_id": sid, "fault_type": mech, "fault_onset": onset,
    "fault_severity": int(sev), "workload_level": int(load), "seed": int(seed),
    "sla_ms": int(sla), "anchor": anchor, "action": action,
    "repeat": int(repeat), "horizon": horizon, "regime": regime,
    # -1 means the mechanism declares no such fault. Written for every branch so
    # no analysis has to infer a mechanism's parameters from its name.
    "relief_degraded_serve": int(relief), "degraded_admit": int(gwadmit),
    "edge_faulted": int(edgefault),
}, open(out, "w"), indent=2, sort_keys=True)
MANIFEST
  cleanup
  # Bringing nine containers up occasionally fails transiently: a node exits
  # before the bus accepts it and --wait gives up. On a 900-branch matrix a
  # single such failure would otherwise end the whole run.
  #
  # The retry is bounded and RECORDED. A silent retry would hide a topology that
  # is becoming unreliable, which is exactly the kind of thing that must appear
  # in the evidence rather than in nobody's memory.
  local attempt=0 started=0
  while [ "$attempt" -lt "${STARTUP_ATTEMPTS:-3}" ]; do
    attempt=$((attempt+1))
    if compose up -d --force-recreate --wait --wait-timeout 90 --no-build \
         >>"$dir/compose-up.log" 2>&1; then
      started=1
      break
    fi
    echo "--- attempt $attempt failed; recreating" >>"$dir/compose-up.log"
    compose ps -a >>"$dir/compose-up.log" 2>&1 || true
    compose logs --tail 20 >>"$dir/compose-up.log" 2>&1 || true
    cleanup
    sleep 3
  done
  echo "{\"startup_attempts\": $attempt}" > "$dir/startup.json"
  if [ "$started" -ne 1 ]; then
    echo "compose startup failed after $attempt attempts" >"$dir/REFUSED.txt"; return 1
  fi
  if [ "$attempt" -gt 1 ]; then
    echo "note: $branch needed $attempt startup attempts" >&2
  fi
  if ! KEEP=1 NETEM_SEED="$NETEM_SEED" COMPOSE="docker compose -f $COMPOSE_FILE" \
       scripts/netem_smoke.sh >"$dir/netem.log" 2>&1; then
    echo "netem validation failed" >"$dir/REFUSED.txt"; return 1
  fi
  version="$(compose exec -T nats nats-server -v 2>/dev/null | tr -d '\r')"
  transport_hash="$(python3 -c 'import hashlib; print(hashlib.sha256(b"nats-core-pubsub;jetstream=false").hexdigest()[:16])')"
  if ! "$BIN/csc-stackstamp" -bus nats -bus-version "$version" \
       -transport-hash "$transport_hash" -netem-service device-sim \
       -out "$dir/stack.json" >"$dir/stackstamp.log" 2>&1; then
    echo "stack stamp failed" >"$dir/REFUSED.txt"; return 1
  fi
  if ! python3 check_reportable_stack.py --stamp "$dir/stack.json" \
       --expect-stack-id "$STACK_ID" >"$dir/stack-check.log" 2>&1; then
    echo "runtime stack changed or is non-reportable" >"$dir/REFUSED.txt"; return 1
  fi
  if ! "$BIN/csc-orchestrator" -bus nats://127.0.0.1:4222 -bus-impl nats \
       -nodes gw00,gw01,edge00,edge01,edge02,ctl,dev-sim \
       -anchor "$anchor" -horizon "$HORIZON" -epochs $((anchor+HORIZON)) \
       -period "$PERIOD" -timeout 90s -action "$action" -action-target gw00 \
       -action-edge edge01 -action-limit 50 -runtime-stack-id "$STACK_ID" \
       -git-commit "$GIT_COMMIT" -config-hash "$CONFIG_HASH" \
       -branch-id "$branch" -out-dir "$dir" >"$dir/orchestrator.log" 2>&1; then
    compose logs --no-color >"$dir/compose.log" 2>&1 || true
    echo "orchestrator refused branch; see orchestrator.log" >"$dir/REFUSED.txt"
    return 1
  fi
  compose logs --no-color >"$dir/compose.log" 2>&1 || true

  # The objective is computed over work accepted at the GATEWAY. A gateway
  # binary that does not report it sends the analysis silently back to the
  # edge-side denominator, which scores an action that refuses work only on the
  # part it let through. Checked on the first branch, not after 900.
  # The fault must reach the container. It travels through compose variable
  # substitution, which can fall back to its defaults without saying so, and
  # then every branch would run the same fault while every manifest claimed a
  # different one. Checked on every branch: it costs nothing and the failure it
  # catches would invalidate the whole design.
  if ! python3 - "$dir" <<'FAULTCHK'
import json, sys, os
d = sys.argv[1]
want = json.load(open(os.path.join(d, "scenario.json")))
a = json.load(open(os.path.join(d, "anchor.json")))
cap = a["state"]["edge_capacity"]
obs = a.get("observed") or {}
onset = want["fault_onset"]
bad = []


def pair(src, node, k1, k2, label):
    """The declared pair as the NODE reported it.

    Resolved by key suffix over whatever node reported it, not by a node id
    spelled here: the first version of this check looked for 'gateway00', the
    compose SERVICE name, while the node's id is 'gw00', so the keys read as
    absent. A missing observable is reported as missing rather than compared
    against a default, because a default turns a check that cannot see its
    subject into a check that quietly passes.
    """
    got = {}
    for k in (k1, k2):
        hits = [v for key, v in src.items()
                if key == node + "/" + k or key.endswith("/" + k)]
        if not hits:
            bad.append("%s: no node reports %s, so the fault cannot be "
                       "verified at all" % (label, k))
            return None
        got[k] = int(hits[0])
    return (got[k1], got[k2])


# The loaded edge. A mechanism that declares NO edge fault must find the edge
# healthy: a substitution that left a previous scenario's fault in place would
# otherwise turn a gateway mechanism into an edge mechanism without saying so,
# and the manifest would still claim the gateway.
exp = (onset, int(want["fault_severity"])) if int(want["edge_faulted"]) else (0, -1)
ran = pair(cap, "edge00", "degrade_at_epoch", "degraded_serve", "edge00")
if ran is not None and ran != exp:
    bad.append("edge00: declared %s but the node ran %s" % (exp, ran))

# The relief path. D4 exists only because this edge is degraded BELOW the loaded
# one. If the parameter fails to arrive, rerouting stays beneficial and D4
# silently becomes D1 -- the exact defect the mechanism was written to remove.
if int(want["relief_degraded_serve"]) >= 0:
    exp = (onset, int(want["relief_degraded_serve"]))
    ran = None
    k1, k2 = "edge01/degrade_at_epoch", "edge01/degraded_serve"
    if k1 in cap and k2 in cap:
        ran = (int(cap[k1]), int(cap[k2]))
    else:
        bad.append("edge01 (relief path): the edge reports no degradation "
                   "parameters, so the relief path cannot be verified")
    if ran is not None and ran != exp:
        bad.append("edge01 (relief path): declared %s but the node ran %s"
                   % (exp, ran))

# The gateway. Reported under observed, not under edge_capacity: an admission
# cap the operator suffers is not structural service capacity.
if int(want["degraded_admit"]) >= 0:
    exp = (onset, int(want["degraded_admit"]))
    ran = pair(obs, "gw00", "degrade_admit_at_epoch", "degraded_admit",
               "gateway (gw00)")
    if ran is not None and ran != exp:
        bad.append("gateway (gw00): declared %s but the node ran %s" % (exp, ran))

# A branch that declares a fault nowhere is a healthy run wearing a scenario id.
if not int(want["edge_faulted"]) and int(want["degraded_admit"]) < 0:
    bad.append("scenario declares neither an edge fault nor a gateway fault")

if bad:
    for b in bad:
        print(b, file=sys.stderr)
    raise SystemExit(1)
FAULTCHK
  then
    echo "FAIL: $branch ran a different fault than its scenario declares."
    echo "      The parameters did not reach the container: check that"
    echo "      $COMPOSE_FILE substitutes DEGRADE_AT / DEGRADED_SERVE (edge00),"
    echo "      DEGRADE_AT_E01 / DEGRADED_SERVE_E01 (relief path, D4) and"
    echo "      DEGRADE_ADMIT_AT / DEGRADED_ADMIT (gateway, D5)."
    echo "fault did not reach the container" >"$dir/REFUSED.txt"
    return 1
  fi

  missing="$(python3 -c "
import json,sys
o = json.load(open(sys.argv[1])).get('observed') or {}
need = ('/ingress_accepted', '/unserved_eligible', '/served', '/lat_ms_violations')
print(' '.join(s.lstrip('/') for s in need
                if not any(k.endswith(s) for k in o)))" "$dir/outcome.json")"
  if [ -n "$missing" ]; then
    echo "FAIL: $branch records no $missing."
    echo "      Every observable the objective reads must be present, or the"
    echo "      analysis substitutes a different one. Run: make build TAGS=nats"
    echo "missing observables: $missing" >"$dir/REFUSED.txt"
    return 1
  fi
  echo "ok $branch"
}

for sidx in $(seq 1 "$SCENARIO_COUNT"); do
  for anchor in $ANCHOR_SEQ; do
    for action in $ACTIONS; do
      for repeat in $(seq 1 "$REPEATS"); do
        if ! run_branch "$sidx" "$anchor" "$action" "$repeat"; then
          echo "REFUSED scenario $sidx a$(printf %02d "$anchor")-$action-r$(printf %02d "$repeat")"
          echo "FAIL FAST: the incomplete matrix remains on disk for diagnosis"
          exit 1
        fi
      done
    done
  done
done
cleanup

if [ "$HORIZON" -eq 0 ]; then
  python3 analysis/m2prime_report.py --prefix-only "$OUT" | tee "$OUT/report.txt"
else
  python3 analysis/m2prime_report.py "$OUT" | tee "$OUT/report.txt"
fi
