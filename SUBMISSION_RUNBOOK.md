# Submission runbook — IEEE TNSM

Every command, in order, with the folder it runs in. Written 2026-10-13.

Three machines are involved and mixing them up is the main way this goes wrong:

| Name | What it is | How you get there |
|---|---|---|
| **Mac** | your laptop, where the manuscript is written and built | Terminal |
| **host** | the analysis host, where branch data lives and runs happen | `ssh cybernord` |
| **web** | Zenodo, ORCID, ScholarOne | browser |

Paths on the Mac are relative to:

```
cd ~/"Science Article 2025-/Counterfactual Shadow Control Uncertainty-Aware Proactive SelfHealing for Mobile Edge IoT Systems/csc-iot-v2"
```

Everything below calls that `$P`. Set it once per terminal window:

```bash
export P=~/"Science Article 2025-/Counterfactual Shadow Control Uncertainty-Aware Proactive SelfHealing for Mobile Edge IoT Systems/csc-iot-v2"
cd "$P"
```

---

## Step 0 — Mac: confirm nothing drifted since the last build (2 min)

```bash
cd "$P"
make audit
```

Expect the last line `REPO AUDIT OK`. If it names a failed check, fix that before
anything else — the audit exists because each of those invariants has been
silently reverted at least once.

```bash
python3 paper/check_transcribed.py
python3 paper/check_citations.py
python3 paper/check_supplement_refs.py
```

If the audit prints `skip  unresolved-citation check (pdftotext not installed)`,
install poppler first — that skipped check is the one that catches a `[?]` in a
rendered PDF, which no LaTeX warning reports:

```bash
brew install poppler
make audit        # the line must now read ok, not skip
```

