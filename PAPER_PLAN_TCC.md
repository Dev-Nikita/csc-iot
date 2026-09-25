# Submission plan — IEEE Transactions on Cloud Computing

Decided 2026-09-26. Primary venue **IEEE TCC**, traditional (non-OA) route.
Fallback **IEEE TNSM**. No mobility-specific functionality is added, and the
work is not compressed to an 8-page limit.

## 1. Venue facts (checked, not assumed)

| | TCC |
|---|---|
| Regular paper pages included | 12 |
| Overlength charge | $220 per page |
| Voluntary page charge | $110 (optional, declined) |
| Open access | $2,045 — not taken |

Source: IEEE voluntary page and overlength article charges table,
`journals.ieeeauthorcenter.ieee.org`. TNSM appears in the same table at the
same voluntary rate; its regular-paper page allowance is not listed there and
must be re-checked from TNSM's own author information before any fallback
submission.

## 2. Venue fit — stated plainly

TCC is a cloud journal. This work is an edge/containerised-service study on a
single host. The contribution — deciding whether and how to intervene in a
degrading distributed service, and measuring whether the intervention helped —
belongs to service and resource management, which is squarely TNSM's subject
and only adjacent to TCC's.

Consequence for the writing, not for the claims: the paper is framed on the
cloud–edge continuum as **self-healing of a containerised service topology**,
and the following are never claimed:

- no geo-distribution, no multi-host placement, no multi-tenancy;
- no physical 5G/RF, no energy measurement, no hardware deployment;
- no mobility model, and none is added to chase a mobility venue.

Honest estimate: desk rejection on scope at TCC 0.15–0.25. Eventual acceptance
at TCC, conditional on the scope below being completed, 0.45–0.60, almost
certainly through major revision. With TNSM as fallback, eventual publication
~0.8. These are estimates, not forecasts of a specific decision.

## 3. Reduced-but-complete scope

The rule: everything the paper claims is implemented, exercised and measured.
Nothing is described as a mechanism unless a run shows it choosing something.

### In

| Element | Content |
|---|---|
| Actions | `NO_OP`, `REROUTE`, `THROTTLE`, `MIGRATE` — four, each with real state mutation and an acknowledged effect |
| Faults | three on the distributed stack: **D1** edge capacity degradation (exists), **D2** ingress impairment ramp on the device→gateway path, **D3** edge stall (service rate to zero for k epochs) |
| Predictor | action-conditioned `Ĵ(s,a)`; structural queue model vs learned model, compared head to head (B5) |
| Uncertainty | bootstrap ensemble, K = 10, giving a set of plausible `Ĵ` per action |
| Safety gate | Conformal Risk Control on the declared set-level monotone loss; `δ` fixed in advance; yields `τ̂` and `U_max` |
| Selector | Minimum-Necessary Intervention: cheapest admissible action, else guarded abstention outside the guarantee |
| Baselines | **B1** never intervene · **B2** reactive threshold after a violation · **B3** greedy predicted-best, no gate and no cost ordering · **B4** replay oracle — an upper bound that uses the reference outcomes and is labelled as not implementable online |
| Ablations | **A1** remove the CRC gate (point prediction) · **A2** remove the cost ordering (best predicted action regardless of cost) |
| Determinism audit | D0 on the frozen configuration |

### Out, and said so in the paper

`REPLICATE`; fault types beyond the three; multi-host and geo-distribution;
energy, RF and hardware measurement; mobility; the resource and bandwidth
components of the cost term, which stays reduced and declared as such.

### Repeats

N = 10 per cell. Justification is measured, not economised: on m2prime-903 the
`REROUTE` contrasts resolve with local SNR 10–19 and bootstrap CIs whose width
is ~0.01 in `J` units at N = 10. A larger N cannot change any conclusion, so
N = 15 or 30 would buy nothing and is not claimed as rigour.

## 4. Sequence, and what each step decides

1. **B5 — the gate on everything.** Does a learned `Ĵ(s,a)` beat the structural
   model out of sample? Uses the existing 900-branch dataset; no new runs.
   If it does not — and on a deterministic substrate with known structure that
   is a real possibility — the "learned prediction under uncertainty" framing
   does not survive, and the honest paper is about the structural model plus
   the calibrated gate. Deciding this before building months of pipeline is the
   whole point of doing it first.
2. `MIGRATE` with real side effects; D2 and D3 faults; one matrix per fault.
3. One budget calibration run. The budget is a property of the healthy system,
   which does not depend on which fault will later occur, so a single
   calibration covers all three faults — restated here so it is a declared
   decision rather than an omission.
4. CRC calibration, MNI selector, closed loop: controller vs B1–B4 vs A1–A2.
5. D0 audit on the frozen configuration.
6. Results, abstract and conclusion written only from validated artifacts.

## 5. What a reviewer will attack, and the answer

| Objection | Answer |
|---|---|
| Single host, so not cloud | Stated as a limitation in the paper, not defended. The claim is about the decision procedure and its measurement, both of which are substrate-independent; the substrate is declared as containerised emulation with kernel netem. |
| Replay is not counterfactual ground truth | It is never called that. Replay produces empirical reference outcomes on a reconstructed prefix, with the reconstruction verified by structural fingerprint and transport quiescence. |
| The objective is reduced | Declared in the text and in every table caption: `J_obs` carries failure, latency and disruption; resource and bandwidth are not instrumented. |
| Effects are small relative to replay noise | Reported under four bands — pooled (preregistered), worst cell, contrast-local, and bootstrap — with the set that survives all four named separately. |
| Results tuned to the conclusion | Three superseded runs, their defects and their dated amendments are in the protocol's amendment log, which is part of the artifact. The gate was fixed before the data and never moved. |
