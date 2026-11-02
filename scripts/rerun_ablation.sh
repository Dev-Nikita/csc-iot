#!/usr/bin/env bash
# Run an ablation with every factor copied from a reference matrix's own
# manifest, so that the only difference between the two runs is MODE.
#
#   bash scripts/rerun_ablation.sh <reference-experiment> <mode> <new-name>
#   bash scripts/rerun_ablation.sh bdg-b-s42 reset bdg-reset-v2-s42 --repeats 3
#
# This exists because the first reset run had to be discarded and the second one
# must be comparable to the same reference. Retyping eight environment variables
# is how a substrate difference gets into an ablation, and analysis/mode_comparison.py
# refuses a mismatched pair -- correctly, and after the hours have been spent.
# The factors are therefore read from the reference manifest rather than typed.
#
# REPEATS is the one factor that may differ, because an ablation at three
# repeats against a reference at ten is the declared design; pass --repeats.
set -euo pipefail
cd "$(dirname "$0")/.."

REF="${1:?usage: rerun_ablation.sh <reference-experiment> <mode> <new-name> [--repeats N]}"
MODE="${2:?mode: quiescence | reset}"
NAME="${3:?new experiment name; it must contain the mode}"
shift 3
REPEATS_OVERRIDE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repeats) REPEATS_OVERRIDE="${2:?}"; shift 2 ;;
    *) echo "FAIL: unknown argument $1"; exit 2 ;;
  esac
done

case "$MODE" in quiescence|reset) ;; *) echo "FAIL: mode $MODE"; exit 2 ;; esac
if [ "${NAME#*$MODE}" = "$NAME" ]; then
  echo "FAIL: the name $NAME does not contain \"$MODE\". The runner will refuse"
  echo "      it too; an ablated matrix under an innocent name is the one"
  echo "      mistake here that cannot be corrected afterwards."
  exit 2
fi

STACK="$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)"
[ -n "$STACK" ] || { echo "FAIL: no validated stack; make up-nats && make stack-nats"; exit 2; }
MANIFEST="data/raw/$STACK/$REF/matrix.json"
[ -f "$MANIFEST" ] || { echo "FAIL: $MANIFEST not found"; exit 2; }

# `eval "$(python3 ...)"` discards the exit status of the command substitution,
# so a refusal inside the reader printed FAIL and the script carried on to an
# unbound-variable error three lines later, naming the wrong cause. The factors
# are captured first, the status is checked, and only then evaluated.
FACTORS="$(python3 - "$MANIFEST" <<'PY'
import json, shlex, sys
m = json.load(open(sys.argv[1]))
if m.get("mode", "full") != "full":
    sys.exit(f"FAIL: the reference {m['experiment']} ran in mode "
             f"{m['mode']!r}; an ablation is not a reference for an ablation.")
# Only one purpose is disqualifying: a budget-calibration matrix ran with a
# placeholder latency budget, so its objective is not a measurement. Every other
# purpose string is a label the campaign chose for its own set -- the B+D+G
# scenarios declare "campaign-bdg" -- and refusing those refused the only
# reference this script exists to copy.
if m.get("purpose", "reportable") == "budget-calibration":
    sys.exit("FAIL: the reference ran for budget calibration, with a "
             "placeholder budget. It is not a reference for anything.")
out = {
    "ANCHOR_LIST": m["anchor_spec"] if "," in str(m["anchor_spec"]) else "",
    "ANCHORS": m["anchors"],
    "REPEATS": m["repeats"],
    "ACTIONS": m["actions"],
    "HORIZON": m["horizon"],
    "PERIOD": m["period"],
    "EMIT_SPREAD": m["emit_spread"],
    "SCENARIOS": m["scenarios_file"],
    "SEED": m["master_seed"],
    "NETEM_SEED": m["netem_seed"],
    "REF_SCENARIOS_HASH": m["scenarios_hash"],
}
for k, v in out.items():
    print(f"{k}={shlex.quote(str(v))}")
PY
)" || { echo "$FACTORS"; exit 2; }
eval "$FACTORS"

[ -f "$SCENARIOS" ] || { echo "FAIL: $SCENARIOS, the reference's scenario set, is gone"; exit 2; }
HAVE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["scenarios_hash"])' "$SCENARIOS")"
if [ "$HAVE" != "$REF_SCENARIOS_HASH" ]; then
  echo "FAIL: $SCENARIOS now hashes to $HAVE; the reference ran $REF_SCENARIOS_HASH."
  echo "      The scenario set has changed since the reference. Regenerate the"
  echo "      reference's set or compare against a matrix that used this one."
  exit 2
fi
[ -n "$REPEATS_OVERRIDE" ] && REPEATS="$REPEATS_OVERRIDE"

echo "reference   $REF   stack $STACK"
echo "ablation    $NAME   mode $MODE"
echo "anchors     ${ANCHOR_LIST:-1..$ANCHORS}"
echo "actions     $ACTIONS    repeats $REPEATS    horizon $HORIZON"
echo "scenarios   $SCENARIOS  ($REF_SCENARIOS_HASH)"
echo "seeds       master $SEED  netem $NETEM_SEED"
echo

export MODE SCENARIOS ANCHOR_LIST ANCHORS REPEATS ACTIONS HORIZON PERIOD \
       EMIT_SPREAD SEED NETEM_SEED
exec bash scripts/m2prime_nats_matrix.sh "$NAME"
