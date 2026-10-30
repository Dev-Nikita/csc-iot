#!/usr/bin/env python3
"""Point every document at a newly published archive version.

    python3 scripts/set_archive_doi.py <record-id> <version>
    python3 scripts/set_archive_doi.py 23400000 0.4

This exists because the DOI was once corrected by hand in
paper/submission-ready/cover_letter.md -- a file the submission builder wipes and
re-copies from submission-ready-keep/ -- so every rebuild silently restored the
wrong identifier. One script, every place, or it happens again.

It refuses unless the old identifier is found exactly where it is expected, so a
half-applied rename cannot pass unnoticed. Run scripts/audit_repo.sh afterwards.
"""
import pathlib
import re
import sys

OLD_ID = "23321904"
OLD_VER = "0.3"


def edit(path, pairs, required=True):
    p = pathlib.Path(path)
    if not p.exists():
        if required:
            sys.exit(f"REFUSED: {path} is missing")
        return 0
    s = original = p.read_text()
    for old, new in pairs:
        n = s.count(old)
        if n == 0:
            sys.exit(f"REFUSED: {path} does not contain the expected text:\n  {old[:120]}")
        s = s.replace(old, new)
    if s != original:
        p.write_text(s)
    return 1


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    new_id, new_ver = sys.argv[1], sys.argv[2]
    if not re.fullmatch(r"\d{6,}", new_id):
        sys.exit("REFUSED: the record id must be the numeric Zenodo id, e.g. 23400000")
    if not re.fullmatch(r"\d+\.\d+", new_ver):
        sys.exit("REFUSED: the version must look like 0.4")
    if new_id == OLD_ID:
        sys.exit("REFUSED: that is the identifier already in the documents")

    # 1. The thanks footnote: the archive is no longer code-only.
    edit("paper/main.tex", [(
        f"""\\thanks{{The current public archive contains the source-code snapshot at
\\protect\\url{{https://doi.org/10.5281/zenodo.{OLD_ID}}} (version~{OLD_VER}) and
is developed at""",
        f"""\\thanks{{The source code and the derived-data package for this revision are
archived together at
\\protect\\url{{https://doi.org/10.5281/zenodo.{new_id}}} (version~{new_ver}) and
the code is developed at""",
    )])

    # 2. Data and code availability: the blocker sentence goes, because the
    #    package it was waiting for is now published.
    edit("paper/main.tex", [(
        f"""\\textbf{{Data and code availability.}} The current public version
\\url{{https://doi.org/10.5281/zenodo.{OLD_ID}}} archives the source-code snapshot,
not the derived matrices used by this revision. A checksum-covered package has
been prepared containing the per-branch objective rows, manifests, structural
and decision outputs, CRC calibration ledger and RCAEval cases and analyses.
This manuscript is not to be submitted until that package is published as a new
version and the exact version DOI is inserted here. Raw per-branch execution logs
are retained on the analysis host and are available from the corresponding
author.""",
        f"""\\textbf{{Data and code availability.}} Version~{new_ver} of the archive,
\\url{{https://doi.org/10.5281/zenodo.{new_id}}}, carries the source code and a
checksum-covered derived-data package: the per-branch objective rows and manifests
for all three reported matrices, the structural and decision outputs, the CRC
calibration ledger with a reconstruction that reads it without importing our
calibration code, and the RCAEval cases with both analyses and a standard-library
verifier. Every file is covered by \\texttt{{SHA256SUMS}}. Re-fitting the predictor
from raw telemetry additionally requires the per-branch execution logs, which are
retained on the analysis host and are available from the corresponding author.""",
    )])

    # 3. Cover letter.
    edit("paper/submission-ready-keep/cover_letter.md", [(
        f"""The source
snapshot is archived at https://doi.org/10.5281/zenodo.{OLD_ID}. The derived-data
package for this revision is being prepared as a new archive version; this letter
and manuscript must receive its exact DOI before submission.""",
        f"""The code and the
derived-data package for this revision are archived together at
https://doi.org/10.5281/zenodo.{new_id} (version {new_ver}), where every file is
covered by published checksums and the calibration threshold and benchmark
analysis can both be recomputed without our implementations.""",
    )])

    # 4. Editorial-office email.
    edit("paper/submission-ready-keep/email_to_editorial_office.md",
         [(f"https://doi.org/10.5281/zenodo.{OLD_ID}",
           f"https://doi.org/10.5281/zenodo.{new_id}")])

    # 5. README.
    edit("README.md", [(
        f"""Archived release: **[10.5281/zenodo.{OLD_ID}](https://doi.org/10.5281/zenodo.{OLD_ID})**
(version {OLD_VER}, <https://zenodo.org/records/{OLD_ID}>). This is the identifier the
manuscript cites and the one to use.""",
        f"""Archived release: **[10.5281/zenodo.{new_id}](https://doi.org/10.5281/zenodo.{new_id})**
(version {new_ver}, <https://zenodo.org/records/{new_id}>). This is the identifier the
manuscript cites and the one to use. It holds two files: the code snapshot and
`csc-iot-data.tar.gz`, the checksum-covered derived data for the reported
matrices. Version {OLD_VER} (`...{OLD_ID}`) is superseded: it shipped code only.""",
    )])

    # 6. CITATION.cff.
    edit("CITATION.cff", [(f'doi: "10.5281/zenodo.{OLD_ID}"',
                           f'doi: "10.5281/zenodo.{new_id}"'),
                          (f'version: "{OLD_VER}"', f'version: "{new_ver}"')])

    # 7. The audit guard itself: the superseded identifier joins the refused set
    #    and the new one becomes the only one a reader may be handed.
    edit("scripts/audit_repo.sh", [
        (f"zenodo\\.(23165224|23165225|23169891|23317517)",
         f"zenodo\\.(23165224|23165225|23169891|23317517|{OLD_ID})"),
        # This string occurs twice, in the explaining comment and in the error
        # the guard prints; replace() takes both, so one pair is correct and a
        # second pair for the parenthesised form would find nothing and refuse.
        (f"10.5281/zenodo.{OLD_ID}, version {OLD_VER}",
         f"10.5281/zenodo.{new_id}, version {new_ver}"),
    ])

    print(f"every document now cites 10.5281/zenodo.{new_id} (version {new_ver})")
    print("next: bash scripts/make_submission_folder.sh && bash scripts/audit_repo.sh")


if __name__ == "__main__":
    main()
