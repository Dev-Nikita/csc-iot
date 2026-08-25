# NOVELTY_AUDIT.md

Status: **round 1, 2026-08-25**. Re-run in full before implementation freeze and again before submission.
Audit owner: N. Tarasov. Method: targeted web/venue search + record-level bibliographic verification (dblp `/rec/`, arXiv abstract pages). No reference is listed here unless its bibliographic identity was checked at the source.

---

## 1. Verdict

**Novelty is not dead, but the original framing "causal AI for self-healing edge" is dead.** Two 2026 preprints from the same research line (Donta / Lapkovskis / Saleh, Stockholm University + Univ. of Helsinki) already occupy the "causal reasoning for self-healing in the computing continuum" territory, and one of them — AURORA — additionally has an uncertainty gate and an abstention mechanism. That is uncomfortably close to two of the five planned CSC pillars.

What survives, and what the paper must therefore be built and sold on:

| CSC pillar | Occupied by prior work? | Verdict |
|---|---|---|
| P1. Online action-conditioned counterfactual evaluation `P(F \| S, do(a))` over a candidate action set | **Partially** — AURORA computes `argmax_a P(S=1 \| do(a))` | Cannot be claimed alone |
| P2. Calibrated (conformal) uncertainty gating | **Partially** — AURORA gates on variational free energy, not calibrated coverage | Claimable only in the sharpened form "distribution-free calibrated risk bound with measured coverage" |
| P3. Safe abstention | **Yes** — AURORA abstains and escalates to fog tier (65.9% abstention rate) | **Do not claim as novel.** Cite AURORA and position CSC's abstention as inherited/comparable |
| P4. Minimum-necessary intervention (cheapest action subject to a risk constraint) | **No** — AURORA and NeSy-Edge both select by best predicted outcome, no cost model, no constrained selection | **Claimable** |
| P5. Deterministic fork-and-replay experimental counterfactual ground truth | **No hit found** | **Strongest claim.** This is the paper's spine |
| P6. Real distributed runtime prototype with kernel-level network emulation and mobility | **No** — AURORA is a Python Monte-Carlo simulator; NeSy-Edge replays static log datasets | **Claimable** |

**Reframed one-sentence contribution (supersedes the original):**
> CSC is not "a causal self-healing framework". It is a method for *deciding whether a runtime intervention is worth making at all* — cheapest sufficient action under a calibrated risk bound — together with the first experimental methodology that measures whether such counterfactual action rankings are actually correct, by forking a deterministic edge emulator and executing every candidate action from the same state.

**Consequence for the Introduction:** the gap sentence must no longer be "existing work predicts failure but does not reason causally". It must be:
> Recent work reasons causally about *which fault occurred* and gates remediation on confidence, but still selects the action with the best predicted outcome, without a cost model, without calibrated coverage guarantees, and — critically — without ever observing what the non-selected actions would have done.

---

## 2. Capability matrix (verified papers only)

Columns: **FP** failure prediction · **CG** explicit causal graph/SCM · **ACF** interventional estimate `P(Y|do(a))` for *multiple* candidate actions · **UQ** quantified uncertainty · **CAL** *calibrated* (coverage-checked) uncertainty · **ABS** abstention · **MNI** cost-minimal action under risk constraint · **RT** executes on a live/emulated running system · **REPLAY** counterfactual outcomes validated against replayed alternative executions · **CL** closed-loop check of the executed action against its own prediction

