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
SLA_MS="${SLA_MS:-500}"
SEED="${SEED:-42}"
NETEM_SEED="${NETEM_SEED:-424242}"
ROOT="${ROOT:-data/raw}"
GIT_COMMIT="${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || sed -n '1p' SOURCE_REVISION 2>/dev/null || echo unknown)}"

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

[ -x "$BIN/csc-orchestrator" ] || { echo "FAIL: build bin/ with -tags=nats first"; exit 2; }
[ -x "$BIN/csc-stackstamp" ] || { echo "FAIL: build bin/csc-stackstamp first"; exit 2; }
[ -n "$STACK_ID" ] || { echo "FAIL: STACK_ID is required (run make stack-nats first)"; exit 2; }

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

python3 check_reportable_stack.py --expect-stack-id "$STACK_ID" >/dev/null

OUT="$ROOT/$STACK_ID/$EXPERIMENT"
[ ! -e "$OUT" ] || { echo "FAIL: $OUT exists; experiments are append-only"; exit 2; }
mkdir -p "$OUT"
CONFIG_HASH="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16])' \
  "$ANCHORS|$REPEATS|$ACTIONS|$HORIZON|$PERIOD|$EVENTS|$EMIT_SPREAD|$SLA_MS|$SEED|$NETEM_SEED")"

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
  "events_per_epoch": $EVENTS,
  "emit_spread": "$EMIT_SPREAD",
  "sla_ms": $SLA_MS,
  "master_seed": $SEED,
  "netem_seed": $NETEM_SEED,
  "bus_impl": "nats",
  "fresh_topology_per_branch": true,
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

export EVENTS_PER_EPOCH="$EVENTS" MASTER_SEED="$SEED" EMIT_SPREAD SLA_MS COMPOSE_FILE
cleanup() { compose down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

run_branch() {
  local anchor="$1" action="$2" repeat="$3" branch dir version transport_hash
  branch="a$(printf %02d "$anchor")-$action-r$(printf %02d "$repeat")"
  dir="$OUT/$branch"
  mkdir -p "$dir"
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
  echo "ok $branch"
}

for anchor in $(seq 1 "$ANCHORS"); do
  for action in $ACTIONS; do
    for repeat in $(seq 1 "$REPEATS"); do
      if ! run_branch "$anchor" "$action" "$repeat"; then
        echo "REFUSED a$(printf %02d "$anchor")-$action-r$(printf %02d "$repeat")"
        echo "FAIL FAST: the incomplete matrix remains on disk for diagnosis"
        exit 1
      fi
    done
  done
done
cleanup

if [ "$HORIZON" -eq 0 ]; then
  python3 analysis/m2prime_report.py --prefix-only "$OUT" | tee "$OUT/report.txt"
else
  python3 analysis/m2prime_report.py "$OUT" | tee "$OUT/report.txt"
fi
