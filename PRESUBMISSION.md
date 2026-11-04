# Pre-submission checklist

**Target: IEEE Transactions on Dependable and Secure Computing (since
2026-10-30).** TNSM declined without review as out of scope; the manuscript was
reframed, not rewritten, and no result changed. Gates below that name TNSM page
counts, templates or supplementary handling are **void until re-checked against
TDSC** — its limits are different and could not be read from this environment.
Three new blockers, all of them lookups on the TDSC author page: the regular-paper
page limit and overlength charge; whether supplemental material is merged into
the review PDF; and whether the journal requires its own LaTeX class rather than
`IEEEtran`, which would make every page measurement in this file stale.


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
      no DOI that has not been seen at the publisher. `li2026pilot` was added on
      2026-10-30 only after the full NSDI paper and proceedings record were read;
      it is now the closest execution-level comparator and the priority claim was
      narrowed around it.

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
- [x] **The concept DOI does not resolve, so nothing published points at it.**
      `10.5281/zenodo.23165224` is registered and DataCite reports it `findable`,
      with a url of `https://zenodo.org/doi/10.5281/zenodo.23165224` and
      `HasVersion` entries for every version. It still returned "DOI not found"
      in a browser on 2026-10-16. Registered is not the test; opens is. The
      manuscript, the supplement, the cover letter and the README now print
      **`10.5281/zenodo.23321904`** (version 0.3), which is the only archive
      identifier a person has actually opened, and which is in any case the
      version that produced the figures -- citing the exact version is the better
      practice for data. The audit refuses any other zenodo identifier in a
      document a reader receives. If the concept DOI starts resolving later,
      nothing needs to change.
- [x] **Publish the archive and confirm it from outside.** Version 0.7,
      `10.5281/zenodo.23835333`, two files, DOI reserved on the draft before the
      tag so the archived code cites the version it is in.

      It carries the three matrices, the calibration ledger, the RCAEval cases
      and every analysis the manuscript cites, and it produces its own frozen
      outputs: `make_data_package.sh` runs the packaged scripts against the
      packaged data with `python3 -I` and refuses to build if the result differs
      from what the working tree claims. The first run of that check refused, on
      a recorded absolute path rather than on a number, which is what a check
      that has never fired usefully is supposed to look like the first time.

      Verified on a machine unrelated to the testbed or the author's laptop: 36
      files checksum, 8118 branch rows, `tau_hat=0.04468686866`, resampling spans
      0.078 and 0.021 with no draw abstaining, 161 design points, the
      four-criterion tables, and `INDEPENDENT RCAEval VERIFICATION OK`. The
      package's own `value_of_protocol_output.txt` matches a fresh run inside it.

      Versions 0.3 to 0.6 are superseded. Do not re-enable the GitHub release
      webhook: it packages the repository and nothing else, which is how 0.4 was
      published carrying no data.
- [ ] **Register and record ORCID for both authors. Confirmed required.** The
      TNSM submission page states: "All IEEE publications require an Open
      Researcher and Contributor ID (ORCID) for all authors," and that a
      registered ORCID is needed to submit a manuscript or review a proof. An
      earlier note here recorded this as unconfirmed; it is confirmed, and it is a
      hard blocker on the submission form, not a recommendation.