| # | Work | FP | CG | ACF | UQ | CAL | ABS | MNI | RT | REPLAY | CL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AURORA (arXiv:2605.10718, 2026) | ~ | Y | ~ | Y | N | **Y** | N | sim | N | N |
| 2 | NeSy-Edge (arXiv:2603.21145, 2026) | N | Y | N | N | N | ~ | N | N | N | N |
| 3 | Aral & Brandic, TPDS 32(7) 2021 | **Y** | ~ | N | N | N | N | N | ~ | N | N |
| 4 | Kumar, Yadav & Indrusiak, TNSM 20(3) 2023 | N | N | N | N | N | N | ~ | **Y** | N | N |
| 5 | Esmat, Lorenzo & Shi, IoT-J 10(16) 2023 | N | N | N | N | N | N | ~ | N | N | N |
| 6 | Xu & Xie, TPAMI 45(10) 2023 | N | N | N | Y | **Y** | N | N | N | N | N |
| 7 | Gibbs & Candès, arXiv:2106.00170 | N | N | N | Y | **Y** | N | N | N | N | N |
| 8 | Lindemann et al., arXiv:2409.00536 | N | N | N | Y | **Y** | ~ | ~ | ~ | N | N |
| 9 | Huang, Park, Paoletti & Simeone, arXiv:2510.17543 | N | N | N | Y | **Y** | **Y** | N | ~ | N | N |
| 10 | **Proposed CSC** | Y | Y | **Y** | Y | **Y** | Y | **Y** | **Y** | **Y** | **Y** |

Legend: Y = yes · ~ = partial / adjacent · N = no · sim = simulation only.
Rows 11-15 are **TODO** — the audit is not complete until 15 rows are filled. Candidates queued in `docs/literature.csv` (RL-based MEC recovery, GNN failure prediction in IoT, microservice root-cause analysis, chaos-engineering methodology, digital-twin edge resilience).

**No row has all ten columns.** No row has the combination {ACF, CAL, MNI, REPLAY}. Novelty gate: **PASS (conditional on completing rows 11-15).**

---

## 3. The two papers that nearly cost us the paper

### 3.1 AURORA — arXiv:2605.10718 (verified: title, authors, abstract, contributions read from the arXiv HTML)
De Silva, Lapkovskis, Saleh, Tarkoma, Donta. *An Uncertainty-Aware Resilience Micro-Agent for Causal Observability in the Computing Continuum.*

What it does: parallel micro-agents diagnose grey failures using the free-energy principle plus causal do-calculus over localized causal state-graphs restricted to each fault's Markov blanket; a **dual-gated execution mechanism** authorizes remediation only when causal confidence is high and predicted epistemic uncertainty is bounded, otherwise abstains and escalates to the fog tier. Reported: 0% destructive action rate, 62.0% repair accuracy, 3 ms MTTR, 65.9% abstention, 30,006 Monte-Carlo trials in a Python simulator.

Overlap with CSC: causal intervention reasoning (P1), uncertainty-gated execution (P2), abstention (P3). This is a real collision on three of five pillars.

Where CSC is genuinely different, and how to say it in the paper without sounding defensive:
1. **Selection rule.** AURORA maximizes recovery probability. CSC *minimizes intervention cost subject to* a conservative risk bound. These answer different questions: "what fixes it best" vs. "what is the least I can do to the running system and still be safe". Under a system where interventions are themselves disruptive (migration, throttling), the second is the operationally relevant one, and CSC must demonstrate that with the intervention-cost metric.
2. **Nature of the uncertainty.** Variational free energy is a model-internal quantity with no coverage semantics. CSC uses conformal/adaptive-conformal calibration and must *report empirical coverage against the nominal level* — including where it breaks under scenario shift. That is a falsifiable claim AURORA does not make.
3. **Evidence class.** AURORA's ground truth is a synthetic Monte-Carlo generator. CSC's is a running distributed Go system under kernel `netem` impairment, with alternative futures physically executed.
4. **Abstention must be cited, not claimed.** Any sentence resembling "we introduce abstention for self-healing" is now false. Correct phrasing: "Consistent with recent uncertainty-gated remediation [AURORA], CSC abstains rather than acting under high uncertainty; unlike [AURORA], the gate is defined on a calibrated risk bound and its coverage is measured."

