#!/usr/bin/env bash
# Start a long matrix so that nothing depends on the terminal staying alive.
#
# A terminal scrollback is not a record. It is truncated by the emulator, lost
# when the laptop sleeps and the SSH session drops, and gone entirely when the
# tmux server is killed. Every run started through this wrapper writes its
# complete output to a file on the server, runs detached from any session, and
# leaves a marker with its exit status. The laptop can sleep, the connection can
# die, tmux can be killed -- the run continues and the log is on disk.
#
#   bash scripts/run_nightly.sh m2prime-900 ANCHORS=30 REPEATS=10 HORIZON=8 \
#        ACTIONS="NO_OP THROTTLE REROUTE"
#
# Then, from anywhere, at any time:
#   bash scripts/run_nightly.sh --status
#   tail -f logs/<name>.log
set -uo pipefail

cd "$(dirname "$0")/.."
mkdir -p logs

if [ "${1:-}" = "--status" ]; then
  printf '%-28s %-10s %s\n' RUN STATUS "LAST LINE"
  for log in logs/*.log; do
    [ -e "$log" ] || continue
    name="$(basename "$log" .log)"
    # A live run is identified by its recorded pid, not by matching a command
    # line: the launcher quotes its environment assignments, so a pattern like
    # EXPERIMENT=$name never matched EXPERIMENT='$name' and every running job
    # was reported as stopped. An indicator that says a healthy run is dead is
    # worse than no indicator.
    pid=""
    [ -f "logs/$name.pid" ] && pid="$(cat "logs/$name.pid")"
    if [ -f "logs/$name.done" ]; then
      rc="$(cat "logs/$name.done")"
      case "$rc" in killed*) st="killed" ;; *) st="exit $rc" ;; esac
    elif [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      st="running"
    elif [ -n "$pid" ]; then
      st="died"
    else
      st="stopped?"
    fi
    printf '%-28s %-10s %s\n' "$name" "$st" "$(tail -1 "$log" | cut -c1-70)"
  done
  exit 0
fi

NAME="${1:?usage: run_nightly.sh <experiment-name> [VAR=value ...]}"
shift

LOG="logs/$NAME.log"
if [ -e "$LOG" ]; then
  echo "FAIL: $LOG exists. Logs are append-only evidence; choose another name."
  exit 2
fi

# Every matrix recreates the whole topology for each branch, so two runs on one
# Docker stack tear each other's containers down mid-branch and both data sets are
# void. Three were once launched at once -- a pilot and two budget calibrations --
# and nothing stopped it. Concurrency here is not slow, it is wrong.
for pidfile in logs/*.pid; do
  [ -e "$pidfile" ] || continue
  other="$(basename "$pidfile" .pid)"
  if kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "FAIL: '$other' is still running (pid $(cat "$pidfile"))."
    echo "      Every branch recreates the shared topology, so a second matrix"
    echo "      would destroy both runs' data rather than merely slow them down."
    echo "      Wait for it, or stop it: kill \$(cat $pidfile)"
    exit 2
  fi
done

# STACK_ID from the environment is taken on trust by every script here, and
# nothing checked it against reality. A stale value left in a shell -- set by
# hand while diagnosing something else -- stamped a whole run with the id of a
# stack from five days earlier, which mislabels its provenance and makes the data
# unusable. The id is derived, and an environment value that disagrees with the
# running stack is now refused rather than believed.
LIVE_STACK="$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)"
if [ -n "${STACK_ID:-}" ] && [ -n "$LIVE_STACK" ] && [ "$STACK_ID" != "$LIVE_STACK" ]; then
  echo "FAIL: STACK_ID=$STACK_ID in the environment, but the validated stack is"
  echo "      $LIVE_STACK. A run stamped with the wrong stack id records the"
  echo "      wrong substrate and cannot be reported. Do not set STACK_ID by"
  echo "      hand; it is derived. Clear it and try again:"
  echo "        unset STACK_ID"
  exit 2
fi
STACK_ID="${STACK_ID:-$LIVE_STACK}"
[ -n "$STACK_ID" ] || { echo "FAIL: no reportable stack. Run make stack-nats first."; exit 2; }

# Each VAR=value is re-quoted individually. Passing them through unquoted split
# ACTIONS="NO_OP THROTTLE REROUTE" into three words, and env took the second one
# as the command to run: "env: 'THROTTLE': No such file or directory".
ENVARGS=""
for kv in "$@"; do
  ENVARGS="$ENVARGS $(printf '%q' "$kv")"
done

# setsid detaches from the terminal's session entirely: closing the SSH
# connection sends no signal the run can die from, with or without tmux.
setsid bash -c "
  { echo \$\$ > 'logs/$NAME.pid'
    # A killed run must still leave its exit status behind: the .done file is
    # the only record once the terminal is gone.
    trap 'st=\$?; [ -f "logs/$NAME.done" ] || echo killed > "logs/$NAME.done"; rm -f "logs/$NAME.pid"' EXIT
    echo '=== $NAME started' \$(date -u +%FT%TZ) 'on stack $STACK_ID'
    echo '=== env:$ENVARGS EXPERIMENT=$NAME'
    env STACK_ID='$STACK_ID'$ENVARGS EXPERIMENT='$NAME' bash scripts/m2prime_nats_matrix.sh
    rc=\$?
    echo '=== matrix finished, exit' \$rc \$(date -u +%FT%TZ)
    if [ \$rc -eq 0 ]; then
      # The measurement is audited before it is interpreted. Three matrices
      # were discarded to defects that were visible in the recorded numbers
      # and that nothing looked at.
      # The two flags this call used to pass, --healthy-anchors and --sla-ms,
      # were left over from the pre-0.8 design where healthy and degraded were
      # partitioned by anchor index and the budget came from the command line.
      # The audit now reads both from each branch's own manifest, so argparse
      # rejected them, the audit exited 2 every single time, and the '||' turned
      # a dead guard into one quiet line above the results. No nightly run has
      # ever actually been audited by this wrapper. The audit now runs, and a
      # failure stops the analysis instead of captioning it.
      echo '=== accounting audit'
      if python3 -u analysis/audit_accounting.py 'data/raw/$STACK_ID/$NAME'; then
        echo '=== accounting audit passed'
      else
        echo '=== AUDIT FAILED. The analysis is NOT run: an unaudited'
        echo '=== measurement is not a measurement. Diagnose, then re-run'
        echo '=== the analysis by hand against data/raw/$STACK_ID/$NAME.'
        touch 'logs/$NAME.audit-failed'
        echo \$rc > 'logs/$NAME.done'
        exit 3
      fi
      echo '=== analysis'
      python3 -u analysis/jobs.py 'data/raw/$STACK_ID/$NAME' \
        --latency-max-epochs 14 --latency-max-ms 3000 --allow-partial-cost \
        --out 'data/raw/$STACK_ID/$NAME/jobs.csv'
      python3 -u analysis/dispersion_breakdown.py 'data/raw/$STACK_ID/$NAME/jobs.csv' \
        --sla-ms \${SLA_MS:-750} --healthy-anchors a01,a02,a03
      echo '=== band sensitivity'
      python3 -u analysis/band_sensitivity.py 'data/raw/$STACK_ID/$NAME/jobs.csv'
    fi
    echo \$rc > 'logs/$NAME.done'
    echo '=== $NAME done' \$(date -u +%FT%TZ)
  } >> '$LOG' 2>&1
" < /dev/null > /dev/null 2>&1 &

sleep 1
cat <<TXT
started: $NAME   stack $STACK_ID
log:     $(pwd)/$LOG

The run no longer depends on this terminal. Close it, let the laptop sleep,
drop the connection -- none of that reaches the run.

  follow:   tail -f $LOG
  check:    bash scripts/run_nightly.sh --status
  result:   sed -n '/=== analysis/,\$p' $LOG
TXT
