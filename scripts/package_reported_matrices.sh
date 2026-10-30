#!/usr/bin/env bash
# Find the three matrix roots the manuscript reports, package their derived data
# and write the tarball for the archive. Run this ON THE ANALYSIS HOST.
#
#   bash scripts/package_reported_matrices.sh
#
# This exists because the alternative was a command with <stack-id> placeholders
# in it, which is a command that gets pasted into a shell verbatim. The stack-id
# directory names are content-derived hashes; nobody should be typing them, and a
# runbook should not ask anyone to.
#
# It refuses rather than guesses: a matrix name that appears under no stack id,
# or under more than one, stops the run with the candidates printed. Two copies
# of a reported matrix under different stack ids means two different substrates
# produced it, and picking one silently is how a figure gets attributed to
# hardware that did not run it.
set -euo pipefail
cd "$(dirname "$0")/.."

MATRICES=(b5-matrix-v2 d45-matrix-v1 d6-pilot-v2)
roots=()

for name in "${MATRICES[@]}"; do
  mapfile -t found < <(find data/raw -maxdepth 2 -type d -name "$name" \
                         -not -path '*_quarantine*' -not -path '*_legacy*' | sort)
  case ${#found[@]} in
    0) echo "REFUSED: no directory named $name under data/raw" >&2
       echo "         stack ids present: $(ls data/raw | tr '\n' ' ')" >&2
       exit 1 ;;
    1) ;;
    *) echo "REFUSED: $name exists under ${#found[@]} stack ids:" >&2
       printf '         %s\n' "${found[@]}" >&2
       echo "         Pick one deliberately and call make_data_package.sh with it." >&2
       exit 1 ;;
  esac
  root="${found[0]}"
  for f in matrix.json jobs.csv; do
    [ -f "$root/$f" ] || { echo "REFUSED: $root/$f is missing" >&2; exit 1; }
  done
  branches=$(find "$root" -maxdepth 1 -type d ! -path "$root" | wc -l | tr -d ' ')
  printf 'found  %-16s %s  (%s branch directories)\n' "$name" "$root" "$branches"
  roots+=("$root")
done

echo
primary="${roots[0]}"
python3 analysis/export_crc_ledger.py "$primary" "$primary/jobs.csv" \
  --out "$primary/crc_calibration.csv"
python3 analysis/recompute_crc_independent.py "$primary/crc_calibration.csv" \
  --curve "$primary/crc_curve_independent.csv"

bash scripts/make_data_package.sh "${roots[@]}"

tar -czf dist/csc-iot-data.tar.gz -C dist zenodo-data
echo
echo "tarball:"
ls -l dist/csc-iot-data.tar.gz
echo
echo "branch total across the three (must be 8118):"
cat dist/zenodo-data/*/branch_index.txt | wc -l
echo
# The packaged RESULTS.md must be the corrected one. Checking that 0.1174 is
# absent was wrong: the file documents the correction in a sentence that names
# both figures, and a record that explains its own history is the point of having
# one. What must not appear is 0.1174 WITHOUT 0.1011 beside it -- that is a stale
# reading rather than a documented one.
r=dist/zenodo-data/RESULTS.md
[ -f "$r" ] || { echo "REFUSED: RESULTS.md is not in the package" >&2; exit 1; }
grep -q '0\.1011' "$r" || { echo "REFUSED: $r does not carry the corrected time-only control (0.1011)" >&2; exit 1; }
stale=$(grep -n '0\.1174' "$r" | grep -v '0\.1011' || true)
if [ -n "$stale" ]; then
  echo "REFUSED: $r states the superseded 0.1174 outside the correction note:" >&2
  echo "$stale" >&2
  exit 1
fi
echo "RESULTS.md: corrected (0.1011 present; 0.1174 only in the correction note)"
echo
# make_data_package.sh already fails on a placeholder outside the three documents
# and prints the documented mentions inside them. This scan is the second pair of
# eyes on the same question, with the same exclusions, so a clean build prints
# nothing and anything printed here is a real finding.
echo "placeholder scan (must print nothing):"
grep -rn "No Experiment Has Been Run\|Placeholder" dist/zenodo-data \
  --exclude=RESULTS.md --exclude=EXPERIMENT_PROTOCOL.md --exclude=CRC_AUDIT.md || true