Caveats to record: preprint, not peer-reviewed at time of writing; if it is still a preprint at submission, cite it as such. Its numbers are simulator numbers and are **not** comparable to CSC's — do not tabulate them side by side.

### 3.2 NeSy-Edge — arXiv:2603.21145 (verified from arXiv HTML)
Ye, Lapkovskis, Saleh, Zhang, Donta. *NeSy-Edge: Neuro-Symbolic Trustworthy Self-Healing in the Computing Continuum.*

Log-driven, edge-first: parses noisy runtime logs into structured events, builds a prior-constrained sparse symbolic causal graph, and combines causal evidence with retrieved troubleshooting knowledge for root-cause analysis and **recovery recommendation**. Evaluated on Loghub datasets (HDFS, OpenStack, Hadoop) under semantic noise; up to 75% RCA accuracy, 65% end-to-end, ~1500 MB local memory.

Overlap: causal graph + self-healing framing. **No** interventional comparison of candidate actions, no uncertainty quantification, no cost model, no execution on a live system, no counterfactual validation. This paper is a *diagnosis and recommendation* system; CSC is a *control* system. That distinction is clean and should be stated in one sentence in Related Work — recommendation ends where CSC begins.

### 3.3 The bigger risk than either paper
Both come from the **same group**, four months apart. That group is actively publishing into this exact space and will likely ship the next increment (cost-aware or calibrated variant) during our implementation window. Two implications, both non-negotiable:
- **Re-run this audit at implementation freeze and again at submission**, with an explicit check of new arXiv postings by Donta, Saleh, Lapkovskis, Tarkoma, Aral, Brandic.
- **Front-load P5 (fork-and-replay).** It is the one pillar a simulator-based competitor cannot cheaply copy, because it requires a deterministic executable environment. If the schedule slips, cut PPO or the GNN baseline before cutting replay.

---

## 4. Novelty-gate questions, answered for the top papers

For each of the 15 most relevant papers, answer: (Q1) predicts failures? (Q2) intervenes online? (Q3) estimates `P(Y|do(A=a))` for multiple candidate actions? (Q4) quantifies uncertainty? (Q5) can abstain? (Q6) optimizes minimum-necessary intervention? (Q7) validates counterfactual outcomes by deterministic replay/forking? (Q8) closes the loop on observed post-action outcomes?

Answered so far: rows 1-9 of the matrix above (Q3=partial only for AURORA; Q6 and Q7 are **no** for every paper examined; Q8 is **no** for every paper examined).

**Stop condition:** if any single publication is found answering yes to Q3+Q4+Q6+Q7 jointly, halt implementation and report the conflict rather than reframing around it.

---

## 5. Claims the paper may and may not make

Permitted (after the audit is completed to 15 rows):
- "To our knowledge, existing approaches do not jointly (i) rank multiple candidate interventions by calibrated interventional risk, (ii) select the cheapest action satisfying a risk constraint, and (iii) validate the resulting counterfactual ranking against executed alternative futures."
- "We provide experimental counterfactual ground truth by deterministic fork-and-replay."

Forbidden:
- "first causal self-healing framework for edge" — false.
- "first to use uncertainty gating / abstention in self-healing" — false, see AURORA.
- "first to apply conformal prediction at the edge" — false, see rows 6-9.
- any "for the first time" formulation not backed by this audit.

---

## 6. Open TODOs

- [ ] Fill matrix rows 11-15 (RL-based MEC recovery; GNN failure prediction in IoT; microservice RCA e.g. MicroRCA-class work; chaos engineering as methodology; digital-twin edge resilience).
- [ ] Locate and verify any prior use of environment forking for counterfactual evaluation in **systems** venues (NSDI/OSDI/SOSP/EuroSys) — currently searched and not found, but the search was not exhaustive.
- [ ] Verify whether AURORA is published (not just preprint) at submission time.
- [ ] Confirm no IoT-J paper in the last 12 months uses the term "counterfactual" for runtime intervention selection.
