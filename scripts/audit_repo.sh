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
# Called the helper by the wrong name and passed the test as one quoted string.
# Bash reported 'check: command not found', the script does not run with -e, and
# the failure counter was never touched -- so this line printed an error after
# REPO AUDIT OK and could never fail. A guard that cannot fail is not a guard.
chk "negative transport tests excluded from the nats build" \
  bash -c 'head -1 internal/bus/factory_notags_test.go | grep -q "go:build !nats"'

# Protocol 0.10. The structural model failed its preregistered sign test because
# the only rate observables were cumulative; these four lines are the fix, and a
# stale binary or a stale feature extractor would silently reinstate the failure.
chk "gateway reports a windowed arrival rate"     grep -q 'ingress_accepted_last_epoch' cmd/csc-node/main.go
chk "edge reports a windowed service rate"        grep -q 'served_last_epoch' cmd/csc-node/main.go
chk "features expose the windowed rates"          grep -q 'system_accepted_last_epoch' analysis/features.py
chk "features flag a missing windowed rate"       grep -q 'has_windowed_serve' analysis/features.py
chk "the structural model reads the windowed rate" grep -q 'system_accepted_last_epoch' analysis/structural.py
chk "the sign test is the declared structural test" grep -q 'surviving ALL FOUR bands' analysis/structural_signtest.py
# The nightly wrapper passed two pre-0.8 flags to the accounting audit, argparse
# rejected them, and '||' printed one line instead of stopping. The audit had
# never run in any nightly. A guard that cannot pass is worse than no guard.
chk "the nightly audit passes no obsolete flags" \
  bash -c '! grep -q "audit_accounting.py.*--healthy-anchors" scripts/run_nightly.sh'
chk "a failed accounting audit stops the analysis" grep -q 'audit-failed' scripts/run_nightly.sh
# Severity and workload were indexed by the same counter, so only three of nine
# combinations could appear and the two factors were aliased. Latent at one
# workload level; active the moment workload becomes a factor.
chk "severity and workload advance on different strides" \
  grep -q 'len(SEVERITY_LEVELS)) % len(workloads)' scripts/gen_scenarios.py
chk "the generator refuses aliased factors"       grep -q '_refuse_aliased_factors' scripts/gen_scenarios.py
# Sized as a leftover, the calibration split gives n=1, tau_hat=-inf, and a
# controller that abstains everywhere -- an artefact that reads as a finding.
chk "calibration runs are allocated first, not left over" \
  grep -q 'cal_runs=CAL_RUNS' analysis/predictor.py
chk "the calibration size is derived from equation 9" \
  grep -q 'def min_calibration_runs' analysis/predictor.py
# A workload level cannot be calibrated from a file that needs its own budget to
# exist. The escape is narrow and every part of it has to be present, or either
# the deadlock returns or a placeholder budget reaches a results table.
chk "the budget deadlock has a stamped escape"     grep -q 'for_calibration' scripts/gen_scenarios.py
chk "the runner carries the calibration stamp"     grep -q 'budget-calibration' scripts/m2prime_nats_matrix.sh
chk "the objective refuses a calibration matrix"   grep -q 'budget-calibration' analysis/jobs.py
chk "aliasing needs two levels on both factors"    grep -q 'min(count.values()) < 2' scripts/gen_scenarios.py

# Protocol 0.5-0.9. Each of these was written after a defect that invalidated a
# run, and each is here because a stale copy of the file would silently undo it.
chk "the objective refuses a missing observable"   grep -q 'no unserved_eligible in observed' analysis/jobs.py
chk "the objective refuses inconsistent accounting" grep -q 'accounting is inconsistent' analysis/jobs.py
chk "the edge reports eligible unserved work"      grep -q '"unserved_eligible": eligible' cmd/csc-node/main.go
chk "eligibility is taken from the event epoch"    grep -q 'q.tick < currentEpoch' cmd/csc-node/main.go
chk "the gateway reports what it accepted"         grep -q '"ingress_accepted":' cmd/csc-node/main.go
chk "every edge reads the frozen budget"           bash -c '! grep -o "\\-sla-ms\", \"[^\"]*\"" docker-compose.nats.yml | sort -u | grep -qv SLA_MS'
chk "the fault is a scenario factor"               grep -q 'DEGRADE_AT' docker-compose.nats.yml
chk "the runner verifies the fault reached the container" grep -q 'ran a different fault than its scenario declares' scripts/m2prime_nats_matrix.sh
chk "the audit bounds served work by the declared severity" grep -q 'declared degradation had no effect' analysis/audit_accounting.py
chk "the budget is looked up per workload level"   test -f configs/budgets.json
chk "features exclude the fault schedule"          grep -q 'FORBIDDEN_SUBSTRINGS' analysis/features.py
chk "a time-only baseline exists"                  grep -q 'TIME_ONLY' analysis/features.py
chk "leakage folds are held out by design point"   grep -q 'held out by DESIGN POINT' analysis/leakage_tests.py
chk "pre-fault needs a strict inequality"          grep -q 'onset > anchor + horizon' analysis/branches.py
echo
if [ "$fail" -eq 0 ]; then echo "REPO AUDIT OK"; else
  echo "REPO AUDIT FAILED -- a fixed file has probably been overwritten by an older copy."; fi
exit $fail
