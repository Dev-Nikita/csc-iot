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
bash scripts/make_data_package.sh "${roots[@]}"

tar -czf dist/csc-iot-data.tar.gz -C dist zenodo-data
echo
echo "tarball:"
ls -l dist/csc-iot-data.tar.gz
echo
echo "branch total across the three (must be 8118):"
cat dist/zenodo-data/*/branch_index.txt | wc -l
echo
echo "RESULTS.md in the package must be the corrected one."
echo "0.1011 occurrences (expect at least 1):"
grep -c '0\.1011' dist/zenodo-data/RESULTS.md 2>/dev/null || echo "  RESULTS.md not in the package -- check make_data_package.sh"
echo "0.1174 occurrences (expect 0):"
grep -c '0\.1174' dist/zenodo-data/RESULTS.md 2>/dev/null || true
echo
echo "placeholder scan (must print nothing):"
grep -rl "No Experiment Has Been Run" dist/zenodo-data || true
