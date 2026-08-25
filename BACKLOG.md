# BACKLOG.md

Ordered. Each phase has an exit criterion; a phase is not done until its criterion is demonstrably met. Phases 1–4 contain no machine learning at all, on purpose: if the environment is not deterministic and the replay does not reproduce, no amount of modelling saves the paper.

| # | Phase | Exit criterion | Status |
|---|---|---|---|
| 0 | Literature and novelty audit | NOVELTY_AUDIT.md matrix filled to 15 rows; no competitor covers {ACF, CAL, MNI, REPLAY} | **partial** — 10 rows, 5 pending |
| 1 | Repo scaffolding, specs, protobuf contract | `make build` succeeds; specs frozen | **in progress** |
| 2 | Go environment: device-sim, gateway, edge-agent, telemetry | 100 devices → 3 edges, end-to-end events flowing, telemetry recorded | todo |
| 3 | Fault engine F1–F7, YAML-configured, `tc`/`netem` + labelled fallback | every scenario reproduces its intended telemetry signature | todo |
| 4 | Determinism | same seed → byte-comparable workload and fault schedule; outcome dispersion measured | todo |
| 5 | **Fork-and-replay** | 5 branches from one state; §10 determinism band measured and narrow enough to resolve action differences | todo — **critical path, do not defer** |
| 6 | Baseline B1 (threshold) | closed loop runs end to end with a controller in it | todo |
| 7 | Telemetry dataset + splits + leakage tests | leakage test fails on a deliberately poisoned split | todo |
| 8 | Temporal predictor (GRU/TCN) | horizon Δ selected on validation, recorded | todo |
| 9 | Topology-informed SCM | `P(F\|S)` and `P(F\|S,do(a))` are distinct, logged, and differ | todo |
| 10 | Conformal calibration | empirical coverage measured against the 0.90 target on ID and OOD | todo |
| 11 | MNI selector + safety gate + abstention (Go) | selector provably never returns risk-argmin; abstention path exercised | todo |
| 12 | Closed-loop verification and drift tracking | predicted vs observed error recorded per intervention | todo |
| 13 | Baselines B2, B3, B5 | matched features and budgets, asserted in tests | todo |
| 14 | Baseline B4 (PPO) | trained under the declared budget | todo |
| 15 | Pilot (protocol §11) | methodological problems found and fixed; protocol → 1.0 | todo |
| 16 | Main experiments | ~700 runs (5+ controllers × 7 scenarios × 20 seeds), manifests complete | todo |
| 17 | Analysis, statistics, validation gate | `validate_results.py` passes; no manual numbers anywhere | todo |
| 18 | Ablations A1–A3 | todo | todo |
| 19 | Scalability 100 → 10k (25k if it holds) | overhead table and curve generated | todo |
| 20 | Figures 1–4 and Tables I–III, auto-generated | `make figures` reproduces every artifact from `results_long.csv` | todo |
| 21 | Paper draft (Results and Abstract written last) | 6.0 pages in IEEE two-column | todo |
| 22 | CLAIM_EVIDENCE.md audit | every claim maps to a table, figure, equation, or verified reference | todo |
| 23 | Re-run novelty audit | no new conflicting publication | todo |
| 24 | REVIEW_REPORT.md hostile self-review | zero fatal issues | todo |

## Rules that outrank the schedule

1. No fabricated results, references, DOIs, or measurements. A missing number is `TODO`, never a plausible-looking one.
2. No number in the Results section is typed by hand if it can be generated from data.
3. Raw experiment logs are append-only and never edited.
4. If the schedule slips, cut PPO or the GNN baseline. **Never cut fork-and-replay** — it is the contribution.
5. Prefer the simplest implementation that answers the research question. The goal is a defensible paper, not maximal software.
