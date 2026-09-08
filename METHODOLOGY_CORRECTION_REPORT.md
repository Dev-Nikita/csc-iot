# METHODOLOGY_CORRECTION_REPORT.md

Correction pass run before implementation, 2026-08-25, in response to external
review of the first full draft. Implementation of Phase 2 was held until this
was complete.

Twelve issues. One was potentially fatal, three were serious, the rest were
defects that would have cost credibility in review. Every correction below is
implemented in the files listed, not merely noted.

---

## C1 — Proposition 1 was not valid (fatal)

**Issue.** The draft formed `R⁺(a|S) = R(a|S) + q̂_{1−α}` and asserted
`P[R(a*) > R_safe] ≤ α`, citing split conformal coverage.

The inequality does not follow, for two independent reasons.

1. **The conformalised quantity is latent.** Split conformal prediction gives
   coverage for an *observable* `Y`. Here `R(a|S) = P(F = 1 | S, do(a))` is a
   conditional probability that is never observed. A replayed branch yields
   `Y^a ∈ {0,1}`, not `R(a|S)`, so the residual `R − R̂` that the construction
   needs does not exist as a measurable quantity. Adding a residual quantile to
   a predicted probability and calling the result an upper bound on a latent
   probability is not a conformal argument.
2. **The selection effect.** Even granting per-action marginal coverage, the
   controller inspects all five bounds and *then* selects. Marginal coverage
   for each `a` separately does not transfer to the adaptively chosen `a*`. A
   union bound at `α/|A|` would restore it formally but is badly conservative
   for a binary outcome with five actions.

**Correction.** The bound is removed. Proposition 1 and its proof are deleted
from the manuscript. The gate itself is calibrated instead, by **conformal risk
control** (Angelopoulos et al., arXiv:2208.02814, verified). Define the
admissible set and a **set-level** loss:

```
A_safe(τ)  = { a : R̂(a|S_t) ≤ τ  ∧  Û(a) ≤ U_max }
ℓ_t(τ)     = 1[ ∃ a ∈ A_safe(τ) : Y^a_t = 1 ]
```

and calibrate `τ̂` so that `E[ℓ(τ̂)] ≤ δ`.

Why this is the right object, and not a cosmetic substitution:

- `ℓ` is **bounded and non-decreasing in τ** — relaxing the threshold can only
  enlarge `A_safe` — which is exactly the monotonicity CRC requires. The
  original construction had no such structure.
- `ℓ` is **observable**. `Y^a_t` is what a replay branch produces. The
  calibration target is now a quantity the testbed actually measures.
- `ℓ` constrains the **whole admissible set**, so it bounds the failure
  probability of *whatever rule selects from that set* — including the
  cost-minimising rule. This dissolves the selection effect rather than
  papering over it, and it is stronger than a per-action statement.

Note what this makes visible: the risk-control layer is only implementable
*because* fork-and-replay exists. The two contributions are not independent —
the replay branches supply the `Y^a` that the calibration consumes. That
connection is now stated in the manuscript.

**Claimed.** `E[ℓ(τ̂)] ≤ δ` under exchangeability of calibration and deployment
decision points, with the finite-sample statement of the cited work.
**Not claimed.** Any per-decision statement about the latent `R(a|S_t)`. Under
scenario shift, exchangeability fails by construction and the guarantee is
replaced by *measured* empirical risk, reported against the nominal `δ`.

**Files.** `main.tex` §III-E (rewritten, theorem environment removed),
`RESEARCH_SPEC.md` §6.5, `EXPERIMENT_PROTOCOL.md` §2,
`experiments/configs/calibration.yaml`, `references.bib`.

---

## C2 — `α` denoted two unrelated quantities (serious)

**Issue.** `α` was the conformal miscoverage level in §III and the failure
weight in `J(a) = αR + βL + γC` in §IV.

**Correction.** One symbol, one meaning, enforced by a notation table in the
protocol:

