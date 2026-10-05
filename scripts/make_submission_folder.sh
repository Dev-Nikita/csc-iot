#!/usr/bin/env bash
# Rebuild paper/submission-ready/ from the working copy.
#
# The folder is a copy, so it goes stale the moment paper/main.tex changes. This
# rebuilds it and refuses to finish if the result does not compile cleanly on its
# own: a submission folder that only builds because of a file one directory up is
# the failure this script exists to prevent.
set -euo pipefail
cd "$(dirname "$0")/.."
src=paper; dst=paper/submission-ready
rm -rf "$dst"; mkdir -p "$dst/figures" "$dst/generated_tables"
cp "$src"/main.tex "$src"/supplement.tex "$src"/references.bib \
   "$src"/table_related.tex "$src"/table_scenarios.tex \
   "$src"/IEEEtran.cls "$src"/IEEEtran.bst "$dst"/
cp "$src"/figures/fig1_concept.tex "$src"/figures/fig2_architecture.tex "$dst"/figures/
for f in table_bands_merged table_prediction table_bands_single \
         table_bands_factored table_spanning table_runs; do
  cp "$src/generated_tables/$f.tex" "$dst/generated_tables/"
done
for keep in README.md cover_letter.md; do
  [ -f "$src/submission-ready-keep/$keep" ] && cp "$src/submission-ready-keep/$keep" "$dst/"
done
cd "$dst"
fail=0
for doc in main supplement; do
  latexmk -pdf -interaction=nonstopmode "$doc.tex" > "build_$doc.log" 2>&1 || true
  err=$(grep -c '^!' "build_$doc.log" || true)
  pages=$(pdfinfo "$doc.pdf" 2>/dev/null | awk '/^Pages/{print $2}')
  q=$(pdftotext "$doc.pdf" - 2>/dev/null | grep -c '\[?\]' || true)
  printf '%-11s errors=%s pages=%s unresolved=%s\n' "$doc" "$err" "${pages:-?}" "$q"
  [ "$err" = 0 ] && [ "$q" = 0 ] || fail=1
done
latexmk -c >/dev/null 2>&1 || true
rm -f build_main.log build_supplement.log
if [ "$fail" -ne 0 ]; then
  echo "REFUSED: the submission folder does not build cleanly on its own." >&2
  exit 1
fi
echo "submission folder rebuilt and verified"
