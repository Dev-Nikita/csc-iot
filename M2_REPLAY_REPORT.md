# M2_REPLAY_REPORT.md

Replay mechanics on the deterministic core, 2026-08-25.

**Read this first.** Every number below was produced by the **in-process**
execution core. There is no NATS, no gRPC, no containers and no kernel `netem`
yet. These are development diagnostics. **None of them may become the paper's
`η_J`**, which must be measured after the distributed substrate exists — that is
where concurrent scheduling and real transport introduce the noise this core
does not have.

---

## Mechanism

At a decision anchor the run is rebuilt from its own inputs — master seed,
per-component RNG streams, configuration hash, workload and fault schedules, and
the action history before the anchor — and re-executed with only the action *at*
the anchor replaced. Nothing is restored from a snapshot: congestion windows,
goroutine schedules and in-flight state are not capturable, and reconstruction
is the only claim this system can honestly make.

After the anchor the controller is **silent**. Any later divergence between
branches is therefore a consequence of the one intervention, not of a controller
reacting differently to it.

Anchors persist `state_id = SHA256(config ‖ seed ‖ tick ‖ action history)`,
alongside workload- and fault-schedule hashes and the stream list. Branches are
`branch_id = SHA256(state_id ‖ action ‖ repetition)`.

## Results — F1, seed 42, 100 devices, horizon 6 s

| anchor | action | mutated | q final | q max | p50 ms | p99 ms | retries | SLA fail |
|---:|---|:--:|---:|---:|---:|---:|---:|:--:|
| 60 | NO_OP | ✓ | 422 | 422 | 565.0 | 894.2 | 1364 | **yes** |
| 60 | REROUTE | ✓ | 9 | 90 | 37.9 | 202.5 | 1364 | no |
| 60 | THROTTLE | ✓ | 271 | 271 | 398.3 | 579.6 | 1342 | **yes** |
| 70 | NO_OP | ✓ | 11 | 33 | 44.2 | 83.8 | 1704 | no |
| 70 | REROUTE | ✓ | 349 | 349 | 427.5 | 742.1 | 1704 | **yes** |
| 70 | THROTTLE | ✓ | 14 | 38 | 44.2 | 94.2 | 1677 | no |
| 90 | NO_OP | ✓ | 0 | 25 | 35.8 | 67.1 | 2321 | no |
| 90 | REROUTE | ✓ | 361 | 361 | 479.6 | 767.1 | 2321 | **yes** |
| 90 | THROTTLE | ✓ | 0 | 23 | 33.8 | 62.9 | 2285 | no |
| 120 | NO_OP | ✓ | 76 | 79 | 140.0 | 179.6 | 3289 | no |
| 120 | REROUTE | ✓ | 403 | 403 | 462.9 | 854.6 | 3289 | **yes** |
| 120 | THROTTLE | ✓ | 74 | 75 | 140.0 | 171.2 | 3257 | no |

Ten anchors × three actions × two repetitions = 60 branches, full trace in
`data/raw/replay/branches.jsonl`.

**Acceptance: all ten anchors show action-dependent branch divergence**, and
every non-`NO_OP` branch mutated runtime state (`state_mutated` true in 40/40;
`NO_OP` executes and mutates nothing, which is its correct outcome). Repetition
pairs are identical in 30/30 comparisons — as expected in a single-threaded
core, and as *not* expected once the substrate is distributed.

**"Divergence", not "distinguishability".** The latter is a claim relative to the
dispersion band `η_J`: `|J(a_i) − J(a_j)| > η_J`. `η_J` does not exist yet, and
will not until D0 runs on the distributed substrate. Using the statistical word
now would quietly borrow a conclusion this milestone has not earned.

## What the branches actually say

The structure the metrics need is present, and it is not the structure one would
have guessed:

- **One anchor (60) where the no-action branch fails and some action avoids the
  failure.** That makes it a *preventable-failure opportunity*, so it belongs to
  the common PFR **denominator**. It enters a controller's PFR numerator only if
  that controller actually selects an action whose branch avoids the failure —
  and no controller under evaluation exists yet.