| was | is | meaning |
|---|---|---|
| `α` (conformal) | `δ` | risk-control level |
| `R_safe` | `τ̂` | calibrated admissibility threshold |
| `α, β, γ` | `λ_F, λ_L, λ_C` | objective weights |
| (absent) | `η_J` | replay dispersion band |

**Files.** `main.tex`, `EXPERIMENT_PROTOCOL.md` §1,
`experiments/configs/objective.yaml`, `figures/fig1_concept.tex`,
`figures/fig2_architecture.tex`.

---

## C3 — the replay reference objective contained the model's own prediction (serious)

**Issue.** `J(a) = αR(a) + βL(a) + γC(a)` was used both as the controller's
ranking and as the replay reference. If `R(a)` is the model-predicted risk, the
"reference" ranking contains the prediction it exists to test, and CRA measures
the model against itself.

**Correction.** Two named, structurally different quantities:

```
Ĵ(a)     = λ_F·R̂(a)  + λ_L·L̂(a)       + λ_C·Ĉ(a)          model output
J_obs(a) = λ_F·Y^a   + λ_L·L̃^a        + λ_C·C_obs^a        replay outcomes only
```

`J_obs` contains no model output — `Y^a` is the realised failure indicator,
`L̃^a` the realised normalised latency, `C_obs^a` the realised cost. CRA and
regret are computed against `J_obs`. `analysis/metrics.py` builds `J_obs` from
branch records exclusively, and the fields it reads are disjoint from any
prediction field.

**Files.** `main.tex` §IV-C, `RESEARCH_SPEC.md` §7,
`experiments/configs/objective.yaml`, `analysis/metrics.py`.

---

## C4 — "counterfactual ground truth" overclaimed (serious)

**Issue.** The phrase asserts access to true alternative outcomes in a
concurrent distributed system, which the manuscript elsewhere honestly admits
it does not have.

**Correction.** The term is **replay-based empirical reference outcomes**
throughout. The residual nondeterminism is not a caveat in prose, it is a
measured number, `η_J`, and every comparison is resolved at that resolution.

**Files.** `main.tex` (all occurrences), `RESEARCH_SPEC.md`,
`EXPERIMENT_PROTOCOL.md`, `README.md`, `BACKLOG.md`.

---

## C5 — determinism validation was unaffordable and unformalised

**Issue.** ≥30 replays of *every* state and action would dominate the compute
budget, and "differences smaller than the dispersion band are not interpreted"
was never given a formula or a threshold.

**Correction.** A one-off audit **D0** — 20 anchors × 5 actions × 30 identical
repeats = 3000 branches — estimates

```
η_J = Q_0.95( | J_obs,ri(a) − J_obs,rj(a) | )   over repeats of the SAME anchor and action
```

`η_J` is frozen at the end of D0 and then decides three things: what counts as a
tie, what counts as a harmful intervention, and how many repeats each
main-experiment branch needs (default 3, revised from measured variance).
`analysis/d0_audit.py` also applies a **usability gate**: if the median
between-action spread is not at least twice `η_J`, it exits non-zero and the
project returns to the determinism phase rather than reporting comparisons the
environment cannot resolve. `analysis/metrics.py` refuses to run at all if
`d0_audit.json` is absent — it will not substitute a default.

**Files.** `analysis/d0_audit.py` (new), `analysis/metrics.py`,
`EXPERIMENT_PROTOCOL.md` §10, `experiments/configs/runs.yaml`.

---

## C6 — exact-argmin CRA punished the controller for unresolvable choices

**Correction.** Tie-aware metrics:

```
CRA_η   = (1/|T|) Σ 1[ J_obs(a*) ≤ min_a J_obs(a) + η_J ]
Reg_η   = max( 0, J_obs(a*) − min_a J_obs(a) − η_J )
```

CRA@2 is retained as a secondary measure.

