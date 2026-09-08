#!/usr/bin/env python3
"""Guard against the failure mode that check_stale.py cannot see.

A manuscript can be terminologically perfect and still ship broken: a .tex that
cites keys a stale .bib does not define compiles cleanly for whoever holds the
matching pair and prints [?] for everyone else. That happened in this project --
main.tex was committed with new citation keys while references.bib was not --
and the local build looked fine, so "it compiles here" proved nothing.

Checks:
  1. every \\cite{} key resolves to a BibTeX entry
  2. every BibTeX entry is cited (warning by default, error with --strict)
  3. the LaTeX log carries no undefined citation or reference
  4. the compiled PDF contains no [?] or ?? marker
  5. every cited key is marked verified in docs/literature.csv
"""
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
def _reachable_tex() -> list[Path]:
    """main.tex plus whatever it \\inputs, transitively.

    Globbing *.tex would also sweep up scratch copies (a probe build, an old
    draft) and report their stale keys as errors. Only files the document
    actually pulls in are part of the manuscript.
    """
    seen, stack = [], [HERE / "main.tex"]
    while stack:
        cur = stack.pop()
        if cur in seen or not cur.exists():
            continue
        seen.append(cur)
        for m in re.finditer(r"\\input\{([^}]+)\}", cur.read_text()):
            name = m.group(1)
            stack.append(HERE / (name if name.endswith(".tex") else name + ".tex"))
    return seen


TEX = _reachable_tex()
BIB = HERE / "references.bib"
LOG = HERE / "main.log"
PDF = HERE / "main.pdf"
LITERATURE = REPO / "docs" / "literature.csv"
OK_STATUS = {"verified", "verified-preprint"}


def cited_keys() -> set[str]:
    keys = set()
    for path in TEX:
        for m in re.finditer(r"\\cite[tp]?\*?(?:\[[^\]]*\])*\{([^}]+)\}", path.read_text()):
            keys |= {k.strip() for k in m.group(1).split(",") if k.strip()}
    return keys


def bib_keys() -> set[str]:
    if not BIB.exists():
        return set()
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", BIB.read_text()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="uncited bib entries are errors")
    args = ap.parse_args()

    errors, warnings = [], []
    cited, defined = cited_keys(), bib_keys()

    missing = cited - defined
    if missing:
        errors.append(f"cited but absent from references.bib: {sorted(missing)}")
    uncited = defined - cited
    if uncited:
        (errors if args.strict else warnings).append(f"in references.bib but never cited: {sorted(uncited)}")

    if LOG.exists():
        log = LOG.read_text(errors="ignore")
        for pat in (r"Citation `([^']+)' (?:on page \d+ )?undefined",
                    r"Reference `([^']+)' (?:on page \d+ )?undefined"):
            for m in re.finditer(pat, log):
                errors.append(f"LaTeX log: undefined {m.group(1)}")
    else:
        warnings.append("main.log not found; compile before checking")

    if PDF.exists():
        try:
            text = subprocess.run(["pdftotext", str(PDF), "-"], capture_output=True,
                                  text=True, check=True).stdout
            n = text.count("[?]") + len(re.findall(r"(?<!\w)\?\?(?!\w)", text))
            if n:
                errors.append(f"compiled PDF contains {n} unresolved marker(s)")
        except (FileNotFoundError, subprocess.CalledProcessError):
            warnings.append("pdftotext unavailable; skipped the PDF marker check")

    if LITERATURE.exists():
        status = {r["key"]: r["verification_status"] for r in csv.DictReader(LITERATURE.open())}
        for k in sorted(cited):
            st = status.get(k)
            if st is None:
                errors.append(f"{k} is cited but has no row in docs/literature.csv")
            elif st not in OK_STATUS:
                errors.append(f"{k} is cited with verification_status={st!r}")
    else:
        warnings.append("docs/literature.csv not found; skipped the verification check")

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        print("CITATION CHECK FAILED", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1
    print(f"citation check passed ({len(cited)} keys cited, {len(defined)} defined)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
