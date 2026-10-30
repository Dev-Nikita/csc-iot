#!/usr/bin/env bash
# Rebuild paper/submission-ready/ from the working copy.
#
# The folder is a copy, so it goes stale the moment paper/main.tex changes. This
# rebuilds it and refuses to finish if the result does not compile cleanly on its
# own: a submission folder that only builds because of a file one directory up is
# the failure this script exists to prevent.
set -euo pipefail
cd "$(dirname "$0")/.."
src=paper; dst=paper/submission-ready; dstabs="$PWD/paper/submission-ready"

# Checked BEFORE the old folder is deleted: a refusal must leave the previous
# package intact rather than a half-built one. An unconfirmed author line is not
# a formatting problem, and this folder is the thing that gets uploaded.
if grep -q 'UNCONFIRMED{' "$src/main.tex" 2>/dev/null; then
  echo "REFUSED: main.tex still carries an UNCONFIRMED authorship placeholder." >&2
  grep -n 'UNCONFIRMED{' "$src/main.tex" >&2
  echo "Affiliations and author contributions come from the people named." >&2
  exit 1
fi

rm -rf "$dst"; mkdir -p "$dst/figures" "$dst/generated_tables"
cp "$src"/main.tex "$src"/supplement.tex "$src"/references.bib \
   "$src"/table_related.tex "$src"/table_scenarios.tex "$src"/table_rcaeval.tex \
   "$src"/table_replication_sensitivity.tex \
   "$src"/IEEEtran.cls "$src"/IEEEtran.bst "$src"/biographies.tex "$dst"/
# main-camera-ready.tex is main.tex plus the biographies, nothing else. It exists
# so the biographies compile and their cost in pages is a measured number rather
# than an estimate, and so that the camera-ready is assembled months from now by
# running a file rather than by remembering a step. The SUBMITTED document stays
# main.pdf: IEEE collects biosketches with the final files on acceptance.
sed 's|^\\end{document}|\\input{biographies.tex}\n\\end{document}|' \
    "$src"/main.tex > "$dst"/main-camera-ready.tex
cp "$src"/figures/fig1_concept.tex "$src"/figures/fig2_architecture.tex "$dst"/figures/
for f in table_bands_merged table_prediction table_bands_single \
         table_bands_factored table_spanning table_runs; do
  cp "$src/generated_tables/$f.tex" "$dst/generated_tables/"
done
for keep in README.md cover_letter.md cover_letter.docx email_to_editorial_office.md; do
  [ -f "$src/submission-ready-keep/$keep" ] && cp "$src/submission-ready-keep/$keep" "$dst/"
done
# Build in a scratch directory on local disk, not in $dst. $dst lives in a
# user-mounted folder whose timestamp and visibility semantics are not those of a
# local filesystem: there, pdflatex wrote main.aux and the bibtex that followed
# did not see it, producing a PDF with 31 unresolved citations and no error. The
# copy in $dst is what gets uploaded, so it must be byte-identical to what was
# verified -- the PDFs are therefore built here and copied in.
build=$(mktemp -d)
cp -R "$dst"/. "$build"/
cd "$build"
fail=0
for doc in main supplement main-camera-ready; do
  # Explicit passes rather than latexmk. latexmk decides whether to rerun by
  # comparing file state, and on a mounted filesystem with coarse timestamp
  # granularity it concluded nothing had changed after bibtex and stopped -- a
  # PDF with 31 unresolved citations and zero errors, which is exactly the
  # failure this folder exists to prevent and which the check below caught.
  # pdflatex, bibtex, pdflatex, pdflatex is deterministic and does not care what
  # the filesystem reports.
  {
    pdflatex -interaction=nonstopmode "$doc.tex"
    bibtex "$doc"
    pdflatex -interaction=nonstopmode "$doc.tex"
    pdflatex -interaction=nonstopmode "$doc.tex"
  } > "build_$doc.log" 2>&1 || true
  err=$(grep -c '^!' "build_$doc.log" || true)
  pages=$(pdfinfo "$doc.pdf" 2>/dev/null | awk '/^Pages/{print $2}')
  q=$(pdftotext "$doc.pdf" - 2>/dev/null | grep -c '\[?\]' || true)
  printf '%-11s errors=%s pages=%s unresolved=%s\n' "$doc" "$err" "${pages:-?}" "$q"
  [ "$err" = 0 ] && [ "$q" = 0 ] || fail=1
  # The submitted manuscript is checked against the free-page allowance of the
  # journal actually being targeted, read from paper/page_budget.conf. When that
  # allowance is unset -- because nobody has yet read it on the journal's own
  # site -- the build says so and does not refuse. Refusing on a number nobody
  # verified would make the guard a source of cuts rather than of correctness.
  if [ "$doc" = main ]; then
    free=$(sed -n 's/^FREE_PAGES=//p' "$OLDPWD/paper/page_budget.conf" 2>/dev/null | tr -d ' ')
    jrnl=$(sed -n 's/^JOURNAL=//p' "$OLDPWD/paper/page_budget.conf" 2>/dev/null)
    if [ -z "$free" ]; then
      echo "            NOTE: free-page allowance for ${jrnl:-the target journal} is unset" >&2
      echo "            in paper/page_budget.conf; page count not checked." >&2
    elif [ "${pages:-0}" -gt "$free" ]; then
      echo "REFUSED: main.pdf is $pages pages against $free free for ${jrnl}." >&2
      fail=1
    fi
  fi
done
# paper/check_supplement_refs.py reads section numbering out of paper/*.aux, and
# the build happens in a scratch directory, so those .aux files were never
# refreshed and the check failed on staleness instead of on content. The .aux is
# a build artefact of this run; copying it back is what makes the macro check
# read the numbering the PDF actually prints.
cp main.aux supplement.aux "$OLDPWD/paper/" 2>/dev/null || true
latexmk -c >/dev/null 2>&1 || true
rm -f build_main.log build_supplement.log
# Only the artefacts a reader needs travel back: the PDFs and the .bbl, so the
# folder still builds standalone for an editor who runs LaTeX on it.
cp main.pdf supplement.pdf main-camera-ready.pdf \
   main.bbl supplement.bbl main-camera-ready.bbl "$dstabs"/
cd / && rm -rf "$build"
if [ "$fail" -ne 0 ]; then
  echo "REFUSED: the submission folder does not build cleanly on its own." >&2
  exit 1
fi
echo "submission folder rebuilt and verified"
