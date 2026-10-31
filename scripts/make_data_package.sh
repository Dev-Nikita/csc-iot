#!/usr/bin/env bash
# Package the derived data for the matrices the paper reports, for the archive.
#
# Run this ON THE ANALYSIS HOST, where the branch data lives. It packages what a
# reader needs to recompute the reported tables and nothing that is merely large:
# the per-branch objective table, the run manifest, a branch index, the generated
# tables and checksums for all of it. Raw execution logs stay where they are.
#
#   bash scripts/make_data_package.sh <matrix-root> [<matrix-root> ...]
#
# A matrix root is a directory holding matrix.json and jobs.csv, e.g.
#   data/raw/161b4e3893c01695/b5-matrix-v2
#
# It refuses a root that is missing either file rather than packaging a partial
# matrix, because a partial archive is worse than a named absence.
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -ge 1 ] || { echo "usage: $0 <matrix-root> [...]" >&2; exit 2; }

out="dist/zenodo-data"
rm -rf "$out"; mkdir -p "$out"

for root in "$@"; do
  name=$(basename "$root")
  for f in matrix.json jobs.csv; do
    [ -f "$root/$f" ] || { echo "REFUSED: $root/$f is missing" >&2; exit 1; }
  done
  mkdir -p "$out/$name"
  cp "$root/matrix.json" "$root/jobs.csv" "$out/$name/"
  # matrix.json names scenarios_file and scenarios_hash but the file itself was
  # never packaged, so a reader could see WHICH design points were declared only
  # by their name. Without it the per-scenario seeds, onsets, severities and
  # loads are unrecoverable from the archive, and the design cannot be re-run.
  # The runner copies it beside the branches; it travels with them from now on,
  # and its hash is checked against what the manifest claims.
  if [ -f "$root/scenarios.json" ]; then
    cp "$root/scenarios.json" "$out/$name/"
    python3 - "$root/matrix.json" "$root/scenarios.json" <<'HASHCHK' || exit 1
import json, sys
man = json.load(open(sys.argv[1]))
sc = json.load(open(sys.argv[2]))
want, got = man.get("scenarios_hash"), sc.get("scenarios_hash")
if want and got and want != got:
    sys.exit(f"REFUSED: {sys.argv[2]} hashes {got}, manifest claims {want}")
HASHCHK
  else
    echo "REFUSED: $root/scenarios.json is missing; the design points it declares" >&2
    echo "         cannot be recovered from the package without it" >&2
    exit 1
  fi
  case "$name" in
    b5-matrix-v2)
      required=(structural.csv decisions.csv crc_calibration.csv crc_curve_independent.csv) ;;
    d45-matrix-v1)
      required=(structural.csv) ;;
    *) required=() ;;
  esac
  for f in "${required[@]}"; do
    [ -f "$root/$f" ] || {
      echo "REFUSED: $root/$f is required for independent reconstruction" >&2
      exit 1
    }
    cp "$root/$f" "$out/$name/"
  done
  # one row per branch: which branch, which action, which scenario. The objective
  # components are already in jobs.csv; this is the index that ties them to the
  # directory names the manifests use.
  ( cd "$root" && for d in [as]*-*; do [ -d "$d" ] || continue; echo "$d"; done ) \
    | sort > "$out/$name/branch_index.txt"
  n=$(wc -l < "$out/$name/branch_index.txt" | tr -d ' ')
  echo "packaged $name: $n branches"
done

# Only the tables the manuscript actually uses. A blanket copy put two
# placeholders captioned "No Experiment Has Been Run" into the archive of a paper
# that reports 8118 branches, which is worse than shipping nothing.
mkdir -p "$out/generated_tables"
for t in table_bands_merged table_bands_single table_bands_factored \
         table_prediction table_spanning table_runs; do
  [ -f "paper/generated_tables/$t.tex" ] && \
    cp "paper/generated_tables/$t.tex" "$out/generated_tables/"
done
# RESULTS.md is not optional decoration: the manuscript's transcribed tables are
# checked against it, and the supplement tells a reader the archive is what lets
# them recompute the reported figures. `|| true` here once meant a package could
# be built without it and nothing would say so.
for f in RESULTS.md EXPERIMENT_PROTOCOL.md CRC_AUDIT.md; do
  [ -f "$f" ] || { echo "REFUSED: $f is missing from the working tree" >&2; exit 1; }
  cp "$f" "$out/"
done

mkdir -p "$out/rcaeval"
for f in secondstand/README.md secondstand/batch.py \
         secondstand/results.jsonl secondstand/analyse2.py \
         secondstand/analysis_output.txt \
         secondstand/replication_sensitivity.py \
         secondstand/replication_sensitivity_output.txt \
         secondstand/verify_independent.py \
         secondstand/verify_independent_output.txt; do
  [ -f "$f" ] || { echo "REFUSED: $f is missing" >&2; exit 1; }
  cp "$f" "$out/rcaeval/"
done
[ -f secondstand/results.jsonl.provenance.json ] || {
  echo "REFUSED: RCAEval package-version provenance is missing" >&2
  echo "         rerun secondstand/batch.py at the pinned dataset revision" >&2
  exit 1
}
cp secondstand/results.jsonl.provenance.json "$out/rcaeval/"
# The archive must carry every analysis the manuscript now cites, or the next
# reviewer finds the same gap again: a paper that reports a distribution from
# data a reader cannot recompute is in the position version 0.3 was in.
for f in analysis/recompute_crc_independent.py \
         analysis/value_of_protocol.py \
         analysis/value_of_protocol_output.txt \
         analysis/independent_units.py \
         analysis/crc_replay_sensitivity.py \
         analysis/units_and_sensitivity_output.txt \
         VALUE_OF_PROTOCOL.md; do
  [ -f "$f" ] || { echo "REFUSED: $f is missing from the working tree" >&2; exit 1; }
  cp "$f" "$out/"
