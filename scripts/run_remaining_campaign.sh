#!/usr/bin/env bash
# The rest of the B+D+G campaign, in one sequential chain, so that nothing
# overlaps and nothing needs watching.
#
#   tmux new-session -d -s campaign "bash scripts/run_remaining_campaign.sh"
#   tail -f /tmp/campaign.log        # or whatever LOG says
#
# Order, and why it is an order rather than a list:
#
#   1. mode R, as a fresh matrix. The runner's lock makes a second runner
#      impossible, which is what wrecked the previous attempt.
#   2. R's own validation, which REFUSES a reset matrix whose branches all tore
#      the topology down. If R is void again, the chain stops here: comparing a
#      void ablation is worse than not comparing.
#   3. R's analysis pipeline, which is what produces jobs.csv.
#   4. the three-mode comparison, under the rules frozen in MODE_COMPARISON.md.
#   5. part D, five arms at the derived seeds. Independent of 2-4, so a failure
#      in the comparison does not cost the eighteen hours.
#
# Everything is logged to one file and every step announces itself, because the
# point of the chain is that nobody is sitting in front of it.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG="${LOG:-/tmp/campaign.log}"
R_NAME="${R_NAME:-bdg-reset-v3-s42}"
REF="${REF:-bdg-b-s42}"
Q_NAME="${Q_NAME:-bdg-quiescence-s42}"

exec > >(tee -a "$LOG") 2>&1

STACK="$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)"
[ -n "$STACK" ] || { echo "FAIL: no validated stack"; exit 2; }

step() { printf '\n\n===== %s  %s =====\n\n' "$(date -u +%FT%TZ)" "$1"; }

step "1/5  mode R as $R_NAME"
if ! bash scripts/rerun_ablation.sh "$REF" reset "$R_NAME" --repeats 3; then
  echo "STOP: mode R did not complete. Nothing downstream is run."
  exit 1
fi

step "2/5  validating $R_NAME -- this refuses a void ablation"
if ! python3 analysis/m2prime_report.py "data/raw/$STACK/$R_NAME"; then
  echo "STOP: $R_NAME did not validate. If the refusal says VOID ABLATION, the"
  echo "      reset mode ablated nothing again and the runner is still wrong."
  echo "      Part D is NOT started: fix the ablation first, it is the cheaper"
  echo "      of the two and the comparison depends on it."
  exit 1
fi

step "3/5  analysis pipeline for $R_NAME"
bash scripts/analyze_matrix.sh "$R_NAME"
# analyze_matrix.sh ends in a pipeline through tee, so its exit status is tee's
# and cannot gate anything. The artefact it exists to produce is the gate.
if [ ! -f "data/raw/$STACK/$R_NAME/jobs.csv" ]; then
  echo "NOTE: no jobs.csv for $R_NAME; the comparison will refuse it and say so."
fi

step "4/5  three-mode comparison"
python3 -I analysis/mode_comparison.py "data/raw/$STACK" \
  --full "$REF" --ablated "$Q_NAME" --ablated "$R_NAME" \
  > data/derived/mode-comparison.txt 2>&1
echo "exit $?; wrote data/derived/mode-comparison.txt"
tail -60 data/derived/mode-comparison.txt

step "5/5  part D, five arms at the derived seeds"
bash scripts/run_campaign_d.sh

step "done"
echo "send data/derived/mode-comparison.txt and the tail of $LOG"