- [ ] **A limited seed control, specified here and not yet run.** One master
      seed, $42$, drives all three matrices, so nothing in this work distinguishes
      "this effect is a property of the system" from "this effect is a property of
      this realisation of the randomness". Reproducing the archive does not touch
      the question: that establishes that the computation repeats, not that the
      finding does. Re-running the whole design is not warranted, but ruling the
      question out in advance is not defensible either, so the control is
      specified now, before it is run, and the decision rule with it.

      **Design.** Twelve design points, chosen by a rule fixed here and not by
      inspecting outcomes: the first six `b5` D1 points, the first three `b5` D3
      points and the first three `d45` D4 points in scenario-identifier order.
      Each re-executed over its full anchor x action x repeat grid under master
      seed `20261101`, everything else unchanged. That is 648 branches, about
      8 per cent of the reported total, hours rather than a week.

      **What is compared, decided before the run.** On those twelve points only,
      under seed 42 and under the new seed: the pooled band `eta_J`; the share of
      anchors classed unresolved; and the number of anchors at which a single
      execution and repeated execution choose differently.

      **Decision rule.** If the unresolved share on the twelve points moves by
      more than 10 percentage points, or if the band moves by more than a factor
      of two, the seed dependence is material and the manuscript must either run
      the full design under a second seed or restrict its claim to the realisation
      it measured. If it moves by less, the control is reported as a bounded
      check -- twelve points, one additional seed -- and the limitation stays
      stated rather than removed. Either outcome is reported; the control is not
      re-specified after its result is seen.

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
- [ ] **An independent audit of the CRC construction.** Partly closed, and the
      remainder needs a person outside this work. What is done: the rule matches
      equation (4) of Angelopoulos et al. after the change of parameter, the
      monotonicity and pointwise-domination arguments pass code-and-claim review,
      a test that checked a tail probability instead of expected loss was
      repaired, and `analysis/recompute_crc_independent.py` recovers
      `tau_hat = 0.04468686866` from the frozen ledger alone, importing neither
      our CRC nor our predictor, on three different machines including a clean
      download of the published archive. Also done: the threshold was resampled
      over the executed replay repeats, 4000 draws, none abstaining, and the
      reported value is the minimum of all of them. What is not done: items 1, 3
      and 4 of `CRC_AUDIT.md` -- run identifiers against the manifests, the order
      of predictor fitting and `U_max` selection against calibration, and the
      search for evidence against exchangeability -- and none of it has been done
      by anyone other than the author. Fallback remains explicitly outside the
      guarantee.
- [x] **Two authors. V. Oksentyuk and O. Oborska withdrew 2026-10-30.** They
      declined to continue on the paper and are removed from the author line, the
      thanks footnote, the e-mail list, the author-contributions paragraph, the
      biographies and the cover letter. Both remaining authors are with the
      Department of Computer-Aided Design Systems, Institute of Computer Science
      and Information Technologies, Lviv Polytechnic National University. The
      contributions paragraph now describes two people and states that both
      reviewed and approved the manuscript.
- [x] **E-mail addresses supplied.** `Nikita.A.Tarasov@lpnu.ua` and
      `Roman.V.Zinko@lpnu.ua` are in the thanks footnote and the cover letter. The
      corresponding address is the institutional one, which is what IEEE prefers.
      The transliteration question that applied to a withdrawn author no longer
      arises.
- [ ] R. Zinko confirms co-authorship, the affiliation as printed, and the author
      contributions paragraph.
- [ ] **Both authors read the AI-use statement** and confirm it matches what
      actually happened, including work done outside the sessions it was written
      from. Each of them is accountable for a declaration about work they did not
      watch, which is the part that needs an actual conversation rather than a
      forwarded PDF.
- [x] Funding, conflict of interest, data and code availability with the Zenodo
      DOI, author contributions, AI use.
- [x] **Biographies written in full from the authors' own records, and the
      overlength page is now a priced decision.** `paper/biographies.tex` holds
      four complete entries -- degrees, dissertation titles, posts and research
      interests, all supplied by the authors, nothing inferred. It is not
      `\input` by `main.tex`: IEEE collects biosketches with the final files on
      acceptance, and nothing in the TNSM pages requires them at submission.
      Measured 2026-10-16, both ways:
      - full entries (about 140 words each): **11 pages**, 378 words on page 11;
      - cut to about 70 words each: **11 pages**, 139 words on page 11.
      Four biographies therefore do not fit in ten pages at any reasonable
      length. Reaching ten would mean removing roughly 150 words of substance
      from the main text, and the revision reserve is spent (R1, R2, R4 on
      2026-10-13; R3 on 2026-10-16). **The recommendation is to keep the full
      entries and pay the US$220 for one overlength page**, which is also the
      cheaper of the two in anything but money. Re-measure at camera-ready: the
      text will have changed by then. Test build: `/tmp/cr`.

