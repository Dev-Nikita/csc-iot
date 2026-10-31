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

def _current():
    """The identifier and version every document carries now.

    This used to be two literals, which meant the script worked exactly once and
    then silently referred to a superseded record. CITATION.cff is the one file
    that states both and is checked by the audit, so it is the source.
    """
    import pathlib as _p
    import re as _re
    text = _p.Path("CITATION.cff").read_text()
    doi = _re.search(r'doi:\s*"10\.5281/zenodo\.(\d+)"', text)
    ver = _re.search(r'version:\s*"([\d.]+)"', text)
    if not doi or not ver:
        raise SystemExit("REFUSED: CITATION.cff does not state a doi and a version")
    return doi.group(1), ver.group(1)


OLD_ID, OLD_VER = _current()


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


def bump_versions(path, old_ver, new_ver):
    """Rewrite every `version~X` / `Version~X` / `version X` in a LaTeX file."""
    p = pathlib.Path(path)
    s = p.read_text()
    pattern = re.compile(r"([Vv]ersion[~ ]\$?)" + re.escape(old_ver) + r"(\$?)")
    s2, n = pattern.subn(lambda m: m.group(1) + new_ver + m.group(2), s)
    if n == 0:
        sys.exit(f"REFUSED: {path} states no version {old_ver}")
    p.write_text(s2)
    print(f"  {path}: {n} version mention(s) -> {new_ver}")


def append_superseded(version):
    """Add a version to README's superseded list, in order, once."""
    p = pathlib.Path("README.md")
    s = p.read_text()
    m = re.search(r"^Superseded versions: ([^\n]*?)\.$", s, re.M)
    if not m:
        sys.exit("REFUSED: README.md has no 'Superseded versions:' line")
    have = [x.strip() for x in m.group(1).split(",") if x.strip()]
    if version in have:
        return
    have.append(version)
    have.sort(key=lambda v: [int(x) for x in v.split(".")])
    s = s[:m.start()] + "Superseded versions: " + ", ".join(have) + "." + s[m.end():]
    p.write_text(s)


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

    # Each document states the identifier in its own wording. The rename is
    # therefore a substitution of the identifier and the version within the
    # sentences that already exist, not a rewrite of those sentences: an earlier
    # version of this script carried the pre-0.5 prose as its anchors and would
    # only ever have worked once.
    doi = [(f"10.5281/zenodo.{OLD_ID}", f"10.5281/zenodo.{new_id}")]
    # The records URL appears in README.md only; listing it for every file would
    # make the script refuse on a file that is perfectly correct.
    pairs = doi
    # Every spelling of the version, not just the parenthesised one. The
    # availability paragraph said "Version~0.5 of the archive" and survived two
    # renames, because the script matched "(version~0.5)" and nothing else.
    edit("paper/main.tex", pairs)
    bump_versions("paper/main.tex", OLD_VER, new_ver)
    bump_versions("paper/supplement.tex", OLD_VER, new_ver)
    edit("paper/submission-ready-keep/cover_letter.md", pairs + [
        (f"(version {OLD_VER})", f"(version {new_ver})")])
    edit("paper/submission-ready-keep/email_to_editorial_office.md", pairs)
    edit("README.md", pairs + [
        (f"zenodo.org/records/{OLD_ID}", f"zenodo.org/records/{new_id}"),
        (f"(version {OLD_VER}, <https://", f"(version {new_ver}, <https://"),
        ])
    append_superseded(OLD_VER)
    edit("CITATION.cff", [(f'doi: "10.5281/zenodo.{OLD_ID}"',
                           f'doi: "10.5281/zenodo.{new_id}"'),
                          (f'version: "{OLD_VER}"', f'version: "{new_ver}"')])

    # The refused set grows by one identifier each time a version is superseded,
    # so it is read out of the guard rather than written here as a literal that
    # would be correct only until the next release.
    guard = pathlib.Path("scripts/audit_repo.sh").read_text()
    m = re.search(r"zenodo\\\.\([0-9|]+\)", guard)
    if not m:
        sys.exit("REFUSED: no refused-identifier set in scripts/audit_repo.sh")
    refused = m.group(0)
    if OLD_ID in refused:
        sys.exit(f"REFUSED: {OLD_ID} is already refused by the audit; the rename "
                 "may already have been applied")

    # 7. The audit guard itself: the superseded identifier joins the refused set
    #    and the new one becomes the only one a reader may be handed.
    edit("scripts/audit_repo.sh", [
        (refused, refused[:-1] + f"|{OLD_ID})"),
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
