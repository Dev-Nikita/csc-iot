# Pre-submission gates

Ordered. Each one is either done or it is not; nothing here is a judgement call.
`scripts/audit_repo.sh` prints the open ones on every run.

The order matters and is not the obvious one. Page count is computed **last**,
because two of the gates below add text. Measuring the manuscript before the
bibliography is final tells you the length of a document you are not going to
submit.

## Gate 1 -- provenance of every reported figure (blocking)

- [x] **0.589 and 0.428 recomputed** on the analysis host 2026-10-05. Every B6
      and A1b figure was reproduced exactly and both A2 figures came back
      identical to the manuscript. The full `evaluate.py` output is in
      `RESULTS.md`; `paper/check_transcribed.py` now reports no unrecorded
      figure, across 84 checked figures in both documents.
- [x] **The re-run surfaced a third result against the method** and it is now
      stated: A2, which removes minimum-necessary selection and nothing else, is
      never worse than CSC and better on both shifted blocks. See amendment 0.30,
      Section V-F and Supplement S9.
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

- [x] **Expanded from 19 to 25**, by a search run against the novelty sentence
      rather than for coverage. Six entries added, each verified at the source and
      recorded in `docs/literature.csv`: `dai2026saferemediation`,
      `zhang2026opentwin`, `alomar2023causalsim`, `scott2016demi`,
      `malik2023chess`, `bartolini2020identifiability`. A seventh candidate
      (Sayer, SoCC 2021) was dropped: its author list could not be confirmed at
      the source, and the project's rule is that this is disqualifying.
- [x] **The novelty sentence is narrowed, because the search defeated part of
      it.** Ranking remediation actions and gating them on a risk criterion are
      both now published: a constrained-MDP formulation bounds a false-remediation
      rate and rejects repairs on blast radius, reversibility and epistemic
      uncertainty \[dai2026saferemediation\], and a conformal gate admits an Open
      RAN action only when its whole prediction set lies in the safe region
      \[zhang2026opentwin\]. The claim now rests on the third element alone --
      executing the rejected actions from the decision's own state -- which
      nothing found does. "No prior approach" became a statement about that
      element, not about the conjunction.
- [x] **Both 2026 preprints read in full (2026-10-13).** The gap claim survives,
      and now for a checkable reason rather than for want of a reading. One does
      execute candidate actions -- which its abstract did not say -- but only
      while its training set is built, each in an isolated replica after a full
      state reset, and at decision time its alternatives are valued by learned
      estimators. The other scores candidates in a calibrated forward model and
      states that it does not run them on the network. Neither verifies that
      compared branches start from the same state, and neither reports how much
      of a measured difference between actions is nondeterminism. Both now have
      rows in Table S1, S2 states the grounds for every mark, and the main text's
      gap sentence names what each one does instead of asserting a negative.
      Amendment 0.35 records it. One of them also reports independently that
      matching telemetry does not establish configuration recovery, which is
      this paper's first limit from the other direction and is now cited where
      the limits are introduced.
- [ ] **One entry still open after two verification sweeps** (was three). All
      nineteen were checked against the record; none is invented and none has a
      wrong author list, venue or page range. Three could not be settled from
      here and need a check on IEEE Xplore, which this environment cannot read:
      - `siew2022fire`: STILL OPEN, narrowed. The arXiv listing (v4, 2025-10-19)
        gives the eight authors in the order cited and carries no journal
        reference, so the preprint is the citable version and the six-author
        third-party index does not override the paper's own front matter.
        Whether Xplore document 11223793 is a published version still cannot be
        read from here; check it at proof.
      - `wu2021dtn`: CLOSED 2026-10-13. The DOI resolves to a record whose
        title, three authors in order, journal, volume 8, issue 18, pages
        13789-13804 and year match the entry field for field.
      - `ye2026nesyedge`: CLOSED for now. Its listing carries no journal
        reference, DOI or acceptance note, so the suspected IEEE EDGE 2026
        version is not announced; re-check at proof.
      Settled and already applied: `gibbs2021aci` now cites the NeurIPS 2021
      record rather than the preprint; `bonilla2026slr` carries the author
      spellings and article number the Crossref record has;
      `angelopoulos2021gentle` stays an arXiv citation, because the first author's
      own publication list gives no journal version.
