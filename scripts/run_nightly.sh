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
    if [ -f "logs/$name.done" ]; then
      st="exit $(cat "logs/$name.done")"
    elif pgrep -f "EXPERIMENT=$name " >/dev/null 2>&1; then
      st="running"
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

STACK_ID="${STACK_ID:-$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)}"
[ -n "$STACK_ID" ] || { echo "FAIL: no reportable stack. Run make stack-nats first."; exit 2; }

# setsid detaches from the terminal's session entirely: closing the SSH
# connection sends no signal the run can die from, with or without tmux.
setsid bash -c "
  { echo '=== $NAME started' \$(date -u +%FT%TZ) 'on stack $STACK_ID'
    env STACK_ID='$STACK_ID' $* EXPERIMENT='$NAME' bash scripts/m2prime_nats_matrix.sh
    rc=\$?
    echo '=== matrix finished, exit' \$rc \$(date -u +%FT%TZ)
    if [ \$rc -eq 0 ]; then
      echo '=== analysis'
      python3 -u analysis/jobs.py 'data/raw/$STACK_ID/$NAME' \
        --latency-max-epochs 14 --latency-max-ms 3000 --allow-partial-cost \
        --out 'data/raw/$STACK_ID/$NAME/jobs.csv'
      python3 -u analysis/dispersion_breakdown.py 'data/raw/$STACK_ID/$NAME/jobs.csv' \
        --sla-ms \${SLA_MS:-500} --healthy-anchors a01,a02,a03
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
