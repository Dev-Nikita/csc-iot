#!/usr/bin/env bash
# The mode study and part D, entirely on whatever stack is live now, because the
# campaign's recorded stack id 99982ee46a1999be is no longer reproducible and
# the field that moved cannot be named (CAMPAIGN_BDG.md amendment 11).
#
#   tmux new-session -d -s campaign2 "bash scripts/run_campaign_on_current_stack.sh"
#
# Why this shape. The mode comparison reads F at THREE repeats by a rule frozen
# before any of these numbers existed, and the matched null calibration needs
# three more. So the reference arm here is F at SIX repeats, not ten: 1296
# branches instead of 2160, and nothing the comparison uses is lost. The old
# ten-repeat matrix keeps its id and stays the paper's main-results matrix; it
# is not compared with anything run here.
#
#   bdg2-f-s42           mode F, 6 repeats   1296 branches  ~7.3 h
#   bdg2-quiescence-s42  mode Q, 3 repeats    648 branches  ~3.7 h
#   bdg2-reset-s42       mode R, 3 repeats    648 branches  ~3.7 h
#   bdg2-d-k1..5-s42     part D, 3 repeats   3240 branches  ~18.4 h
#
# The "bdg2" prefix is the substrate, not a version: a name must say which stack
# its branches belong to without opening a manifest.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG="${LOG:-/tmp/campaign2.log}"
OLD_REF="${OLD_REF:-bdg-b-s42}"
OLD_STACK="${OLD_STACK:-99982ee46a1999be}"
F_REPEATS="${F_REPEATS:-6}"
exec > >(tee -a "$LOG") 2>&1

step() { printf '\n\n===== %s  %s =====\n\n' "$(date -u +%FT%TZ)" "$1"; }

# ---- 0. is the identity reproducible at all? -----------------------------
# The whole reason this script exists is a stack id that could not be
# reproduced. Spending thirty-three hours on a substrate whose identity is not
# stable across two consecutive stamps would repeat the mistake exactly.
step "0/6  is the live stack id reproducible across two stamps?"
if ! docker compose -f docker-compose.nats.yml ps --status running \
     --format '{{.Service}}' | grep -q gateway00; then
  docker compose -f docker-compose.nats.yml up -d --no-build || {
    echo "FAIL: could not bring the stack up without rebuilding"; exit 2; }
  sleep 30
fi
A="$(bash scripts/verify_stack.sh 2>/dev/null | awk '/^live stack/{print $3}')"
sleep 20
B="$(bash scripts/verify_stack.sh 2>/dev/null | awk '/^live stack/{print $3}')"
if [ -z "$A" ] || [ "$A" != "$B" ]; then
  echo "STOP: two consecutive stamps gave '$A' and '$B'."
  echo "      The identity is not reproducible, so no measurement taken here"
  echo "      could be attributed to a substrate. Fix that before running."
  exit 2
fi
if [ "$A" = "$OLD_STACK" ]; then
  echo "NOTE: the live stack is $OLD_STACK after all. The old arms are usable"
  echo "      and this script is the wrong one; use run_remaining_campaign.sh."
  exit 2
fi
STACK="$A"
echo "live stack $STACK, reproducible across two stamps"
make stack-nats   # promote it, keeping the previous stamp in history/

# The runner refuses a bin/ older than the Go sources, and it is right to: a
# stale orchestrator once produced 27 clean-looking branches whose outcomes were
# missing the observed block entirely. This week's commits touched internal/, so
# the binaries are rebuilt here rather than left for the chain to trip over
# eleven hours in.
#
# `make build` compiles host binaries only -- the container images are built by
# up-nats from go.Dockerfile -- so it cannot move the stack id. Verified rather
# than asserted: the stamp is taken again afterwards.
step "0b/6  rebuilding bin/ and confirming the identity did not move"
make build TAGS=nats || { echo "STOP: the build failed"; exit 2; }
C="$(bash scripts/verify_stack.sh 2>/dev/null | awk '/^live stack/{print $3}')"
if [ "$C" != "$STACK" ]; then
  echo "STOP: the stack id moved from $STACK to $C across a host-side build."
  echo "      That should be impossible -- the id hashes container images, not"
  echo "      bin/ -- so something else is moving and must be found first."
  exit 2
