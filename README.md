# Three Identifiability Limits in the Evaluation of Proactive Self-Healing

Reproducibility artifact for a study of what a counterfactual evaluation of
self-healing controllers can and cannot establish, built around
**Counterfactual Shadow Control** (CSC) as one evaluated method.

Most resilience mechanisms either react to a failure that already happened or
predict that one is likely. Neither tells you what a *specific* recovery action
would do to *this* system, or whether taking it is worth the disruption. The
machinery here makes that checkable: a reconstructible **fork-and-replay**
environment with exact, transport-quiescent anchors. From the same decision state
and deterministic input specification, every candidate action is executed in its
own branch while residual runtime nondeterminism is measured, so a predicted
ranking is scored against outcomes that were actually observed.

## What was found

Once those futures became measurable, three limits appeared, each declared before
it was tested:

1. **A degradation's onset and severity are not separately identifiable from
   cumulative counters.** A windowed observable removes this: a preregistered
   sign test goes from 13 failures in 203 contrasts to 0 in 187.
2. **The capacity of a path carrying no traffic is not identifiable from
   telemetry of the path in use.** The structural predictor reproduces 96 of 101
   resolvable signs, and every failure is a rerouting onto a target degraded
   unobservably. No instrumentation removes this; the quantity is unsampled
   rather than under-sampled.
3. **The resource cost of an action is not identifiable from container
   accounting dominated by idle work.** Recruiting a second node moves the
   measured figure by 0.0001.

Two consequences follow for the benchmark rather than for any method: on one
fault family a one-line reactive threshold attains the oracle bound, and on
another an ablation that never intervenes beats the calibrated controller, 0.955
against 0.900. **Both results are adverse to CSC and both are reported as
measured.** `RESULTS.md` has every number with its reading, including the ones
that tell against the method.

## Status

The experiments are run; the manuscript is under preparation for IEEE
Transactions on Network and Service Management. 8118 branches across three fault
mechanism families are reported, from a total of 14091 run.

**The manuscript itself is not in this repository.** Its prose, figures,
bibliography and supplement are not needed to reproduce anything here, and they
are the part that can be scooped before acceptance; they are added together with
the camera-ready version once the paper is accepted. What is here is everything
needed to re-run the work and check the numbers.

Archived release: [10.5281/zenodo.23165225](https://doi.org/10.5281/zenodo.23165225)

## Read these first

| File | What it settles |
|---|---|
| `RESULTS.md` | Every measured number with its reading, adverse results included |
| `EXPERIMENT_PROTOCOL.md` | Frozen constants, splits, seed pairing, exclusion policy, and the dated amendment log for every defect found and corrected |
| `RESEARCH_SPEC.md` | What the contribution is, and the adjacent literatures it is not |
| `NOVELTY_AUDIT.md` | What competing work already covers, and what survives |
| `ARCHITECTURE.md` | Go execution plane / Python intelligence plane and the boundary between them |

The amendment log is worth reading before the results. Several reported findings
exist because an earlier measurement was wrong in a way that was found and
documented rather than smoothed over, and two completed matrices are superseded
rather than reinterpreted for that reason.

## Layout

```
cmd/            Go services: device-sim, gateway, edge-agent, controller,
                fault-injector, replay-orchestrator
internal/       Go libraries: telemetry, routing, queue, workload, recovery,
                mobility, bus (with byte accounting), sysusage (cgroup CPU)
intelligence/   Python: models, causal (SCM), conformal, counterfactual,
                training, inference server, tests
experiments/    frozen configs, scenario generators, runners, run manifests
analysis/       objective, bands, leakage tests, accounting audit, fault check,
                cost sensitivity, table generators
tests/          fixtures for the fault check, admission limits, the gateway
                bound, the accounting audit end to end, and the cost term
scripts/        deploy, matrix runners, repository audit (148 guards)
data/raw/       append-only run output, never edited (not committed)
```

## Quick start

```bash
make build                  # Go services
make test                   # go test -race + pytest (intelligence, analysis, tests)
bash scripts/audit_repo.sh  # 148 invariants, each added after a real defect
docker compose up           # the whole system on one machine
```

`docker compose up` is the reproducibility contract.

## House rules

1. **No fabricated anything.** Results, references, DOIs, measurements. A missing
   number is `TODO`, never a plausible-looking placeholder.
2. **No manual numbers in the paper.** Values are generated by `analysis/` from
   the recorded runs. Where a table must be transcribed because its branch data
   is held on the analysis host, `paper/check_transcribed.py` asserts every
   figure in it against `RESULTS.md`, and figures with no provenance in this
   repository are listed rather than excused.
3. **Raw logs are append-only.** Processed data is derived by versioned scripts;
   `data/raw/` is never edited.
4. **Emulation is called emulation.** `link_quality` is an abstract [0,1] score,
   not a measured RF SINR. There is no physical radio, no RF measurement and no
   energy measurement anywhere in this work.
5. **A reference enters `references.bib` only after its bibliographic identity
   is verified at the source** and recorded in `docs/literature.csv`.
6. **A result against the method is reported in the same table as the rest.**
7. Never cut fork-and-replay.

## License

MIT. See `LICENSE`.
