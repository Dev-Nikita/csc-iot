#!/usr/bin/env bash
# Reportable M2' runner: Docker/NATS, one fresh topology per branch, fixed netem.
# A fresh topology is mandatory because run_id isolates protocol messages but
# does not reset gateway counters, backlogs, routing, or edge processed state.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.nats.yml}"
BIN="${BIN:-bin}"
STACK_ID="${STACK_ID:-}"
EXPERIMENT="${EXPERIMENT:-m2prime-nats}"
ANCHORS="${ANCHORS:-30}"
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
[ -n "$STACK_ID" ] || { echo "FAIL: STACK_ID is required (run make stack-nats first)"; exit 2; }

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

SCENARIOS_HASH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["scenarios_hash"])' "$SCENARIOS")"
SCENARIO_COUNT="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["scenarios"]))' "$SCENARIOS")"
OUT="$ROOT/$STACK_ID/$EXPERIMENT"
[ ! -e "$OUT" ] || { echo "FAIL: $OUT exists; experiments are append-only"; exit 2; }
mkdir -p "$OUT"
CONFIG_HASH="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16])' \
  "$ANCHORS|$REPEATS|$ACTIONS|$HORIZON|$PERIOD|$EMIT_SPREAD|$SEED|$NETEM_SEED|$SCENARIOS_HASH")"

cat > "$OUT/matrix.json" <<JSON
{
  "experiment": "$EXPERIMENT",
  "runtime_stack_id": "$STACK_ID",
  "git_commit": "$GIT_COMMIT",
  "config_hash": "$CONFIG_HASH",
  "anchors": $ANCHORS,
  "repeats": $REPEATS,
  "actions": "$ACTIONS",
  "horizon": $HORIZON,
  "period": "$PERIOD",
  "emit_spread": "$EMIT_SPREAD",
  "scenarios_file": "$SCENARIOS",
  "scenarios_hash": "$SCENARIOS_HASH",
  "scenario_count": $SCENARIO_COUNT,
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
  local sid mech onset sev load sseed sla
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
print(f"sla={budgets[str(sc['workload_level'])]['sla_ms']}")
ENV
)"
  branch="$sid-a$(printf %02d "$anchor")-$action-r$(printf %02d "$repeat")"
  dir="$OUT/$branch"
  mkdir -p "$dir"
  # The scenario is fixed within a cell and across the actions compared at an
  # anchor: repeats are replays of one prefix, and actions must share that
  # prefix to be comparable at all.
  export DEGRADE_AT="$onset" DEGRADED_SERVE="$sev" \
         EVENTS_PER_EPOCH="$load" MASTER_SEED="$sseed" SLA_MS="$sla"
  python3 - "$dir/scenario.json" "$sid" "$mech" "$onset" "$sev" "$load" \
           "$sseed" "$sla" "$anchor" "$action" "$repeat" "$HORIZON" <<'MANIFEST'
import json, sys
(out, sid, mech, onset, sev, load, seed, sla, anchor, action, repeat, horizon) = sys.argv[1:]
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
  for anchor in $(seq 1 "$ANCHORS"); do
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
