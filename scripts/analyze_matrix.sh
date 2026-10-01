#!/usr/bin/env bash
# The whole analysis of one matrix, in the order the protocol requires, into one
# report file.
#
#   bash scripts/analyze_matrix.sh b5-matrix-v2
#
# The order is not cosmetic. The measurement is audited before it is interpreted;
# resolvability is established before any model result is read; the leakage tests
# gate the model results; and the preregistered structural sign test is run before
# the layers are compared. A gate that fails stops the sections that depend on it
# and says so, rather than letting a number through with a caption.
set -uo pipefail
cd "$(dirname "$0")/.."

NAME="${1:?usage: analyze_matrix.sh <experiment-name>}"
LIVE="$(python3 check_reportable_stack.py --print-stack-id 2>/dev/null)"
[ -n "$LIVE" ] || { echo "FAIL: no validated stack"; exit 2; }
R="data/raw/$LIVE/$NAME"
[ -d "$R" ] || { echo "FAIL: $R not found"; exit 2; }
OUT="data/derived/$NAME-report.txt"
mkdir -p data/derived

section() { printf '\n\n========== %s ==========\n\n' "$1"; }

{
  echo "ANALYSIS REPORT  $NAME"
  echo "stack      $LIVE"
  echo "generated  $(date -u +%FT%TZ)"
  echo "revision   $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "branches   $(find "$R" -maxdepth 1 -type d -name 's*-a*' | wc -l)"

  section "1. accounting audit -- the measurement before the interpretation"
  if python3 -u analysis/audit_accounting.py "$R"; then
    echo "AUDIT PASSED"
  else
    echo
    echo "AUDIT FAILED. Nothing below this line is reportable. The remaining"
    echo "sections are not run: an unaudited measurement is not a measurement."
    exit 3
  fi

  section "2. objective"
  python3 -u analysis/jobs.py "$R" --latency-max-ms 3000 --latency-max-epochs 14 \
    --allow-partial-cost --out "$R/jobs.csv" | tail -40

  section "3. replay resolution -- the four bands"
  python3 -u analysis/band_sensitivity.py "$R/jobs.csv" | tail -45

  section "4. leakage -- these gate every model result below"
  python3 -u analysis/leakage_tests.py "$R" "$R/jobs.csv" | tail -30
  LEAK=$?

  section "5. spanning-regime holdout"
  python3 -u analysis/regime_holdout.py "$R" "$R/jobs.csv" --regime spanning | tail -14

  section "6. structural model -- the preregistered sign test"
  python3 -u analysis/structural.py "$R" "$R/jobs.csv" --out "$R/structural.csv" 2>/dev/null | tail -8
  echo
  python3 -u analysis/structural_signtest.py "$R/jobs.csv" "$R/structural.csv"
  echo "(sign test exit $?: 0 passes, 1 a flipped sign, 2 nothing resolvable)"

  section "7. splits and the ensemble"
  python3 -u analysis/predictor.py "$R" "$R/jobs.csv"

  section "8. conformal risk control"
  python3 -u analysis/crc.py "$R" "$R/jobs.csv" --delta 0.10 | tail -25

  section "9. decision methods on common anchors"
  python3 -u analysis/evaluate.py "$R" "$R/jobs.csv" --delta 0.10 \
    --out "$R/decisions.csv"

  if [ "${LEAK:-0}" -ne 0 ]; then
    section "WARNING"
    echo "A leakage test did not pass. Sections 6-9 are printed but MUST NOT be"
    echo "reported: a model result over a failed leakage test is not evidence."
  fi

  section "done"
  echo "wrote $R/jobs.csv, $R/structural.csv, $R/decisions.csv"
} 2>&1 | tee "$OUT"

echo
echo "report: $OUT"
echo "send that file; it is self-contained."