- [ ] `desilva2026aurora` and `huang2025cascades` have no peer-reviewed version;
      re-check at submission time.
- [ ] Every new entry verified at the source and recorded in
      `docs/literature.csv` before it enters `references.bib`. No exceptions, and
      no DOI that has not been seen at the publisher.

Expect this to add 0.2--0.4 page. It happens **before** Gate 5.

## Gate 2b -- originality screening

- [ ] **Run the manuscript through iThenticate or Turnitin** via the university.
      This cannot be done from the project environment and no substitute for it
      exists here. What was done instead: the distinctive terminology of the paper
      ("reconstructible fork-and-replay", "transport-quiescent common anchors",
      "minimum-necessary intervention" in this sense) returns no matching text
      anywhere on the web, which is consistent with originality but is not a
      similarity report.
- [ ] **Check overlap against your own other manuscripts**, which is what an
      editor's similarity report will flag first. Several share this project's
      lineage and vocabulary. Text reused from your own unpublished or published
      work has to be rewritten or cited, not carried over.

      *This box was ticked on 2026-10-06 and has been un-ticked. Nothing in the
      repository records the comparison being made, and it is a check only an
      author can perform. If you did it, tick it again and say against which
      manuscripts; if you have not, it is still open. A checklist that records an
      unperformed verification is the failure this project exists to avoid, and
      it would be a strange one to commit in this paper of all papers.*

## Gate 2c -- raised by the 2026-10-12 independent review

- [x] **Reference [24] corrected.** The review found that the published PDF's
      title page lists six authors and the entry carried five. Verified: the
      USENIX catalogue page omits Aurojit Panda, the title page does not. Fixed in
      `references.bib` and `docs/literature.csv`, with the reason recorded there.
      A publisher's catalogue page is not the paper.
- [x] **The three limits are no longer presented as one kind.** Limits 1 and 2 are
      structural -- distinct configurations give the same observation, or the
      quantity does not enter it. Limit 3 is a resolution limit: the quantity does
      move the measurement, by 0.0001, and is dominated by a term independent of
      the action. Section V-G now says so, and the contributions define the term
      where it is first claimed. This was the review's strongest point.
- [x] **The AI statement no longer reads as self-contradictory.** It now
      distinguishes writing code from generating data explicitly.
- [x] **The archive DOI printed in the paper was the wrong one.** Zenodo was
      unreachable from here, so the identifiers were read from the DataCite
      metadata API instead, which settles it: `10.5281/zenodo.23165224` is the
      concept DOI (all versions), `...23165225` is version **0.1**,
      `...23169891` is 0.2 and `...23321904` is 0.3, published 2026-10-12. The
      manuscript, the cover letter and the README all printed `...23165225` --
      that is, they pointed a reader at version 0.1, which predates the corrected
      prediction table, rather than at the data that backs the figures. Now
      corrected everywhere to the concept DOI, with version 0.3 named explicitly.
      The 2026-10-13 review called this a mismatch between the manuscript and the
      cover letter; there was no mismatch between those two documents -- both were
      consistently wrong in the same way, which is worse.
- [x] **The package itself is verified -- independently, file by file.** The
      tarball built by `scripts/package_reported_matrices.sh` on 2026-10-13 was
      extracted and checked away from the host that produced it:
      all **17** `SHA256SUMS` lines `OK`; `jobs.csv` row counts
      6210 + 1800 + 108 = **8118**, each matching its own `branch_index.txt`;
      no file containing "Placeholder" or "No Experiment Has Been Run"; six
      generated tables present; `RESULTS.md` and `EXPERIMENT_PROTOCOL.md`
      present. Two reported figures were then recomputed from `jobs.csv` alone,
      without the analysis scripts: the NO_OP-to-REROUTE gap in $J$ is
      **0.0445** and the implied crossing price **0.667**, both exactly as
      printed; the resource movement is 0.000057, which is the 0.0001 the paper
      reports at four decimals. The archive does back the paper.
