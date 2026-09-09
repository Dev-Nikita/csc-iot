#!/usr/bin/env bash
# M2': the branch matrix.
#
#   30 anchors x 3 actions x 10 repeats = 900 branches
#
# One branch is one complete run of the topology from the same specification:
# the prefix is re-executed rather than snapshotted, which is what the prefix
# equality result licenses -- two runs from the same specification reach the same
# structural state at the same anchor, so the state an action is applied to is
# the same state in every branch of a cell.
#
# Repeats are what make the replay dispersion eta_J measurable: identical
# (anchor, action) branches differ only by the nondeterminism the system really
# has, and that spread is the reference against which any claimed effect must be
# large. Do NOT reduce the repeats to make the matrix finish sooner; a cell with
# one branch has no dispersion and therefore licenses no comparison.
#
# Output is append-only. Every branch writes into its own directory and the
# runner refuses to start if the experiment directory already exists.
set -euo pipefail

BIN="${BIN:-bin}"
STACK_ID="${STACK_ID:-}"                 # required: reportable runtime_stack_id
GIT_COMMIT="${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)}"
EXPERIMENT="${EXPERIMENT:-m2prime}"
ANCHORS="${ANCHORS:-30}"
REPEATS="${REPEATS:-10}"
ACTIONS="${ACTIONS:-NO_OP THROTTLE REROUTE}"
HORIZON="${HORIZON:-3}"
PERIOD="${PERIOD:-300ms}"
EVENTS="${EVENTS:-100}"
SEED="${SEED:-42}"
BUS_IMPL="${BUS_IMPL:-tcp}"
BUS_ADDR="${BUS_ADDR:-127.0.0.1:4300}"
ROOT="${ROOT:-data/raw}"

if [ "$BUS_IMPL" != "tcp" ]; then
  echo "FAIL: scripts/m2prime_matrix.sh is the local stdlib-TCP diagnostic runner."
  echo "Use scripts/m2prime_nats_matrix.sh for reportable Docker/NATS/netem runs."
  exit 2
fi

if [ -z "$STACK_ID" ]; then
  echo "STACK_ID is required: a branch that does not name the stack it ran on"
  echo "cannot be pooled with any other. Get it from check_reportable_stack.py."
  exit 2
fi

OUT="$ROOT/$STACK_ID/$EXPERIMENT"
if [ -e "$OUT" ]; then
  echo "FAIL: $OUT already exists. Runs are append-only; use EXPERIMENT=<new name>."
  exit 2
fi
mkdir -p "$OUT"
LOG="${LOG:-$OUT/logs}"
mkdir -p "$LOG"

cat > "$OUT/matrix.json" <<JSON
{
  "experiment": "$EXPERIMENT",
  "runtime_stack_id": "$STACK_ID",
  "git_commit": "$GIT_COMMIT",
  "anchors": $ANCHORS,
  "repeats": $REPEATS,
  "actions": "$ACTIONS",
  "horizon": $HORIZON,
  "events_per_epoch": $EVENTS,
  "master_seed": $SEED,
  "bus_impl": "$BUS_IMPL",
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

topology_up() { # topology_up <tag>
  local tag="$1"
  PIDS=()
  "$BIN/csc-broker" -addr "$BUS_ADDR" >"$LOG/$tag-broker.log" 2>&1 & PIDS+=($!)
  sleep 0.4
  for e in edge00 edge01 edge02; do
    case "$e" in
      edge00) CAP="${CAP00:-150}";;   # sized above the offered load, degrades at DEGRADE_AT
      edge01) CAP="${CAP01:-300}";;   # the relief path REROUTE moves work to
      *)      CAP="${CAP02:-200}";;
    esac
    "$BIN/csc-node" -role edge -id "$e" -bus-impl "$BUS_IMPL" -bus "$BUS_ADDR" \
      -serve-per-epoch "$CAP" -sla-epochs "${SLA_EPOCHS:-1}" -sla-ms "${SLA_MS:-500}" \
      $( [ "$e" = edge00 ] && echo "-degrade-at-epoch ${DEGRADE_AT:-4} -degraded-serve-per-epoch ${DEGRADED_SERVE:-60}" ) \
      >"$LOG/$tag-$e.log" 2>&1 & PIDS+=($!)
  done
  "$BIN/csc-node" -role gateway -id gw00 -bus-impl "$BUS_IMPL" -bus "$BUS_ADDR" -ingress 127.0.0.1:5000 -route edge00 >"$LOG/$tag-gw00.log" 2>&1 & PIDS+=($!)
  "$BIN/csc-node" -role gateway -id gw01 -bus-impl "$BUS_IMPL" -bus "$BUS_ADDR" -ingress 127.0.0.1:5001 -route edge01 >"$LOG/$tag-gw01.log" 2>&1 & PIDS+=($!)
  "$BIN/csc-intelligence" -addr 127.0.0.1:50051 -delay 5ms >"$LOG/$tag-intel.log" 2>&1 & PIDS+=($!)
  "$BIN/csc-node" -role controller -id ctl -bus-impl "$BUS_IMPL" -bus "$BUS_ADDR" -rpc 127.0.0.1:50051 >"$LOG/$tag-ctl.log" 2>&1 & PIDS+=($!)
  sleep 0.8
  "$BIN/csc-node" -role device-sim -id dev-sim -bus-impl "$BUS_IMPL" -bus "$BUS_ADDR" \
     -ingress 127.0.0.1:5000 -devices 100 -events-per-epoch "$EVENTS" -seed "$SEED" \
     -emit-spread "${EMIT_SPREAD:-200ms}" \
     >"$LOG/$tag-dev.log" 2>&1 & PIDS+=($!)
  sleep 0.4
}
topology_down() {
  for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
  sleep 0.3
}
trap topology_down EXIT

total=0; failed=0
for a in $(seq 1 "$ANCHORS"); do
  for action in $ACTIONS; do
    for r in $(seq 1 "$REPEATS"); do
      total=$((total+1))
      branch="a$(printf %02d "$a")-$action-r$(printf %02d "$r")"
      dir="$OUT/$branch"
      tag="$branch"
      topology_up "$tag"
      if ! "$BIN/csc-orchestrator" -bus "$BUS_ADDR" -bus-impl "$BUS_IMPL" \
           -anchor "$a" -horizon "$HORIZON" -epochs $((a+HORIZON)) -period "$PERIOD" \
           -action "$action" -action-target gw00 -action-edge edge01 -action-limit 50 \
           -runtime-stack-id "$STACK_ID" -git-commit "$GIT_COMMIT" \
           -config-hash "$EXPERIMENT" -branch-id "$branch" \
           -out-dir "$dir" >"$LOG/$tag-orch.log" 2>&1; then
        failed=$((failed+1))
        # A refused branch is recorded, not silently retried: the exclusion
        # policy is decided before the results are looked at, and a branch that
        # was dropped without a trace cannot be excluded honestly.
        mkdir -p "$dir"
        { echo "branch=$branch"; echo "status=refused"; tail -20 "$LOG/$tag-orch.log"; } \
          > "$dir/REFUSED.txt"
        echo "REFUSED $branch"
      else
        echo "ok       $branch  $(python3 -c "import json;print(json.load(open('$dir/outcome.json'))['hash'][:16])" 2>/dev/null || echo '-')"
      fi
      topology_down
    done
  done
done

echo
echo "branches: $total, refused: $failed"
if [ "$HORIZON" -eq 0 ]; then
  python3 analysis/m2prime_report.py --prefix-only "$OUT"
else
  python3 analysis/m2prime_report.py "$OUT"
fi
[ "$failed" -eq 0 ] || exit 1
