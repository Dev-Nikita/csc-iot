# BACKLOG.md

Ordered. Each phase has an exit criterion; a phase is not done until its criterion is demonstrably met. Phases 1–4 contain no machine learning at all, on purpose: if the environment is not deterministic and the replay does not reproduce, no amount of modelling saves the paper.

| # | Phase | Exit criterion | Status |
|---|---|---|---|
| 0 | Literature and novelty audit | 15/15 matrix rows; no competitor covers {ACF, CAL, MNI, REPLAY} | **done** |
| 1 | Repo scaffolding, specs, protobuf contract | specs frozen; document compiles | **done** |
| 1b | **Methodology correction pass** | risk-control layer valid; notation, objectives, metrics, splits, hypotheses corrected; protocol v2 frozen | **done** |
| 2 | **A0** — deterministic execution core: experiment clock, per-component RNG streams, device-sim, gateway, 3 edge agents, telemetry, manifests, threshold controller, F1–F2 | `make experiment-smoke` passes; same seed reproduces the run | **done** — in-process only, see `PHASE_A_REPORT.md` |
| 3 | **M2** — replay mechanics on the deterministic core | prefix reconstruction, `sid`/`bid` hashes, action-dependent branch divergence, every non-`NO_OP` action mutates runtime state | **done** — `M2_REPLAY_REPORT.md` |
| 4 | **A1** — distributed substrate: NATS, separate gateway/edge/controller processes, typed RPC boundary, Docker Compose, privileged `tc`/`netem` | smoke passes with device→gateway egress `impairment_mode = kernel_netem` | code complete; **repeat validation after qdisc-direction correction** |
| 4b | **M2′** — repeat replay over the distributed substrate | logical prefix equivalence holds under concurrency; branch divergence survives real transport; ≥30 anchors across pre-fault, transition and degraded regions, 10 repeats per action | todo — **the real test of the contribution** |
| 4b2 | **D0-lite** — 10 anchors × 3 actions × 20 repeats on A1 | provisional `η_J`; preregistered `SNR_J ≥ 3`; full frozen `J_obs` (failure, latency, cost), never the M2 throughput diagnostic | todo |
| 4c | **D0 (full)** — determinism audit, on A1 only, after `MIGRATE`/`REPLICATE` | 20 anchors × 5 actions × 30 repeats; `η_J` measured and frozen; usability gate passes | todo — **hard gate. Any `η_J` measured on A0 is a development diagnostic and must never be reported** |
| 5 | Actions with real side effects | `NO_OP`, `REROUTE`, `THROTTLE` first (deterministic); `MIGRATE`, `REPLICATE` after replay is stable, with their state-transfer and cold-start costs modelled rather than subtracted from latency | todo |
| 6 | Fault engine F3–F7, YAML-configured | each scenario reproduces its intended telemetry signature | todo |
| 7 | Telemetry dataset, splits, leakage tests, exhaustive interventional branches at training anchors | leakage test fails on a deliberately poisoned split; every training anchor carries a branch per action with `state_mutated` recorded | todo |
| 8 | Temporal predictor (GRU first) | horizon Δ selected on validation, recorded | todo |
| 9 | Dynamic SCM: `X_{j,t+1} = g_j(Pa_j, A_t, u)` per-mechanism GAM/GBM | rollout produces `P(F\|do(a))` distinct from `P(F\|S)`, logged separately | todo |
| 10 | Counterfactual evaluator: `do(a)` + H-step rollout for all five actions | per-action risk, latency and cost returned within the decision deadline | todo |
| 11 | Conformal risk control on the set-level loss | `τ̂` calibrated; realised risk measured against `δ` on ID and shift | todo |
| 12 | MNI selector + gate + abstention (Go) | selector provably never returns `argmin R̂`; abstention path exercised | todo |
| 13 | Closed-loop verification and drift tracking | predicted vs observed recorded per intervention | todo |
| 14 | Baselines B2, B3, B5 | matched features and budgets, asserted in tests; B5 is the action-conditioned associative predictor | todo |
| 15 | Baseline B4 (PPO) with pre-declared reward | trained under the declared budget; no replay outcomes visible to it | todo |
| 16 | Pilot | methodological problems found and fixed; protocol → 1.0; 100 ms p95 budget checked against the tick | todo |
| 17 | Main experiments | 6 controllers × 7 scenarios × 20 seeds ≈ 840 runs, plus ablations, branches, D0, scale | todo |
| 18 | Analysis, statistics, validation gate | `validate_results.py` passes; TOST/non-inferiority for H3; no manual numbers | todo |
| 19 | Ablations A1–A3 | | todo |
| 20 | Scalability 100 → 10k (25k only if it holds) | p95 decision latency, deadline misses, CPU, RAM | todo |
| 21 | Figures 3–4 and Table III, auto-generated | `make figures` reproduces every artifact from `results_long.csv` | todo |
| 22 | Optional F8: trace-driven external validity | public 5G measurement trace replayed as a bandwidth/loss/handover schedule. Describe as **trace-driven emulation using measurements from a production 5G network** — never as "evaluated on a 5G network" | optional |
| 23 | Paper: Results and Abstract written last | ≤6.3 pages after final compression | todo |
| 24 | `CLAIM_EVIDENCE.md` audit | every claim maps to a table, figure, equation, or verified reference | todo |
| 25 | Re-run novelty audit | no new conflicting publication | todo |
| 26 | `REVIEW_REPORT.md` hostile self-review | zero fatal issues | todo |

## Rules that outrank the schedule

1. No fabricated results, references, DOIs, or measurements. A missing number is `TODO`, never a plausible-looking one.
2. No number in the Results section is typed by hand if it can be generated from data.
3. Raw experiment logs are append-only and never edited.
4. If the schedule slips, cut PPO or the GNN baseline. **Never cut fork-and-replay** — it is the contribution.
5. Recovery actions must have real side effects. `REROUTE` changes the gateway-to-edge routing table; `MIGRATE` changes service placement and pays a transfer delay; `THROTTLE` changes the source rate; `REPLICATE` starts a second instance and changes routing capacity. Subtracting a constant from a latency variable is simulation wearing a system's clothes, and a reviewer will find it.
6. No machine learning is written before A1 exists and D0 has frozen `η_J` on it. A model trained against a reference the environment cannot resolve is not evidence.
7. `η_J` measured on the in-process core is a development diagnostic. It never enters the paper. The reportable value comes from replay over the distributed substrate.
8. A baseline is never left deliberately weak. B1 got a release rule the moment the run showed it could throttle but not recover. A model trained against a reference the environment cannot resolve is not evidence.
5. Prefer the simplest implementation that answers the research question. The goal is a defensible paper, not maximal software.
