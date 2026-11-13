#!/usr/bin/env bash
# The randomised-order arm of RANDOMISED_ORDER.md: one mode-F matrix whose
# within-cell execution order is a constrained random draw, so that action
# identity and execution position are independent inside a cell.
#
#   tmux new-session -d -s forder "bash scripts/run_randomised_order_arm.sh"
#
# Everything but the order is copied from the reference matrix's own manifest,
# because the comparison is only worth making if nothing else moved.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG="${LOG:-/tmp/forder.log}"
REF="${REF:-bdg2-f-s42}"
NAME="${NAME:-bdg2-forder-s42}"
SCHED="${SCHED:-configs/order-bdg2-forder.json}"
exec > >(tee -a "$LOG") 2>&1

step() { printf '\n\n===== %s  %s =====\n\n' "$(date -u +%FT%TZ)" "$1"; }

STACK="$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)"
[ -n "$STACK" ] || { echo "FAIL: no validated stack"; exit 2; }
MANIFEST="data/raw/$STACK/$REF/matrix.json"
[ -f "$MANIFEST" ] || { echo "FAIL: $MANIFEST not found"; exit 2; }

step "0/4  the reference arm's factors, and the stack it ran on"
FACTORS="$(python3 - "$MANIFEST" <<'PY'
import json, shlex, sys
m = json.load(open(sys.argv[1]))
if m.get("mode", "full") != "full":
    sys.exit(f"FAIL: the reference ran in mode {m['mode']!r}; this arm is mode F.")
if m.get("within_cell_order", "fixed-action-blocks") != "fixed-action-blocks":
    sys.exit("FAIL: the reference already used a schedule; there is nothing to "
             "compare against.")
out = {"ANCHOR_LIST": m["anchor_spec"] if "," in str(m["anchor_spec"]) else "",
       "ANCHORS": m["anchors"], "ACTIONS": m["actions"], "HORIZON": m["horizon"],
       "PERIOD": m["period"], "EMIT_SPREAD": m["emit_spread"],
       "SCENARIOS": m["scenarios_file"], "SEED": m["master_seed"],
       "NETEM_SEED": m["netem_seed"], "REPEATS": m["repeats"],
       "REF_STACK": m["runtime_stack_id"], "REF_SCEN_HASH": m["scenarios_hash"]}
for k, v in out.items():
    print(f"{k}={shlex.quote(str(v))}")
PY
)" || { echo "$FACTORS"; exit 2; }
eval "$FACTORS"
if [ "$REF_STACK" != "$STACK" ]; then
  echo "STOP: the reference ran on $REF_STACK and the live stack is $STACK."
  echo "      This arm exists to vary ONE thing. Two substrates is not one thing."
  exit 2
fi
echo "reference $REF on $STACK; anchors ${ANCHOR_LIST:-1..$ANCHORS}, "\
     "actions $ACTIONS, repeats $REPEATS"

step "1/4  the order schedule, drawn from the design before the run"
if [ -f "$SCHED" ]; then
  echo "$SCHED exists; reusing it (the draw is a function of the design)"
else
  python3 -I scripts/gen_order_schedule.py --scenarios "$SCENARIOS" \
    --anchors "${ANCHOR_LIST:-}" --actions "$ACTIONS" --repeats "$REPEATS" \
    --out "$SCHED" || { echo "STOP: the schedule could not be drawn"; exit 2; }
fi

step "2/4  $NAME, mode F, constrained-random within-cell order"
if [ -e "data/raw/$STACK/$NAME" ]; then
  echo "$NAME exists with $(find "data/raw/$STACK/$NAME" -maxdepth 1 -type d -name '*-a*' | wc -l) branches; skipped"
else
  MODE=full ORDER_SCHEDULE="$SCHED" SCENARIOS="$SCENARIOS" \
    ANCHOR_LIST="$ANCHOR_LIST" ANCHORS="$ANCHORS" REPEATS="$REPEATS" \
    ACTIONS="$ACTIONS" HORIZON="$HORIZON" PERIOD="$PERIOD" \
    EMIT_SPREAD="$EMIT_SPREAD" SEED="$SEED" NETEM_SEED="$NETEM_SEED" \
    bash scripts/m2prime_nats_matrix.sh "$NAME" \
    || { echo "STOP: the arm did not complete"; exit 1; }
fi

step "3/4  score it, then the order effect WITHIN this arm -- the primary reading"
python3 -I analysis/jobs.py "data/raw/$STACK/$NAME" --latency-max-ms 3000 \
  --latency-max-epochs 14 --allow-partial-cost \
  --out "data/raw/$STACK/$NAME/jobs.csv" | tail -2
python3 -I analysis/order_effects.py "data/raw/$STACK/$NAME/jobs.csv" \
  | tee data/derived/order-effects-forder.txt | tail -30

step "4/4  the secondary reading: the headline share against $REF"
python3 -I analysis/paired_comparator.py "data/raw/$STACK/$NAME/jobs.csv" \
  --by-point | tee data/derived/comparator-forder.txt | sed -n '/resolved at the band/,/band only/p'
echo
echo "reference $REF, for the +/- 8 pp criterion in RANDOMISED_ORDER.md:"
python3 -I analysis/paired_comparator.py "data/raw/$STACK/$REF/jobs.csv" \
  | sed -n '/resolved at the band/,/band only/p'

step "done"
echo "send data/derived/order-effects-forder.txt and the two comparator tails"
