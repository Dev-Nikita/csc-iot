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
  # one row per branch: which branch, which action, which scenario. The objective
  # components are already in jobs.csv; this is the index that ties them to the
  # directory names the manifests use.
  ( cd "$root" && for d in [as]*-*; do [ -d "$d" ] || continue; echo "$d"; done ) \
    | sort > "$out/$name/branch_index.txt"
  n=$(wc -l < "$out/$name/branch_index.txt" | tr -d ' ')
  echo "packaged $name: $n branches"
done

mkdir -p "$out/generated_tables"
cp paper/generated_tables/*.tex "$out/generated_tables/" 2>/dev/null || true
cp RESULTS.md EXPERIMENT_PROTOCOL.md "$out/" 2>/dev/null || true

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

`generated_tables/` holds the tables as the analysis emitted them, and
`SHA256SUMS` covers every file here.

Raw execution logs are not included: they are large, they are append-only, and
nothing in the manuscript is computed from them directly. Everything the
manuscript reports is recomputable from `jobs.csv` with the analysis scripts in
the source repository.
INNER

echo
echo "wrote $out"
du -sh "$out"
echo "now: tar -czf dist/csc-iot-data.tar.gz -C dist zenodo-data"
