#!/usr/bin/env bash
# Quarantine a run that must not be reported, safely.
#
# This exists because the job was being done by hand with a loop of `mv`, and
# that loop once moved a LIVE run's log and output directory out from under it:
# the status listing showed "_void-budget-cal-L60-... ok s02-a02-NO_OP-r08",
# a branch still in progress under a name that says the run is finished. A void
# is a records operation and it needs the same care as a measurement.
#
#   bash scripts/void_run.sh <run-name> "<reason>"
#
# It refuses while the run is alive, moves both the data directory and the log
# into quarantine, and appends a line to data/raw/_quarantine/LEDGER.md so the
# exclusion is documented where the data is rather than only in a commit message.
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?usage: void_run.sh <run-name> \"<reason>\"}"
REASON="${2:?a reason is required; an undocumented exclusion is not an exclusion}"

if [ -f "logs/$NAME.pid" ] && kill -0 "$(cat "logs/$NAME.pid")" 2>/dev/null; then
  echo "FAIL: '$NAME' is still running (pid $(cat "logs/$NAME.pid"))."
  echo "      Voiding a live run corrupts it mid-branch and leaves a log that"
  echo "      claims to be finished. Stop it first: kill \$(cat logs/$NAME.pid)"
  exit 2
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
QUAR="data/raw/_quarantine"
mkdir -p "$QUAR" logs/_void

moved=0
for stack in data/raw/*/; do
  d="$stack$NAME"
  [ -d "$d" ] || continue
  dest="$QUAR/${NAME}-$(basename "$stack")-$STAMP"
  mv "$d" "$dest" && { echo "moved $d -> $dest"; moved=$((moved + 1)); }
done
if [ -f "logs/$NAME.log" ]; then
  mv "logs/$NAME.log" "logs/_void/${NAME}-$STAMP.log"
  echo "moved logs/$NAME.log -> logs/_void/${NAME}-$STAMP.log"
fi
rm -f "logs/$NAME.pid" "logs/$NAME.done"

{
  printf '%s | %s | %s | %d data director%s\n' \
    "$STAMP" "$NAME" "$REASON" "$moved" "$([ "$moved" -eq 1 ] && echo y || echo ies)"
} >> "$QUAR/LEDGER.md"

echo
echo "voided '$NAME': $REASON"
echo "recorded in $QUAR/LEDGER.md"
[ "$moved" -eq 0 ] && echo "note: no data directory found; only the log and markers were cleared"
exit 0