- [ ] **Upload that tarball as a new Zenodo version, then confirm the record.**
      The verified package is `dist/csc-iot-data.tar.gz` (470 KB), already copied
      to the Mac. Zenodo record -> New version -> upload -> publish. It mints a
      new version DOI, which changes nothing in the manuscript: the paper cites
      the concept DOI `10.5281/zenodo.23165224`, which resolves to the newest
      version. Afterwards open the record and confirm the files are **listed and
      downloadable** -- that is the one thing a verified local tarball does not
      prove, because a failed or partial upload looks like nothing from here.
- [ ] **Register and record ORCID for both authors. Confirmed required.** The
      TNSM submission page states: "All IEEE publications require an Open
      Researcher and Contributor ID (ORCID) for all authors," and that a
      registered ORCID is needed to submit a manuscript or review a proof. An
      earlier note here recorded this as unconfirmed; it is confirmed, and it is a
      hard blocker on the submission form, not a recommendation.
- [ ] **Decision overhead.** Still not measured, and it is the most obvious
      reviewer question about a runtime mechanism. A single instrumented run on
      the existing testbed would answer it. Either do it or state in the Discussion
      why it is out of scope for a decision-quality study. If it is measured,
      report the online path only -- feature extraction, the RPC, the model, the
      counterfactual scoring and the gate -- with p50/p95/p99 and a deadline-miss
      rate, and keep the offline fork-and-replay benchmark out of that figure:
      replay is how the decisions were *evaluated*, and charging its cost to the
      online decision would overstate the latency by orders of magnitude. The
      2026-10-13 review raised this distinction and it is the right one.
- [ ] **An independent audit of the CRC construction** -- that the finite-sample
      rule applies to this run-level loss and to taking the largest admissible
      threshold, and that adaptive selection from the admissible set is covered
      under every realised fallback. The guarantee is stated conservatively, but
      it has not been checked by anyone outside this work.

## Gate 3 -- authorship

- [x] **Four authors; affiliation and contributions supplied and in the paper.**
      All four are with the Department of Computer-Aided Design Systems,
      Institute of Computer Science and Information Technologies, Lviv
      Polytechnic National University. The contributions paragraph is the text
      the authors themselves confirmed, naming what each did, and states that all
      four reviewed and approved the manuscript and accept responsibility for
      their respective contributions. The `UNCONFIRMED` markers are gone and the
      audit passes again.
- [x] **E-mail addresses supplied; the spelling question answered by them.** All
      four institutional addresses are now in the thanks footnote and the cover
      letter: `Nikita.A.Tarasov@lpnu.ua`, `Roman.V.Zinko@lpnu.ua`,
      `Vira.M.Oksentyuk@lpnu.ua`, `Oksana.V.Oborska@lpnu.ua`. The university's own
      address spells it **Oksentyuk**, not the "Oksentiuk" this file had from the
      official transliteration, so the manuscript, the cover letter and the
      biographies now follow the university. The corresponding address changed
      from the personal one to the institutional one, which is what IEEE prefers.
      One thing left to eyeball: that Scopus 58178836600 publishes the same
      spelling. Scopus cannot be read from here.

- [ ] R. Zinko confirms co-authorship, the affiliation as printed, and the author
      contributions paragraph.
- [ ] **All four** authors read the AI-use statement and confirm it matches what
      actually happened, including work done outside the sessions it was written
      from. Adding authors does not make this easier: each of them is
      accountable for a declaration about work they did not watch, which is a
      reason to show them the statement rather than summarise it.

## Gate 4 -- front and back matter

- [x] Funding, conflict of interest, data and code availability with the Zenodo
      DOI, author contributions, AI use.