**Files.** `main.tex` (13)–(14), `analysis/metrics.py`.

---

## C7 — PFR and WIR were verbal, not defined

**Correction.** `N_pre` counts decision points where the no-action branch failed
**and some alternative branch did not** — failures no available action could
have averted are excluded from the denominator, so no controller is penalised
for the unavoidable. `N_prev` counts those where the no-action branch failed and
the executed action's branch did not. `N_harm` counts interventions whose branch
objective exceeds the no-action branch by more than `η_J`. Then
`PFR = N_prev/N_pre`, `WIR = N_harm/N_int`.

**Files.** `main.tex` (15), `analysis/metrics.py`.

---

## C8 — H3 asserted equivalence from a non-significant difference

**Issue.** "No significant availability regression" is not evidence of
equivalence; it is equally consistent with an underpowered comparison.

**Correction.** H3 is a **one-sided non-inferiority** claim against a margin
`Δ_A = 0.005` fixed before the main runs:

```
H0 : A_MNI − A_riskmin ≤ −Δ_A       H1 : A_MNI − A_riskmin > −Δ_A
```

implemented in `analysis/statistics.py::noninferiority` with a bootstrap
one-sided lower bound and a paired test, TOST reported alongside. The protocol
states explicitly what may be written if H1 is *not* accepted.

**Files.** `RESEARCH_SPEC.md` §4, `EXPERIMENT_PROTOCOL.md` §9,
`analysis/statistics.py`, `experiments/configs/objective.yaml`.

---

## C9 — H4 used the median

**Correction.** `p95(T_dec) < 100 ms` up to 10,000 devices with a deadline-miss
rate below 1%. The 100 ms figure is checked against the 500 ms controller tick
and 100 ms telemetry period during the pilot before being frozen.

**Files.** `RESEARCH_SPEC.md` §4, `EXPERIMENT_PROTOCOL.md` §9,
`experiments/configs/runs.yaml`, `main.tex` §IV-D.

---

## C10 — the F6 split contradicted itself

**Issue.** Table II listed F6 as an ID test scenario; the text drew ID data from
F1–F4 *and* F6.

**Correction.** Resolved as: train/validation/calibration from F1–F4 on disjoint
seed blocks; ID test from F1–F4 with **new parameter values as well as new
seeds** (otherwise the ID test measures only seed variance); F5, F6, F7 and
combined faults held out entirely as scenario shift.

**Files.** `EXPERIMENT_PROTOCOL.md` §3 and §6, `table_scenarios.tex`,
`main.tex` §IV-D.

---

## C11 — B5 was too weak to carry its role

**Issue.** "Scores actions observationally" was underspecified, and B5 is the
baseline that decides whether the causal layer earns its place.

**Correction.** B5 estimates `P̂(F_{t+Δ} | S_t, A_t = a)` with the action as an
ordinary predictor input, trained on the same records as CSC (including the
randomised-action records of C12), with no structural intervention. If it ranks
as well as CSC, the SCM is decoration — and that is stated in the protocol
before the experiments, so a null result must be reported.

**Files.** `EXPERIMENT_PROTOCOL.md` §4, `main.tex` §IV-B.

---

## C12 — the SCM was a static picture, and identification rested on observational assignment alone

**Correction, two parts.**

*Dynamic.* `X_{j,t+1} = g_j(Pa_j(X_t), A_t, u_{j,t})`, with counterfactual
evaluation rolling the model forward `H = Δ/tick` steps under `do(A_t = a)` and
averaging over sampled noise. Which mechanism each action replaces is documented
per action — reroute replaces the gateway-to-edge assignment in `g_LinkQ` and
`g_Loss`, migration the placement term in `g_ProcTime`, throttling the source
term in `g_EvRate`, replication the capacity term in `g_Queue`. Each `g_j` is a
GAM or gradient-boosted model, not a large network: interpretability is worth
more here than capacity.