done

# The placeholder guard runs HERE, after every file is in place. It used to run
# immediately after the generated tables were copied, which was before RESULTS.md,
# EXPERIMENT_PROTOCOL.md, CRC_AUDIT.md and the whole rcaeval/ directory existed in
# the package: it could not have seen a placeholder in any of them. A guard that
# cannot see most of what it guards is worse than no guard, because it reports ok.
#
# The three top-level documents are excluded from the hard failure and reported
# instead: EXPERIMENT_PROTOCOL.md legitimately quotes both phrases in the sentence
# that specifies this very check, the same way RESULTS.md legitimately states the
# superseded 0.1174 inside its correction note. A document that describes an audit
# has to be allowed to name what the audit looks for.
docs="RESULTS.md EXPERIMENT_PROTOCOL.md CRC_AUDIT.md"
excl=""
for d in $docs; do excl="$excl --exclude=$d"; done
if grep -rl 'Placeholder\|No Experiment Has Been Run' "$out" $excl >/dev/null 2>&1; then
  echo "REFUSED: a placeholder reached the data package" >&2
  grep -rn 'Placeholder\|No Experiment Has Been Run' "$out" $excl >&2
  exit 1
fi
for d in $docs; do
  [ -f "$out/$d" ] || continue
  hits=$(grep -n 'Placeholder\|No Experiment Has Been Run' "$out/$d" || true)
  [ -n "$hits" ] && { echo "note: $d names the placeholder phrases, read these lines:"; echo "$hits" | sed 's/^/      /'; }
done

# The frozen outputs are REGENERATED HERE, by the packaged scripts reading the
# packaged data, with -I so the interpreter cannot import anything from outside.
# Copying outputs that were produced elsewhere would mean the tables in the paper
# are traceable to a working tree rather than to the archive, which is the
# circularity an external review asked us to close. If the packaged code and the
# packaged data disagree with what was copied in, the build says so and stops.
for g in value_of_protocol independent_units; do
  [ -f "$out/$g.py" ] || { echo "REFUSED: $out/$g.py is missing" >&2; exit 1; }
done
(
  cd "$out"
  {
    echo "# Generated inside the data package by value_of_protocol.py,"
    echo "# reading only the matrices in this package. Rules frozen in"
    echo "# VALUE_OF_PROTOCOL.md; amendment 1 adds the four-criterion columns."
    python3 -I value_of_protocol.py . d45-matrix-v1 b5-matrix-v2
  } > value_of_protocol_output.txt 2>&1
  {
    echo "# Generated inside the data package."
    echo "#"
    echo "# independent_units.py"
    python3 -I independent_units.py . b5-matrix-v2 d45-matrix-v1 d6-pilot-v2
    echo
    echo "# crc_replay_sensitivity.py, 2000 draws"
    python3 -I crc_replay_sensitivity.py b5-matrix-v2/crc_calibration.csv 2000
  } > units_and_sensitivity_output.txt 2>&1
)
# The working tree's copies must agree with what the package just produced, on
# everything but the provenance header, or the manuscript is transcribed against
# numbers the archive does not yield.
for g in value_of_protocol_output.txt units_and_sensitivity_output.txt; do
  if ! diff -q <(grep -v '^#' "analysis/$g") <(grep -v '^#' "$out/$g") >/dev/null; then
    echo "REFUSED: analysis/$g disagrees with what the package produces" >&2
    diff <(grep -v '^#' "analysis/$g") <(grep -v '^#' "$out/$g") | head -20 >&2
    exit 1
  fi
done
echo "frozen outputs regenerated inside the package and matched against analysis/"

( cd "$out" && find . -type f ! -name SHA256SUMS -print0 | sort -z \
    | xargs -0 shasum -a 256 > SHA256SUMS )

cat > "$out/README.md" <<'INNER'
# Derived data for the reported matrices

One directory per matrix the manuscript reports. Each contains:

- `matrix.json`   -- the manifest the runner wrote when the matrix started
- `jobs.csv`      -- one row per branch: scenario, anchor, action, the objective
                     and its measured components
- `branch_index.txt` -- the branch directory names, so a row can be tied to the
                     run that produced it

The primary matrix also contains `crc_calibration.csv`, the frozen calibration
ledger, and `crc_curve_independent.csv`. Run
`python3 recompute_crc_independent.py b5-matrix-v2/crc_calibration.csv` to rebuild
the run-level loss curve and threshold without importing the project CRC module.
`structural.csv` and `decisions.csv` preserve the prediction and method-summary
outputs used by the paper.

`generated_tables/` holds the tables as the analysis emitted them, and
`SHA256SUMS` covers every file here.

`rcaeval/` contains the 375 per-case benchmark results used in the second study,
the pinned scorer, both analysis scripts, their frozen outputs, and an
independent standard-library verifier. Follow `rcaeval/README.md` to download
the public cases at the recorded dataset revision and reproduce the scorer.

Raw execution logs are not included: they are large, they are append-only, and
nothing in the manuscript is computed from them directly. Objective and
dispersion tables are recomputable from `jobs.csv`; CRC arithmetic is
recomputable from the explicit ledger. Re-fitting the predictor from raw
telemetry still requires the branch records retained on the analysis host, so
this derived-data package does not claim full end-to-end re-execution.
INNER

echo
echo "wrote $out"
du -sh "$out"
echo "now: tar -czf dist/csc-iot-data.tar.gz -C dist zenodo-data"