- [x] **Biographies written and measured; the camera-ready is one page over and
      that is now a decision, not a surprise.** `paper/biographies.tex` is not
      `\input` by `main.tex` -- IEEE collects biosketches at acceptance -- and the
      three unsupplied research-interest lines are marked `FILL:`, which the audit
      refuses if the file is ever included. Measured after the declarations were
      corrected on 2026-10-16: four `IEEEbiographynophoto` entries give
      **11 pages**, with **39 words** on page 11. Three passages were tightened by
      35 words without losing a fact and the biographies themselves were cut; the
      spill went 47 to 39 and the eleventh page did not go away, because what
      spills is an unbreakable biography block.
      **The choice at camera-ready, stated plainly:** take roughly 50 more words
      out of the main text, or pay US$220 for one overlength page. The revision
      reserve is spent -- R1, R2 and R4 were taken for the 2026-10-13 revision and
      R3 on 2026-10-16 -- so the next cut comes out of substance. Do not cut now:
      the real research interests are not written yet, review will change the text
      anyway, and this is measured again at camera-ready. Test build: `/tmp/cr`.

- [ ] Confirm in ScholarOne that TNSM accepts supplementary material, and under
      which file designation. Neither ComSoc policy page documents it. The main
      text is written so that no claim in it requires the supplement to be
      assessed, which is the insurance; confirm anyway.
- [x] Abstract length checked against the policy, not the submission form.
      TNSM requires "a 75 to 200 word abstract"; the rendered abstract is **186
      words**, counted on 2026-10-13 from the left column of page 1 of the PDF:
      `pdftotext -f 1 -l 1 -x 0 -y 0 -W 306 -H 792 main.pdf -`. The earlier
      figure recorded here, 175, came from a count over the whole page, which in
      a two-column layout interleaves the second column and is not a count of
      the abstract; it was wrong in the safe direction. The 232-word abstract
      this replaced was over the limit, and that was a formal violation this
      checklist had listed and nobody had executed. Margin is now 14 words --
      re-count after any edit to the abstract, with the command above.
- [x] **Derived data re-published as Zenodo 0.3.** Version 0.2 was defective --
      the packaging script copied every generated table and so shipped two files
      captioned "Placeholder --- No Experiment Has Been Run" into the archive of a
      paper reporting 8118 branches, and its `RESULTS.md` predated the prediction
      figures and the A2 table. The script refuses to finish on a placeholder now.
      Version 0.3 was issued 2026-10-12 (`10.5281/zenodo.23321904`, concept DOI
      `...23165224`), which DataCite confirms. **Still to confirm by eye, and it is
      not a formality:** that 0.3 actually lists and serves `jobs.csv`, the
      manifests, the branch index, the generated tables and `SHA256SUMS`, that the
      packaged `RESULTS.md` is the current one, and that no placeholder file is in
      it. A registered DOI proves a record exists, not what is inside it.
- [x] **Supplement S9 and the data-availability statement now separate the three
      tiers.** They had said only that branch data for the three reported matrices
      is held on the analysis host, which was true before the upload and stale
      after it. The wording now distinguishes what is published (derived
      per-branch tables, manifests, branch index, generated tables, SHA-256 sums
      -- enough to recompute every reported figure), what is not (raw per-branch
      execution logs, retained on the analysis host, available from the
      corresponding author), and what `RESULTS.md` holds (the aggregated readings
      the manuscript is transcribed against). Re-read this against the actual
      contents of 0.3 when you check it: if the package lacks any of the four
      published items, this wording is the thing that becomes false.
- [ ] **Archive authorship.** The DataCite record for 0.3 lists one creator,
      N. Tarasov. If R. Zinko contributed to the code or the data rather than to
      the manuscript alone, the archive's creator list should say so; it is
      separate metadata from the paper's author list and nobody checks it for you.
      Raised by the 2026-10-13 review. Decide with him, then edit the Zenodo
      record -- metadata can be edited without a new version.
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