*Randomised.* On training scenarios only, at a declared fraction of eligible
decision points, the action is drawn from a logged behaviour policy
`π_b(a|S_t)` with the propensity stored per record. Mechanisms are then fitted
partly from randomised rather than purely observational assignment, which
weakens — but does not remove — the no-unmeasured-confounding assumption.
Randomisation is disabled above a risk threshold and never enabled on test or
shift scenarios.

**Files.** `main.tex` (3)–(5), `RESEARCH_SPEC.md` §6,
`EXPERIMENT_PROTOCOL.md` §6a, `experiments/configs/behaviour_policy.yaml`.

---

## Literature

| Reference | Action | Status |
|---|---|---|
| Lindemann et al., *Formal Verification and Control With Conformal Prediction* | arXiv entry **replaced** by IEEE Control Systems 45(6):72–122, 2025, DOI 10.1109/MCS.2025.3611545 | verified (OpenAlex) |
| Angelopoulos et al., *Conformal Risk Control* | **added** — the basis of the corrected gate | verified preprint (arXiv:2208.02814); ICLR 2024 proceedings record not yet confirmed |
| García & Fernández, *Safe Reinforcement Learning* | **added** — cited where CSC contrasts explicit constraints with scalarised returns | verified (dblp) |
| 2026 SLR on AI-driven self-healing across the edge–cloud continuum | **not added** | PENDING — publisher page robots-blocked and OpenAlex rate-limited during the audit. Genuinely valuable if it holds, since a reported validation gap for AI repairs in nondeterministic runtimes is direct support for fork-and-replay. Must be read at source first |
| Raca et al., 5G measurement dataset | **not added** | PENDING — needed only if optional scenario F8 is built |
| Barber et al., *Conformal prediction beyond exchangeability* | **not added** | PENDING — would let the shift discussion be rigorous rather than only empirical |

Bibliography: 19 entries, all cited, all verified at source. AURORA and NeSy-Edge
remain explicitly labelled as preprints.

---

## Implementation order, changed

Fork-and-replay moved from phase 5 to **phase 3**, and the D0 audit is phase 4 —
both before any machine learning. Two hard gates now exist: `make
experiment-smoke` must pass before a line of Python ML is written, and `η_J` must
be frozen and pass the usability check before a model is trained. Actions are
built in two waves — `NO_OP`, `REROUTE`, `THROTTLE` first because they are
straightforwardly deterministic, then `MIGRATE` and `REPLICATE` with their
state-transfer and cold-start costs modelled rather than subtracted from a
latency variable.

---

## Unresolved risks

1. **CRC monotonicity holds for the set-level loss, not for a policy loss.** The
   guarantee covers "the admissible set contains a failing action". A loss
   defined directly on the selected action would not be monotone in `τ`, because
   a cheaper admitted action can fail where a costlier one would not. The
   set-level formulation is the correct one, but it is *conservative*: it
   charges the gate for a failing action even when the cost rule would never
   have chosen it. Expect a reviewer to notice, and say so first.
2. **`δ` is set to 0.10 before any data exist.** If the achievable risk is far
   below it the gate will be slack and MNI will look better than it is; if far
   above, abstention will dominate. The pilot must sanity-check `δ` before the
   protocol is frozen at 1.0, and any change must be logged as an amendment.
3. **`η_J` is unknown.** The whole replay contribution rests on it being small
   relative to between-action spread. This is a genuine empirical risk with a
   real chance of failure, and the D0 gate exists so that it fails loudly and
   early rather than quietly in the Results.
4. **The 2026 SLR is unverified.** It is the single most useful piece of
   supporting literature found in this pass and it is not yet citable.
5. **Page budget.** With the corrected mathematics the pre-results manuscript
   measures ≈6.6–6.7 pages against a 6.3 target. The remaining levers are listed
   in `paper/PAGE_BUDGET.md`; none should be pulled before the Results section
   exists.
