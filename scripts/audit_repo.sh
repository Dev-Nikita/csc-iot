#!/usr/bin/env bash
# Invariants that have each been silently reverted at least once.
#
# Every check below corresponds to a real regression in this project, caused the
# same way: an archive unpacked over the repository carried an older copy of a
# file that had been fixed here. The individual fixes were fine; discovering
# them one failed build at a time was not. This runs in a second.
set -uo pipefail
fail=0
chk() { # chk <description> <test-command...>
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then printf '  ok    %s\n' "$desc"
  else printf '  FAIL  %s\n' "$desc"; fail=1; fi
}

echo "repository invariants"
chk "go.mod requires the NATS adapter"            grep -q 'nats-io/nats.go' go.mod
chk "go.sum present"                              test -f go.sum
chk "Dockerfile base matches the go directive"    bash -c '
    req=$(awk "/^go /{print \$2; exit}" go.mod)
    img=$(awk -F= "/^ARG GO_VERSION/{print \$2}" deploy/go.Dockerfile)
    case "$req" in "$img"*) exit 0;; *) exit 1;; esac'
chk "Dockerfile copies go.sum"                    grep -q 'COPY go.mod go.sum' deploy/go.Dockerfile
chk "Dockerfile honours GO_TAGS"                  grep -q 'tags "\${GO_TAGS}"' deploy/go.Dockerfile
chk "Dockerfile is not named *.go"                bash -c '! ls deploy/*.go >/dev/null 2>&1'
chk "netem script splits the @ifNN suffix"        grep -qF '/[@:]/' scripts/netem_smoke.sh
chk "netem script checks the control/bus interface" grep -q 'leaked onto the bus interface' scripts/netem_smoke.sh
chk "netem shapes the sender rather than reverse ACK path" grep -q 'SVC:-device-sim' scripts/netem_smoke.sh
chk "netem seed is fixed and recorded"            grep -q 'NETEM_SEED:-424242' scripts/netem_smoke.sh
chk "transport registry refuses unknown kinds"    grep -q 'not compiled into this binary' internal/bus/factory.go
chk "nats adapter is behind a build tag"          head -1 internal/bus/nats.go | grep -q 'go:build nats'
chk "stackstamp requires an explicit -bus"        grep -q '\-bus is required' cmd/csc-stackstamp/main.go
chk "reportable guard rejects the dev bus"        grep -q 'stdlib-tcp' check_reportable_stack.py
chk "terminology guard covers the md docs"        grep -q 'RESEARCH_SPEC.md' paper/check_stale.py
chk "citation guard checks literature.csv"        grep -q 'literature.csv' paper/check_citations.py
chk "netem script can keep the qdisc (KEEP=1)"    grep -q 'KEEP=1: leaving the qdisc' scripts/netem_smoke.sh
chk "stack-nats applies impairment first"         grep -q 'stack-nats: netem-apply' Makefile
chk "framed RPC does not block reportability"     bash -c '! grep -q "rpc_type.*stdlib-framed-tcp" <<<"$(sed -n "/^DEV_ONLY/p" check_reportable_stack.py)"'
chk "stamp records notes separately from blockers" grep -q 'Notes  ' cmd/csc-stackstamp/main.go
chk "device-sim joins the barrier (nats stack)"   grep -q 'events-per-epoch' docker-compose.nats.yml
chk "device-sim reaches the control plane"        grep -q 'device-gateway, control' docker-compose.nats.yml
chk "epoch markers ride the data path"            grep -q 'Marker closes an epoch IN BAND' cmd/csc-node/main.go
chk "orchestrator refuses an undrained anchor"    grep -q 'refusing to fingerprint an undrained transport' cmd/csc-orchestrator/main.go
chk "orchestrator is built with the nats tag"     grep -q 'run -tags=nats ./cmd/csc-orchestrator' Makefile
chk "nats port is reachable from the host"        grep -q '"4222:4222"' docker-compose.nats.yml
chk "stackstamp scans every interface"            grep -q 'scans every interface' cmd/csc-stackstamp/main.go
chk "nats Subscribe flushes before returning"     bash -c 'awk "/func .n .natsBus. Subscribe/,/^}/" internal/bus/nats.go | grep -q FlushTimeout'
chk "branch actions require acknowledgements"     grep -q 'SubjectControllerActionAcks' cmd/csc-orchestrator/main.go
chk "reportable branches recreate topology"       grep -q 'force-recreate' scripts/m2prime_nats_matrix.sh
chk "local matrix refuses to impersonate NATS"    grep -q 'local stdlib-TCP diagnostic runner' scripts/m2prime_matrix.sh
chk "M2 diagnostic is not named J_obs"            grep -q 'never the manuscript.*J_obs' analysis/m2prime_report.py
check "negative transport tests excluded from the nats build" \
  'head -1 internal/bus/factory_notags_test.go | grep -q "go:build !nats"'
echo
if [ "$fail" -eq 0 ]; then echo "REPO AUDIT OK"; else
  echo "REPO AUDIT FAILED -- a fixed file has probably been overwritten by an older copy."; fi
exit $fail
