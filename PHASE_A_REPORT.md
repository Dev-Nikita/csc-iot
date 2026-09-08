# PHASE_A_REPORT.md

Phase A of `BACKLOG.md`, run 2026-08-25. No machine learning was written, and
none may be before the replay and D0 gates pass.

---

## What was built, and what was not

**Built.** The determinism substrate and an executable closed loop: experiment
clock, per-component RNG streams, deterministic workload and mobility, F1 and F2
fault schedules, a real routing table and rate limiter, a reactive threshold
controller, JSONL telemetry and decision logs, and run manifests with a
wall-clock-independent reproducibility digest.

**Not built, and not implied.** This is an **in-process discrete-time
emulation**. There is no NATS, no gRPC between planes, no containers and no
kernel `netem` yet. Every run it produces is stamped
`impairment_mode = application_layer`, which by the frozen protocol means such
runs are labelled and never mixed into reported comparisons. The distributed
deployment in `ARCHITECTURE.md` is the next increment, not something this
report claims to have delivered.

That split is deliberate. The critical path is replay and D0, and both depend on
the determinism substrate rather than on the transport. Standing up NATS and
netem first would have delayed the one question that can still kill the
contribution.

## Acceptance

```bash
make build            # go build ./...
make test             # go test -race ./... && pytest intelligence/tests
make determinism      # the same-seed gate, verbose
make experiment-smoke # 100 devices, F1, threshold controller, then a rerun
```

Observed on the build host (linux/amd64, Go 1.24.7, 2 CPUs):

```
run F1-B1_threshold-seed042  scenario=F1 devices=100 impairment=application_layer
  events sent=29150 delivered=25604 retries=3202 sla_violation_ticks=515
  determinism sha256=b3cd105e925d6322
  manifest experiments/manifests/F1-B1_threshold-seed042.json
```

Rerun at the same seed, separate output directory: `determinism sha256=b3cd105e925d6322` — identical.
Seed 43: `ebaa3b680d2bec33` — different, as it must be.
Scenario F2 at seed 42: `events sent=29150`, `retries=0` — the workload is bit-identical across scenarios while the fault schedule is not, which is the stream-independence property the design exists to provide.

Wall-clock time (~75 ms per 75 s run at 100 devices) is far below real time, so the emulation is not rate-limited by the tick loop at this scale.

## Tests

`go test -race ./...` — all pass. `internal/rng` 4 tests, `internal/routing` 3, `internal/sim` 5.
`pytest intelligence/tests` — 6 tests for the CRC threshold rule, including an empirical check that the guarantee holds on held-out runs.

The tests that earn their place:

- **`TestStreamsAreIndependent`** burns 1000 mobility draws and asserts the fault stream is untouched. This is the property whose silent violation would invalidate every replay taken before the offending refactor.
- **`TestSameSeedReproducesRun`** compares the full decision log, wall clock excluded. It failed on first run and found a real defect (below).
- **`TestRerouteChangesRealState`** and the throttle bounds tests assert that actions mutate the routing table and the rate limiter, not a latency variable.
- **`test_correction_is_material_at_realistic_n`** pins the CRC finite-sample correction at ≈0.048 for `n=20`, so it cannot quietly shrink to nothing.

## Defects found by running it

1. **Wall clock leaked into the reproducibility digest.** The first determinism
   test failed because `telemetry.jsonl` and `decisions.jsonl` carry
   `wall_nanos`, which legitimately differs between runs. Hashing the file
   verbatim would have failed on every run and trained us to ignore the check.
   Fixed by `experiment.DeterminismDigest`, which strips named keys at every
   nesting level before hashing; the manifest now records both the raw hash
   (integrity) and the determinism digest (reproducibility).
2. **Package-level mutable state.** Action history was a package-level slice,
   shared across engines in one process — two runs in the same process would
   have contaminated each other's state ids. Moved onto the engine.
3. **Warm-up transients counted as SLA violations.** Delivery ratio was
   cumulative from `t=0`, so it never recovered from the initial queue fill and
   every run reported a violation from the first tick. Both the ratio and the
   violation counter are now confined to the measurement window. This changed
   the smoke run from 662 to 515 violation ticks — it would have inflated the
   failure count in every run and every controller equally, which is exactly the
   kind of bias that survives review because it looks consistent.

## Known nondeterminism and limitations

- Wall-clock timestamps are recorded and excluded from the digest by design.
- Everything else is currently reproducible bit-for-bit, because the loop is
  single-process and single-threaded. **This will not survive the move to real
  processes over NATS**, and that is precisely why `η_J` must be measured on the
  distributed system rather than on this core. A small `η_J` here proves nothing
  about the deployment; do not report one.
- `MIGRATE` and `REPLICATE` are not implemented. They arrive after replay is
  stable, with state-transfer and cold-start costs modelled.
- The threshold controller never released a throttle: it fired 92 times and
  mutated state once, because it re-issued the same factor to the same gateway.
  Fixed with hysteresis before the comparative pilot — a baseline that can enter
  a mitigation but not leave it is not a fair comparison.
- `linkQuality` is an abstract `[0,1]` score. It is not a measured radio SINR
  anywhere in the code, the logs or the manuscript.

## Files added

```
go.mod
cmd/csc-sim/main.go
internal/clock/clock.go                 experiment clock: experiment_nanos, seq, wall
internal/rng/streams.go  (+test)        seed_i = SHA256(master ‖ component ‖ instance)
internal/config/config.go               run config + content hash + validation
internal/faults/faults.go               F1, F2 as pure functions of experiment time
internal/routing/routing.go (+test)     routing table + rate limiters — real action targets
internal/telemetry/telemetry.go         JSONL samples and decisions
internal/experiment/manifest.go         manifest + FileSHA256 + DeterminismDigest
internal/sim/sim.go      (+test)        devices, gateways, edges, tick loop, state ids
internal/control/threshold.go           B1 reactive baseline
intelligence/conformal/crc.py (+test)   finite-sample CRC threshold rule
```

## Next

**M2 — replay.** Reconstruct a run prefix and re-execute one anchor under
`NO_OP`, `REROUTE`, `THROTTLE`. Acceptance: the three branches produce genuinely
different queue depth, latency, SLA outcome and cost. If they differ only in a
cosmetic variable, stop and fix the model before going further.

**M3 — D0.** Three actions first; add `MIGRATE` and `REPLICATE` only once `η_J`
is small and branches are distinguishable. Then the full 20 × 5 × 30.

**Not next: the GRU.** Dataset construction begins after D0, not before.