Expect, in order: `transcription check ok` (plus two lines marked QUOTED FROM A
CITED WORK — those are OpenTwin's figures and are supposed to be there),
`citation check passed (25 keys cited, 25 defined)`, `supplement reference check
ok: 12 macros match supplement.aux`.

```bash
pdfinfo paper/main.pdf | grep Pages          # expect 10
pdfinfo paper/supplement.pdf | grep Pages    # expect 7
pdftotext paper/main.pdf - | grep -c '\[?\]'        # expect 0
pdftotext paper/supplement.pdf - | grep -c '\[?\]'  # expect 0
```

---

## Step 1 — web: verify Zenodo 0.3 actually contains the data (10 min, BLOCKING)

Open <https://doi.org/10.5281/zenodo.23321904>. This is the one check nobody has
been able to do for you: a registered DOI proves the record exists, not what is
inside it.

Confirm all five, by eye:

1. The files list is non-empty and each file downloads.
2. `jobs.csv` is present for **all three** reported matrices: `b5-matrix-v2`,
   `d45-matrix-v1`, `d6-pilot-v2`.
3. `SHA256SUMS` is present. Download the archive and run `shasum -c SHA256SUMS`
   in the extracted folder — expect every line `OK`.
4. The packaged `RESULTS.md` is the current one. Check it contains the string
   `0.1011` (the corrected time-only control). If it says `0.1174`, the package
   was built before the fix and **must be rebuilt** — go to Step 1b.
5. No file is captioned `Placeholder` or `No Experiment Has Been Run`:
   `grep -rl "No Experiment Has Been Run" .` in the extracted folder must print
   nothing.

Also check the record's metadata: the creator list currently names only you.
Decide with Zinko whether he belongs there as a contributor to the code or data —
the paper's author list and the archive's creator list are separate metadata.
Zenodo lets you edit metadata without issuing a new version.

### Step 1b — rebuild and re-upload the package (host, then web)

Needed if Step 1 found anything wrong, and needed anyway if the package has no
`RESULTS.md` or an old one.

On the **Mac**, push the current tree to the host first, so the packaged
`RESULTS.md` is the current one:

```bash
cd "$P"
make deploy HOST=cybernord
```

Then on the **host** — one command, no placeholders to fill in:

```bash
ssh cybernord
cd ~/csc-iot
bash scripts/package_reported_matrices.sh
```

It finds the three matrix roots itself, refuses if a reported matrix appears
under no stack id or under more than one, and prints its own verification: the
three roots with their branch counts, the tarball, the branch total (**must be
8118**), the `RESULTS.md` check (`0.1011` present, `0.1174` absent) and a
placeholder scan that must print nothing.

Do not type a stack-id by hand. They are content-derived hashes, several of them
look alike, and two of the directories under `data/raw` are a quarantine and a
legacy copy that must not be packaged — the script excludes both.

Copy the tarball to the Mac:

```bash
exit
scp cybernord:~/csc-iot/dist/csc-iot-data.tar.gz ~/Downloads/
```

Then on **web**: Zenodo record → *New version* → upload the tarball → publish.
This mints a **new version DOI**, which is fine and changes nothing in the paper:
the manuscript cites the concept DOI `10.5281/zenodo.23165224`, which always
resolves to the newest version. Do not put a version DOI in the manuscript.

---

## Step 2 — web: ORCID for both authors (15 min, BLOCKING)

TNSM states that all IEEE publications require an ORCID for **all** authors, and
that a registered ORCID is needed to submit and to review proofs. This is a hard
stop on the submission form, not a recommendation.

1. <https://orcid.org/register> — you, if you do not already have one.
2. Send Zinko the same link. You cannot create one for him; the form will ask for
   his iD when you add him as a co-author.
3. Record both in `CITATION.cff` and in the ScholarOne author fields.

---

## Step 3 — the CRC audit (host + a human, BLOCKING by my judgement)

This is the item I would not submit without, because it is the one place where a
mistake would be a *wrong claim* rather than a missing measurement. Two parts.

**3a. The mathematics, by a person who is not you or me.** Give whoever reviews
it Section IV of the manuscript and S3 of the supplement, and ask them to check
exactly five things:

1. The loss is monotone in the threshold, as conformal risk control requires.
2. The dominance argument: that the failure indicator of the chosen action is
   bounded by the indicator that the admissible set contains a failing action.
3. That the threshold is selected on the calibration runs and nothing downstream
   reuses them.
4. Exchangeability of the calibration units — runs, not decision points.
5. The empty-admissible-set case: what the rule does, and that the guarantee
   still holds under every realised fallback.

**3b. The code against the formula.** On the **host**:

```bash
ssh cybernord
cd ~/csc-iot
python3 -m pytest intelligence/tests/test_crc.py -v
python3 -c "
import inspect, intelligence.conformal.crc as c
print(inspect.getsource(c.corrected_risk))
print(inspect.getsource(c.calibrate))"

```

The point of 3b is not that the test passes — it is that someone reads
`intelligence/conformal/crc.py` beside equation (8) and agrees they are the same
rule, including the `sup` being attained and the `+B/(n+1)` term.

---

## Step 4 — Mac: iThenticate and self-overlap (1 day of waiting)

Submit `paper/submission-ready/main.pdf` through the university's iThenticate.
I cannot give you a similarity percentage and will not guess one.

The risk here is **not** someone else's text — it is your own. You have several
manuscripts in this project line. Before the report comes back, check the overlap
yourself:

```bash
cd "$P"
pdftotext paper/main.pdf /tmp/this.txt
# for each of your other manuscripts:
pdftotext ~/path/to/other_paper.pdf /tmp/other.txt
python3 - <<'PY'
import re
a=open('/tmp/this.txt').read(); b=open('/tmp/other.txt').read()
def shingles(t,n=8):
    w=re.findall(r"[a-z']+",t.lower())
    return {" ".join(w[i:i+n]) for i in range(len(w)-n)}
A,B=shingles(a),shingles(b)
common=A&B
print(f"{len(common)} shared 8-word runs out of {len(A)}")
for c in sorted(common)[:20]: print("  ",c)
PY
```

Shared boilerplate in a methods description is normal; shared *paragraphs* are
what an editor flags as self-plagiarism. Rewrite those before submitting.

---

## Step 5 — web: ScholarOne, the one thing to confirm before you start the form

Neither ComSoc policy page documents whether TNSM accepts supplementary material
or under what file designation. Check the submission form's file-type list before
you begin. The main text is written so that no claim in it needs the supplement
to be assessed — that is the insurance — but find out anyway.

---

## Step 6 — Mac: the authorship and declaration sign-off (BLOCKING, human)

Send Zinko, in one message, the four things he has to actually confirm:

1. Co-authorship and the affiliation exactly as printed: *Lviv Polytechnic
   National University, Lviv, Ukraine*.
2. The author-contributions paragraph as written (page 10).
3. The AI-use statement as written — read it, not a summary of it. Both authors
   have to be able to stand behind it, including work done in sessions he did not
   see.
4. Whether he should be named as a creator on the Zenodo archive.

Do not submit before he answers 1–3. This is not a formality; it is the one
declaration where a disagreement after submission is very hard to repair.

---

## Step 7 — Mac: final freeze (10 min)

Only after Steps 1–6.

```bash
cd "$P"
latexmk -g -pdf -interaction=nonstopmode paper/main.tex
latexmk -g -pdf -interaction=nonstopmode paper/supplement.tex
bash scripts/make_submission_folder.sh
make audit
```

The submission script refuses to finish unless the copied folder compiles on its
own, and the audit fails if the copy has drifted from the working tree. Then
re-check the two numbers that a late edit breaks:

```bash
pdfinfo paper/main.pdf | grep Pages     # must be 10
pdftotext -f 1 -l 1 -x 0 -y 0 -W 306 -H 792 paper/main.pdf - | \
  awk '/Abstract/,/Index Terms/' | wc -w   # must be under 200; it is 186
```

**Page budget warning.** With two biographies of realistic length the paper is
still 10 pages, but the last page now holds 969 words of roughly a thousand. The
margin is about 30 words. If any step above makes you add a sentence to the main
text, spend R3 from the revision reserve (named in the header of `main.tex`)
rather than letting it run to page 11 at \$220.

---

## Step 8 — web: what to upload, in the order ScholarOne asks for it

From `paper/submission-ready/`:

| File | Designation on the form |
|---|---|
| `main.pdf` | Main Document |
| `supplement.pdf` | Supplementary Material (confirm the designation in Step 5) |
| `cover_letter.md` → paste as text | Cover Letter |

Do **not** upload: the `.tex` sources (not at submission; they are asked for at
acceptance), `PRESUBMISSION.md`, `EXPERIMENT_PROTOCOL.md`, the data tarball.
The protocol and the data reach reviewers through the Zenodo DOI in the paper,
which is the point of having it.

Form fields that are easy to get wrong:

- **Corresponding author:** N. Tarasov, dev.nikita@outlook.com.
- **Second author:** R. Zinko, roman.v.zinko@lpnu.ua, with his ORCID.
- **Abstract:** paste the 186-word abstract from the PDF, not from the `.tex`
  (the `.tex` has LaTeX markup in it).
- **Conflict of interest / funding:** the statements on page 10 of the manuscript.
- **Suggested reviewers:** if the form asks, do not name anyone you have
  co-authored with.

---

## Step 9 — Mac: after you press Submit

```bash
cd "$P"
git tag -a submitted-tnsm-$(date +%Y%m%d) -m "state of the repository at TNSM submission"
git push origin main --tags
```

Tag the exact state you submitted. When the reviews come back in three to five
months you will want to know what the paper said, not what the repository says
by then.

---

## What is deliberately NOT on this list

**Decision overhead.** Not measured, and not instrumented anywhere in the code.
It is declared as not measured in the manuscript (page 10) and the supplement
specifies the decomposition a replication should use, including the point that
the offline fork-and-replay cost is *not* part of it. Measuring it properly means
writing new instrumentation into the online decision path and re-running on the
host — a code change to a frozen stack, days before submission, to produce a
number no claim in the paper depends on. The honest version is the one already
there. If a reviewer asks, that is a strong revision answer, not a desk reject.

**Reading the manuscript one more time for style.** `PRESUBMISSION.md` has an
item that says: after the final freeze, stop rewriting the paper for style. It is
there because this is the stage at which papers acquire new errors.
