#!/usr/bin/env bash
# Part D: the twelve design points at five derived seeds, mode F, one matrix per
# seed index.
#
#   bash scripts/run_campaign_d.sh            # all five arms, in order
#   bash scripts/run_campaign_d.sh 3 4 5      # only these arms
#
# Each arm is an ordinary full-protocol matrix whose scenario set carries the
# derived per-scenario seeds, so nothing in the runner or the orchestrator
# changes for part D. The factors of every arm are the campaign's own twelve
# points, copied, and the anchors, actions, repeats, horizon, period, emission
# spread and netem seed come from part B's manifest through rerun_ablation.sh's
# reader -- read here directly, because these arms are not ablations.
#
# Arms already on disk are skipped, not re-run: experiments are append-only and
# a second attempt at an existing name is a refusal, not a resumption.
set -euo pipefail
cd "$(dirname "$0")/.."

REF="${REF:-bdg-b-s42}"
BASE="${BASE:-configs/scenarios-bdg.json}"
REPEATS_D="${REPEATS_D:-3}"
ARMS=("$@")
[ ${#ARMS[@]} -gt 0 ] || ARMS=(1 2 3 4 5)

STACK="$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)"
[ -n "$STACK" ] || { echo "FAIL: no validated stack; make up-nats && make stack-nats"; exit 2; }
MANIFEST="data/raw/$STACK/$REF/matrix.json"
[ -f "$MANIFEST" ] || { echo "FAIL: $MANIFEST not found"; exit 2; }

FACTORS="$(python3 - "$MANIFEST" <<'PY'
import json, shlex, sys
m = json.load(open(sys.argv[1]))
if m.get("mode", "full") != "full":
    sys.exit(f"FAIL: the reference ran in mode {m['mode']!r}; part D is mode F "
             f"and takes its factors from a full-protocol reference.")
out = {"ANCHOR_LIST": m["anchor_spec"] if "," in str(m["anchor_spec"]) else "",
       "ANCHORS": m["anchors"], "ACTIONS": m["actions"], "HORIZON": m["horizon"],
       "PERIOD": m["period"], "EMIT_SPREAD": m["emit_spread"],
       "NETEM_SEED": m["netem_seed"], "SEED": m["master_seed"]}
for k, v in out.items():
    print(f"{k}={shlex.quote(str(v))}")
PY
)" || { echo "$FACTORS"; exit 2; }
eval "$FACTORS"

echo "part D    reference $REF   stack $STACK"
echo "anchors   ${ANCHOR_LIST:-1..$ANCHORS}    actions $ACTIONS    repeats $REPEATS_D"
echo "arms      ${ARMS[*]}"
echo "netem     $NETEM_SEED (held fixed: only the per-scenario workload seed varies)"
echo

for K in "${ARMS[@]}"; do
  SET="configs/scenarios-bdg-k$K.json"
  NAME="bdg-d-k$K-s42"
  OUT="data/raw/$STACK/$NAME"
  if [ -e "$OUT" ]; then
    echo "== arm k=$K: $NAME exists with $(find "$OUT" -maxdepth 1 -type d -name '*-a*' | wc -l) branches; skipped"
    continue
  fi
  echo "== arm k=$K -> $NAME"
  python3 scripts/gen_campaign_seeds.py --k "$K" --base "$BASE" --out "$SET"
  MODE=full SCENARIOS="$SET" ANCHOR_LIST="$ANCHOR_LIST" ANCHORS="$ANCHORS" \
    REPEATS="$REPEATS_D" ACTIONS="$ACTIONS" HORIZON="$HORIZON" PERIOD="$PERIOD" \
    EMIT_SPREAD="$EMIT_SPREAD" SEED="$SEED" NETEM_SEED="$NETEM_SEED" \
    bash scripts/m2prime_nats_matrix.sh "$NAME"
  echo "== arm k=$K done: $(find "$OUT" -maxdepth 1 -type d -name '*-a*' | wc -l) branches"
done

echo
echo "all requested arms finished. Analyse each with scripts/analyze_matrix.sh"
echo "before any cross-seed reading; the seed-variance rules are frozen separately."