- [ ] **BLOCKER, and it already fired once. Settle how the supplement travels.**
      The submission of 2026-10-16 (TNSM-2026-12519) was accepted by the portal
      and then unsubmitted by the editorial office for exceeding the 16-page
      limit. The manuscript is 10 pages and was never the problem: ScholarOne
      merges the review package into **one** proof PDF and the administrative
      check counts that file -- 4 pages of portal cover sheet + 10 of `main.pdf`
      + 7 of `supplement.pdf` = **21**. Uploading separate files is not the same
      as having them counted separately, and nothing in the ComSoc policy pages
      says so. Either re-upload the supplement under a designation confirmed not
      to be merged (ask: `paper/submission-ready-keep/email_to_editorial_office.md`
      is the query, ready to send to `tnsm@uwo.ca`), or submit the manuscript
      alone and let the archive DOI carry the supplement -- the main text is
      written so every claim in it can be assessed without it, which is what that
      insurance was for. **Then, on the final review step, open the merged proof
      the portal generates and count its pages before pressing submit.**

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
- [ ] **Archive metadata: two fields are wrong on the record the paper cites.**
      Checked against the Zenodo API on 2026-10-30, not in the browser session
      that uploaded it. The files, the DOI and the related identifier on
      `10.5281/zenodo.23820907` are correct, and both files replay end to end
      from a fresh download. Two metadata fields are not, and both are editable
      on a published record without minting a new version:

      1. **The version field is empty.** Zenodo therefore labels the record
         `v7`, an internal revision counter, while the manuscript, the cover
         letter, README.md and CITATION.cff all say `version 0.6`. A reviewer who
         opens the DOI sees a different version string than the one cited. Set it
         to `0.6`.
      2. **One creator where the paper has two.** N. Tarasov is listed;
         R. Zinko is not. This has now been true of every version. Decide with him
         whether he contributed to the code and data or to the manuscript alone --
         the creator list is separate metadata from the author list and nobody
         checks it for you -- then set it, with ORCIDs
         `0000-0003-1870-3436` and `0000-0002-3275-8188`.

      Versions 0.3, 0.4 and 0.5 carry the same single-creator defect, and 0.5's
      related identifier still points at `tree/0.4`. Fixing the superseded records
      is optional; fixing 0.6 is not, because it is the one the paper cites.
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

---

## 2026-11-04, measured on a clean build, not estimated

Built from the working tree in an isolated directory with `latexmk -pdf`, three
passes, bibliography resolved, no undefined references or citations, no overfull
boxes. The only warnings are missing small-caps-italic font shapes in the title
font, which do not affect layout.

- **`main.pdf` is 12 pages**, not the 13 recorded earlier. Removing the two
  co-authors who withdrew took the biographies down and recovered a page. Twelve
  is exactly the TDSC free allowance, so the overlength charge is **not** owed as
  the paper stands --- and the margin is **zero**. Page 12 holds 991 words; it is
  a full page, not a stub. Anything the campaign adds to Section V puts the paper
  at 13 pages and US$220, and that is now a planning decision rather than a
  discovery.
- **`supplement.pdf` is 9 pages**, not 7. It grew with S12.
- **The abstract was 244 rendered words against a 100-to-200-word limit.** IEEE
  Computer Society sets "Regular/special-issue paper -- 100 to 200 words" for
  journal abstracts, read at the first source on 2026-11-04. The abstract was
  186 words when it was last checked against TNSM's 75-to-200 rule; it grew to
  244 when the value-of-protocol result was written into it and nobody re-counted.
  **This was a formal violation of the target venue's rules, standing in the
  submission package.** It is now **191 words**, counted the same way: left column
  of page 1, label excluded. Every number and every claim is unchanged; only
  wording was compressed. Re-count after any edit:
  `pdftotext -f 1 -l 1 -x 0 -y 0 -W 306 -H 792 main.pdf - | sed -n '/Abstract/,/Index Terms/p'`
- `paper/page_budget.conf` now carries `ABSTRACT_MIN_WORDS` and
  `ABSTRACT_MAX_WORDS` with the source, so the build guard can enforce what was
  previously checked by hand once and then left.

### The TNSM desk reject, restated, because it decides the TDSC procedure

The manuscript was never the problem. The portal merged the review package into
one proof PDF --- 4 pages of cover sheet + 10 of `main.pdf` + 7 of
`supplement.pdf` = 21 --- and the administrative check counted that file against
a 16-page limit. Today the same arithmetic gives 4 + 12 + 9 = **25**.

IEEE CS policy says supplemental material goes in separate files, must not be
inside the main PDF, and is not counted. That is the policy and it is not what
failed: policy wording does not control what ScholarOne generates. So, for TDSC:

1. Submit the manuscript **alone** and let the archive DOI carry the supplement.
   The main text was written so that every claim in it can be assessed without
   the supplement; that insurance exists precisely for this, and this is when to
   spend it.
2. On the final review step, **open the merged proof the portal generates and
   count its pages before pressing submit.** This single action would have
   prevented the TNSM return outright, and it is the only check that does not
   depend on reading a policy page correctly.
