# Pre-submission gates

Ordered. Each one is either done or it is not; nothing here is a judgement call.
`scripts/audit_repo.sh` prints the open ones on every run.

The order matters and is not the obvious one. Page count is computed **last**,
because two of the gates below add text. Measuring the manuscript before the
bibliography is final tells you the length of a document you are not going to
submit.

## Gate 1 -- provenance of every reported figure (blocking)

- [ ] **0.589 and 0.428** (ablation A2, parameter-shift and mechanism-shift
      blocks of Table III) have no provenance anywhere in this repository.
      `paper/check_transcribed.py` lists them. Find them in the run log on the
      analysis host, add them to `RESULTS.md`, then delete their entries from
      `UNRECORDED` in that script.
- [x] **Regenerated on the analysis host** under the stable-sort fix. Both hosts
      now emit the same table to the digit (amendment 0.29), the pinned pre-fix
      copy is deleted, and `scripts/audit_repo.sh` fails if the pre-fix time-only
      control 0.1174 reappears.
- [x] **Section V-C rewritten from it.** The reduction against the time-only
      control reads 74 per cent, not 78: the control itself moved from 0.1174 to
      0.1011 once neighbour ties stopped being broken arbitrarily. The
      permutation factor is 6.2 either way and no conclusion changed.

This gate is otherwise still open on the first item.

## Gate 2 -- the bibliography (blocking, and it is a content gap)

- [ ] Expand from 19 to roughly **24--27** verified references: five to nine
      additions, not fifteen. The target is coverage of the nearest prior art,
      not a count. Padding to 35--50 would eat the page reserve, dilute Related
      Work and read as citation padding, which is its own reviewer comment.
- [ ] The additions exist to defend one sentence: *"No prior approach, to our
      knowledge, jointly ranks candidate interventions, selects the cheapest one
      admitted by a calibrated safety criterion, and validates that ranking
      against alternative futures that were actually executed."* Every candidate
      reference is judged by whether it bears on that claim. If it does not, it
      does not go in.
- [ ] Weight the additions toward the venue's own audience: TNSM first, then
      TMC, TON, TPDS, IoT-J, TSC, JSAC and strong ACM venues. Citing TNSM papers
      shows the editor the manuscript is talking to this Transactions.
- [ ] Re-check `ye2026nesyedge` and `desilva2026aurora`: both are arXiv
      preprints. Replace with the peer-reviewed version if one now exists.
- [ ] Every new entry verified at the source and recorded in
      `docs/literature.csv` before it enters `references.bib`. No exceptions, and
      no DOI that has not been seen at the publisher.

Expect this to add 0.2--0.4 page. It happens **before** Gate 5.

## Gate 3 -- authorship

- [ ] R. Zinko confirms co-authorship, the affiliation as printed, and the author
      contributions paragraph.
- [ ] Both authors read the AI-use statement and confirm it matches what actually
      happened, including work done outside the sessions it was written from.

## Gate 4 -- front and back matter

- [x] Funding, conflict of interest, data and code availability with the Zenodo
      DOI, author contributions, AI use.
- [x] Biographies deliberately absent: IEEE collects biosketches with the final
      files on acceptance.
- [ ] **Reserve about 0.3 page for them in the camera-ready budget.** TNSM counts
      biographies and author pictures inside the ten pages it provides free of
      charge, so removing them now defers the space, it does not create it.
- [ ] Confirm in ScholarOne that TNSM accepts supplementary material, and under
      which file designation. Neither ComSoc policy page documents it. The main
      text is written so that no claim in it requires the supplement to be
      assessed, which is the insurance; confirm anyway.
- [ ] Check the submission form's abstract word limit against the current
      abstract.
- [ ] **Publish the reported matrices' derived data** (Zenodo version 0.2).
      Supplement S9 currently says the branch data for the three reported
      matrices is held on the analysis host and is not in the artifact
      repository. For a paper whose contribution is that an evaluation must be
      auditable, that is an invitation to ask why the headline data is the part
      that is missing. Run `scripts/make_data_package.sh` on the analysis host
      over the three reported matrix roots; it packages `jobs.csv`, the run
      manifests, a branch index, the generated tables and SHA-256 sums, and
      leaves the raw logs where they are.
- [ ] **Only after that upload**, replace the sentence in Supplement S9 and the
      matching one in the main manuscript's data-availability statement. Until
      the upload exists the current wording is the true one, and changing it
      first would make the paper claim something that is not yet so. The
      replacement:

      > Derived per-branch outcome tables, run manifests and checksums for all
      > three reported matrices are archived with the artifact; raw execution
      > logs are retained on the analysis host and are available from the
      > corresponding author.
- [ ] Neither PDF contains `[?]`. Check with `pdftotext file.pdf - | grep '\[?\]'`,
      not by reading the LaTeX log: an undefined citation in a document with no
      bibliography at all produces no warning to grep for. That is how eight of
      them survived a build that reported zero problems.

## Gate 5 -- final page count, computed last

- [ ] Rebuild after Gates 2 and 3 and read the page count then.
      - 9.7--9.9 pages: submit as is.
      - exactly 10.0: submit as is.
      - 10.4 or more: cut now, from the revision reserve named in the header
        comment of `paper/main.tex`, in the order R1, R2, R4, R3. Do not plan to
        fix it after review.
- [ ] One final PDF freeze. After it, stop rewriting the paper for style.

## How a revision is absorbed

A reviewer can demand that something be clarified **in the main manuscript**, and
answering that it is in the supplement will not do. The working model is:

- the main text gets the 2--5 sentences that close the criticism directly;
- the supplement gets the table, the sensitivity analysis or the full experiment;
- the response letter carries the argument.

That is usually 200--400 words of main-text growth per reviewer, which is what
the R1--R4 reserve is sized for. The supplement is not an automatic escape from
a major revision; it is what keeps the growth to sentences instead of pages.
