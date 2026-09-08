#!/usr/bin/env bash
# Start the A1a topology as real OS processes, without Docker.
#
# Useful in two situations: a machine with no Docker daemon, and as the fast
# check before spending minutes on an image build. It exercises exactly the
# concurrency that matters -- separate processes, real sockets, a transport that
# can reorder and delay -- and none of the container plumbing.
set -euo pipefail
BIN="${BIN:-bin}"
LOG="${LOG:-/tmp/csc-topology}"
RUN_S="${RUN_S:-8}"
mkdir -p "$LOG"; rm -f "$LOG"/*.log
pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; wait 2>/dev/null || true; }
trap cleanup EXIT

"$BIN/csc-broker" -addr 127.0.0.1:4300 >"$LOG/broker.log" 2>&1 & pids+=($!)
"$BIN/csc-intelligence" -addr 127.0.0.1:50051 -delay 5ms >"$LOG/intelligence.log" 2>&1 & pids+=($!)
sleep 0.6
for e in edge00 edge01 edge02; do
  "$BIN/csc-node" -role edge -id "$e" -bus 127.0.0.1:4300 >"$LOG/$e.log" 2>&1 & pids+=($!)
done
"$BIN/csc-node" -role gateway -id gw00 -bus 127.0.0.1:4300 -ingress 127.0.0.1:5000 >"$LOG/gw00.log" 2>&1 & pids+=($!)
"$BIN/csc-node" -role controller -id ctl -bus 127.0.0.1:4300 -rpc 127.0.0.1:50051 >"$LOG/ctl.log" 2>&1 & pids+=($!)
sleep 0.8
"$BIN/csc-node" -role device-sim -id dev-sim -ingress 127.0.0.1:5000 -devices 100 -rate-hz 4 >"$LOG/dev.log" 2>&1 & pids+=($!)

sleep "$RUN_S"

# Phase 1: with gw00 routed to edge00, only edge00 may be doing work. If every
# edge is busy the routing table is decorative and REROUTE would be a no-op
# dressed as an intervention -- which is precisely what an earlier version of
# this topology did, broadcasting to one shared subject.
fail=0
before00=$(grep -o "processed=[0-9]*" "$LOG/edge00.log" | tail -1 | cut -d= -f2)
before01=$(grep -o "processed=[0-9]*" "$LOG/edge01.log" | tail -1 | cut -d= -f2)
echo "--- before reroute: edge00=$before00 edge01=${before01:-0} ---"
[ "${before00:-0}" -gt 0 ] || { echo "FAIL: routed edge processed nothing"; fail=1; }
[ "${before01:-0}" -eq 0 ] || { echo "FAIL: an unrouted edge processed work; routing is not real"; fail=1; }

# Phase 2: reroute gw00 to edge01 and confirm the traffic actually moves.
"$BIN/csc-act" -bus 127.0.0.1:4300 -target gw00 -action REROUTE -edge edge01 >"$LOG/act.log" 2>&1 || true
sleep 4
after00=$(grep -o "processed=[0-9]*" "$LOG/edge00.log" | tail -1 | cut -d= -f2)
after01=$(grep -o "processed=[0-9]*" "$LOG/edge01.log" | tail -1 | cut -d= -f2)
echo "--- after reroute:  edge00=$after00 edge01=$after01 ---"
[ "${after01:-0}" -gt 0 ] || { echo "FAIL: REROUTE did not move traffic to edge01"; fail=1; }
grep -q "REROUTE edge00 -> edge01" "$LOG/gw00.log" || { echo "FAIL: gateway never applied the action"; fail=1; }

grep -q "telemetry samples=[1-9]" "$LOG/ctl.log" || { echo "FAIL: controller saw no telemetry"; fail=1; }
echo "--- gateway ---"; tail -2 "$LOG/gw00.log"
echo "--- controller ---"; tail -1 "$LOG/ctl.log"
[ "$fail" -eq 0 ] && echo "TOPOLOGY SMOKE OK" || { echo "TOPOLOGY SMOKE FAILED"; exit 1; }