- **Nine *candidate-action* branches that caused a failure the no-action branch
  avoided.** These are potentially harmful outcomes available at those anchors.
  They contribute to a controller's WIR only when that controller selects them;
  charging a controller for an action it never chose would be meaningless.

In this configuration `REROUTE` is usually the *wrong* move: it shifts a gateway
onto another edge and creates the imbalance it was meant to relieve, while
`THROTTLE` yields small improvements at a fraction of the disruption.

What this does and does not support. It does **not** demonstrate
minimum-necessary intervention — H3 is settled by the A2 comparison and nothing
else, and the data here in fact cuts across the easy story: at anchor 60 both
`NO_OP` and `THROTTLE` fail while `REROUTE` succeeds, so the minimum *sufficient*
action there is the aggressive one; at anchors 70–150 the no-action branch is
already safe, and with `C(NO_OP) = 0` a minimum-necessary rule should do nothing
at all. What the data does support is narrower and still useful: **the same
action helps in one state and harms in another, and doing nothing must remain a
first-class candidate.** That is the premise state-conditioned intervention
selection rests on. It is an observation on a development core, not a result.

## Defects M2 found

1. **The baseline was saturated before any fault.** Two gateways round-robin
   onto three edges left `edge02` idle, so the smoke topology ran at **1.25×**
   capacity from `t = 0`. Every branch failed its SLA and most anchors were
   insensitive to the action under test — the signal was drowned by a
   configuration error, not by nondeterminism. Fixed to three gateways;
   utilisation is now 0.83 at baseline and crosses 1.0 as F1 retries accumulate,
   which is the scenario shape F1 was meant to have.
2. **`REROUTE` could be a silent no-op.** The policy picked the least-loaded
   edge, which was sometimes the edge already in use, producing a branch
   identical to `NO_OP` while being counted as a distinct alternative. That
   would inflate apparent agreement between actions in D0. Reroute now selects
   the least-loaded edge *other than* the current one.
3. **`THROTTLE` was a silent no-op in every branch.** The prefix controller had
   already throttled `gw00`, so forcing the same throttle changed nothing —
   `state_mutated` was false in 10/10 branches, and the table above would have shown
   `THROTTLE ≡ NO_OP` throughout. The forced action now targets the least
   throttled gateway. **This is the most dangerous class of defect for this
   project**: the branch was well-formed, reproducible and completely
   uninformative. Hence state mutation is now recorded per branch and asserted.
4. **SLA failure was inherited from the prefix.** `Failed` was computed from the
   run's cumulative violation counter, so every branch inherited whatever the
   shared prefix had accumulated and the column was constant. Now attributed to
   the branch horizon only.

Defect 3 is the reason `executed` and `state_mutated` are now separate
first-class fields, replacing the single effect flag: an action can be
dispatched and still change nothing, and the replay runner now fails rather than
averaging such a branch in. a replay
framework that cannot tell a real alternative from a relabelled `NO_OP` will
report high agreement between actions and a small `η_J`, and both numbers will
be wrong in the flattering direction.

## Tests

`internal/replay`: anchors reproducible from their own inputs; branch ids
distinct across actions and repetitions; **branch reproducible on re-execution**;
**actions reach system state** (reroute changes the routing table, throttle
changes the rate limiter, throttle does not change routing).

## Stop conditions checked

| Condition | Status |
|---|---|
| Prefixes differ before the branch action | no — anchors reproduce identically |
| Branch effects cosmetic | no — queue, latency, retries and SLA all move |
| No meaningful action effect | no — 10/10 anchors show action-dependent divergence |
| Reconstruction depends on wall time | no — the clock is logical; wall time is recorded and excluded |
| Replay needs runtime-unavailable information | no — anchors carry only seed, config and action history |

## Next, and explicitly not next

**Next: A1, the distributed substrate.** NATS, separate gateway/edge/controller
processes, the gRPC boundary, Docker Compose, privileged `tc`/`netem`,
Prometheus. Then repeat M2 on that substrate.

**Not next: D0.** Measuring `η_J` now would produce a beautiful number — the
repetition pairs are bit-identical — that says nothing about a deployment. The
paper's `η_J` comes from replay over the distributed environment, and only then
does `MIGRATE`/`REPLICATE` and the full 20 × 5 × 30 audit follow.

**Still not next: the GRU.**
