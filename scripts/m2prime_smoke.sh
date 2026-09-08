#!/usr/bin/env bash
# M2' step one: do two runs from the same prefix specification reach the same
# structural state at the same anchor?
#
# This runs against the local process topology (stdlib broker) so it can be
# exercised without Docker. The reportable version runs against the NATS stack;
# the question it asks is identical and the answer may not be.
set -euo pipefail
BIN="${BIN:-bin}"
LOG="${LOG:-/tmp/csc-m2prime}"
ANCHOR="${ANCHOR:-5}"
EPOCHS="${EPOCHS:-8}"
mkdir -p "$LOG"; rm -f "$LOG"/*.log "$LOG"/*.json

run_once() { # run_once <label>
  local label="$1" pids=()
  "$BIN/csc-broker" -addr 127.0.0.1:4300 >"$LOG/$label-broker.log" 2>&1 & pids+=($!)
  sleep 0.5
  for e in edge00 edge01 edge02; do
    "$BIN/csc-node" -role edge -id "$e" -bus 127.0.0.1:4300 >"$LOG/$label-$e.log" 2>&1 & pids+=($!)
  done
  "$BIN/csc-node" -role gateway -id gw00 -bus 127.0.0.1:4300 -ingress 127.0.0.1:5000 -route edge00 >"$LOG/$label-gw00.log" 2>&1 & pids+=($!)
  "$BIN/csc-node" -role gateway -id gw01 -bus 127.0.0.1:4300 -ingress 127.0.0.1:5001 -route edge01 >"$LOG/$label-gw01.log" 2>&1 & pids+=($!)
  "$BIN/csc-intelligence" -addr 127.0.0.1:50051 -delay 5ms >"$LOG/$label-intel.log" 2>&1 & pids+=($!)
  "$BIN/csc-node" -role controller -id ctl -bus 127.0.0.1:4300 -rpc 127.0.0.1:50051 >"$LOG/$label-ctl.log" 2>&1 & pids+=($!)
  sleep 1.0
  "$BIN/csc-node" -role device-sim -id dev-sim -bus 127.0.0.1:4300 \
     -ingress 127.0.0.1:5000 -devices 100 -events-per-epoch 200 -seed 42 \
     >"$LOG/$label-dev.log" 2>&1 & pids+=($!)
  sleep 0.5

  "$BIN/csc-orchestrator" -bus 127.0.0.1:4300 -bus-impl tcp \
     -nodes gw00,gw01,edge00,edge01,edge02,ctl,dev-sim \
     -anchor "$ANCHOR" -epochs "$EPOCHS" -period 300ms \
     -out "$LOG/$label-anchor.json" >"$LOG/$label-orch.log" 2>&1 || true

  for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
  sleep 0.7
}

echo "run A"; run_once A
echo "run B"; run_once B

for l in A B; do
  if ! [ -s "$LOG/$l-anchor.json" ]; then
    echo "FAIL: run $l produced no anchor fingerprint"; tail -12 "$LOG/$l-orch.log"; exit 1
  fi
done

HA=$(python3 -c "import json,sys;print(json.load(open('$LOG/A-anchor.json'))['hash'])")
HB=$(python3 -c "import json,sys;print(json.load(open('$LOG/B-anchor.json'))['hash'])")
echo
echo "run A anchor hash: ${HA:0:32}"
echo "run B anchor hash: ${HB:0:32}"
if [ "$HA" = "$HB" ]; then
  echo "MATCH: two distributed runs reached an identical structural state at the anchor."
else
  echo "DIVERGED. This is the measurement, not a failure -- these are the fields that differ:"
  python3 - "$LOG/A-anchor.json" "$LOG/B-anchor.json" <<'PY'
import json,sys
a=json.load(open(sys.argv[1]))["state"]; b=json.load(open(sys.argv[2]))["state"]
for section in ("queues","seq_positions","processed_counts","routing","rate_tokens"):
    ka, kb = a.get(section) or {}, b.get(section) or {}
    for k in sorted(set(ka)|set(kb)):
        va, vb = ka.get(k), kb.get(k)
        if va != vb:
            print(f"  {section}[{k}]: {va} != {vb}")
PY
fi