fi
echo "stack $STACK unchanged after the build"

# ---- the reference arm's factors, from the old manifest -------------------
FACTORS="$(python3 - "data/raw/$OLD_STACK/$OLD_REF/matrix.json" <<'PY'
import json, shlex, sys
m = json.load(open(sys.argv[1]))
out = {"ANCHOR_LIST": m["anchor_spec"] if "," in str(m["anchor_spec"]) else "",
       "ANCHORS": m["anchors"], "ACTIONS": m["actions"], "HORIZON": m["horizon"],
       "PERIOD": m["period"], "EMIT_SPREAD": m["emit_spread"],
       "SCENARIOS": m["scenarios_file"], "SEED": m["master_seed"],
       "NETEM_SEED": m["netem_seed"]}
for k, v in out.items():
    print(f"{k}={shlex.quote(str(v))}")
PY
)" || { echo "$FACTORS"; exit 2; }
eval "$FACTORS"
echo "factors copied from $OLD_REF: anchors ${ANCHOR_LIST:-1..$ANCHORS}, actions $ACTIONS"

run_matrix() {  # name, repeats, extra env assignments passed as MODE=...
  local name="$1" repeats="$2" mode="$3"
  if [ -e "data/raw/$STACK/$name" ]; then
    echo "$name exists with $(find "data/raw/$STACK/$name" -maxdepth 1 -type d -name '*-a*' | wc -l) branches; skipped"
    return 0
  fi
  MODE="$mode" SCENARIOS="$SCENARIOS" ANCHOR_LIST="$ANCHOR_LIST" ANCHORS="$ANCHORS" \
    REPEATS="$repeats" ACTIONS="$ACTIONS" HORIZON="$HORIZON" PERIOD="$PERIOD" \
    EMIT_SPREAD="$EMIT_SPREAD" SEED="$SEED" NETEM_SEED="$NETEM_SEED" \
    bash scripts/m2prime_nats_matrix.sh "$name"
}

step "1/6  mode F at $F_REPEATS repeats as bdg2-f-s42"
run_matrix bdg2-f-s42 "$F_REPEATS" full || { echo "STOP: F did not complete"; exit 1; }

step "2/6  mode Q as bdg2-quiescence-s42"
run_matrix bdg2-quiescence-s42 3 quiescence || { echo "STOP: Q did not complete"; exit 1; }

step "3/6  mode R as bdg2-reset-s42"
run_matrix bdg2-reset-s42 3 reset || { echo "STOP: R did not complete"; exit 1; }

step "4/6  validating all three -- this refuses a void ablation"
ok=1
for n in bdg2-f-s42 bdg2-quiescence-s42 bdg2-reset-s42; do
  python3 analysis/m2prime_report.py "data/raw/$STACK/$n" | tail -5 || ok=0
done
[ "$ok" = 1 ] || { echo "STOP: a matrix did not validate; part D is not started."; exit 1; }

step "5/6  analysis and the three-mode comparison"
for n in bdg2-f-s42 bdg2-quiescence-s42 bdg2-reset-s42; do
  bash scripts/analyze_matrix.sh "$n" >/dev/null
  [ -f "data/raw/$STACK/$n/jobs.csv" ] || echo "NOTE: no jobs.csv for $n"
done
python3 -I analysis/mode_comparison.py "data/raw/$STACK" \
  --full bdg2-f-s42 --ablated bdg2-quiescence-s42 --ablated bdg2-reset-s42 \
  > data/derived/mode-comparison-bdg2.txt 2>&1
echo "exit $?; wrote data/derived/mode-comparison-bdg2.txt"
tail -70 data/derived/mode-comparison-bdg2.txt

step "6/6  part D, five arms at the derived seeds"
REF=bdg2-f-s42 bash scripts/run_campaign_d.sh

step "done"
echo "send data/derived/mode-comparison-bdg2.txt and the tail of $LOG"
