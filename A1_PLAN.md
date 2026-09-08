# A1_PLAN.md — distributed substrate

Written before implementation, 2026-08-25. A1 is not plumbing: it is the next
scientific gate, because `η_J` measured on a single-threaded core says nothing
about a deployment.

---

## Status

**A1a is built and tested** (`internal/bus`, `internal/epoch`,
`internal/fingerprint`): transport behind an interface with a stdlib TCP
adapter, the epoch barrier, and both fingerprints, all under `go test -race`.
**A1b — the NATS and gRPC adapters — is not**, for the reason below, and no
reportable measurement may be taken until it is.

## A constraint that changes the build order

The Go module proxy is unreachable from the build environment used for A0 and
M2 (`proxy.golang.org` is outside its egress allowlist), so `nats.go` and
`nats-server` cannot be fetched, compiled or tested there. Two consequences,
stated plainly rather than worked around:

1. **Anything written against the NATS client here would be untested code**, and
   this project's rules forbid shipping that. The same applies to
   `google.golang.org/grpc` and `protobuf`: the RPC boundary is equally
   unbuildable here, so A1a uses a stdlib framed RPC adapter and the manifest
   records `rpc_type` accordingly. Neither NATS nor gRPC may appear in a
   manifest, or in the manuscript, before it has actually run.
2. **The transport is therefore built behind an interface.** `internal/bus`
   defines the publish/subscribe contract; the first implementation is a
   stdlib TCP broker, which gives what the science actually needs — separate OS
   processes, real sockets, real kernel scheduling, real interleaving. A NATS
   adapter implements the same interface and is built and tested on a machine
   with module access.

**The manuscript must say what was actually used.** Until the NATS adapter runs
the reported experiments, `ARCHITECTURE.md` and the paper say "a message bus"
with the concrete implementation named in the artifact. Writing NATS into the
prototype description while the runs used a stdlib broker would be the same
class of error as calling application-layer impairment `netem`.

## Processes and topology

Separate binaries, one role each, not goroutines in one process — the point is
concurrency the runtime does not control:

```
   virtual devices (inside device-sim workers)
            │  direct TCP ingress   ← F1/F2 tc/netem applies HERE
            ▼
   gateway-01/02/03
            │  message bus          ← REROUTE changes THIS assignment
            ▼
   edge-01/02/03
            │
   controller ─── typed RPC ──► intelligence (stub until a model exists)
```

The earlier draft of this plan showed `device → gateway → bus → edge` while also
listing an `iot.events` subject carrying `device → gateway`. Those are two
different architectures and only one can be built. Resolved in favour of direct
TCP ingress, because it lines up with the corrected SCM: impairment belongs to
the radio-facing link, and `REROUTE` is a compute-path intervention that must
leave that impairment untouched. Routing ingress over the same bus would
reintroduce exactly the mismatch M2 exposed.

Virtual devices stay inside `device-sim` workers; one container per device would
buy nothing and cost everything.

## Bus subjects

```
edge.work             gateway → edge
gateway.telemetry     gateway → collector
edge.telemetry        edge → collector
controller.actions    controller → gateway/edge
experiment.epoch      coordinator → all
experiment.epoch.ack  all → coordinator
```

**Message identity is for alignment, not for reordering.** Every envelope
carries `experiment_id`, `logical_tick`, `producer_id`, `seq` and `event_id`,
used for trace alignment, deduplication, replay matching and fingerprinting.

They are deliberately **not** used to reorder the live stream into a
deterministic sequence. Where queueing depends on arrival order, real arrival
order is preserved. Globally reordering delivery would remove much of the
nondeterminism D0 exists to measure and quietly turn physically separate
processes back into a deterministic emulator — the system would look
distributed and behave like the in-process core, and `η_J` would be flattering
and meaningless.

## The one place synchronisation is allowed: the epoch barrier

A branch is never taken at an arbitrary wall-clock instant. The coordinator
declares epoch `k` only after every participant has acknowledged completing all
work belonging to ticks `< k`; the action is applied before tick `k` is
processed. A barrier that timed out silently would produce branches whose
prefixes were never equal, so a timeout fails and names the participants that
did not acknowledge.

**Local acknowledgement is not enough on an asynchronous bus.** A gateway can
truthfully report that it finished tick 99 while a message it published during
tick 99 is still in a socket buffer on its way to an edge. Both branches would
then show identical local counters and differ in what is in flight — a mismatch
no local bookkeeping can see, presenting as a valid common anchor. The barrier
therefore carries a watermark protocol: each producer declares
`END_EPOCH(k, producer, last_seq)`, each consumer confirms
`DRAINED(k, producer, consumer, consumed_through_seq)`, and the anchor opens only
when every consumer has consumed every declaring producer through its declared
last sequence. The resulting watermarks form a **TransportQuiescenceFingerprint**
that must also match exactly before branching.

The protocol is about completeness, not scheduling. Within an epoch, messages
are still delivered and processed in real arrival order.

## Impairment must not leak onto the control plane

`tc`/`netem` on a shared interface would degrade the controller's own RPC and
the gateway-to-edge bus alongside the data plane, and the run would be reported
as a data-plane fault experiment. Three Docker networks keep them apart —
`csc-net-device-gateway` (impaired), `csc-net-gateway-edge`, `csc-net-control` —
and `scripts/netem_smoke.sh` fails if the qdisc appears on any but the first.
Interface, qdisc type, loss, delay, jitter, rate and handle are recorded in the
manifest, so "did the injected loss also impair the controller?" has an answer.

## gRPC boundary

A stub intelligence service implementing `EvaluateActions` and returning
deterministic dummy scores. Its purpose before any model exists is to measure
what the paper claims to measure: RPC latency distribution, the enforced
deadline, and that a missed deadline produces a **recorded fallback** rather
than a stalled controller.

## Network impairment

Per-path qdiscs, privileged `tc`/`netem`. Because `REROUTE` is a **compute-path**
intervention (M2 confirmed the implementation never touched loss or retries, and
the SCM in the manuscript now says so), F1 and F2 impairment applies to the
device→gateway ingress path, not to the gateway→edge choice. Applying loss to
the edge selection would reintroduce exactly the mismatch M2 exposed.

## M2′ acceptance

Bit-identical telemetry is the wrong test here and will not hold. The test is
the **StructuralStateFingerprint**, matched exactly: logical tick, per-producer
sequence positions, fault phase, routing assignment, rate limits, per-edge
processed counters, queue depths, action history and configuration hash. The
runner recomputes it from live state and compares it with the anchor's before
branching; a mismatch aborts the branch set and reports which field disagreed.

No tolerance is permitted there. If branches may start from queue depths of 48
and 54, the dispersion band measured afterwards mixes post-action
nondeterminism, which it must capture, with pre-action state mismatch, which it
must not — and becomes partly a measure of its own sloppiness. Tolerance belongs
to the **RuntimeObservationFingerprint** (CPU, RSS, wall-clock and scheduler
timings), whose dispersion is recorded as evidence and never gates a branch.

Scale: **≥30 anchors** — not the 10 of M2 — spread across a pre-fault region, a
transition region and a degraded region of F1 and F2, with 10 repeats per
action. No `η_J` is frozen at this stage; what is measured is prefix dispersion,
branch outcome dispersion, real action effect, and transport-induced noise.

## Then, in order

1. **D0-lite**: 10 anchors × 3 actions × 20 repeats on A1, with the go/no-go
   criterion declared here, before the data exist:

   ```
   SNR_J = median over anchors and action pairs of |median J(a_i) − median J(a_j)|
           ────────────────────────────────────────────────────────────────────
                                       η_J
   ```

   **Gate: `SNR_J ≥ 3`.** Below that, stop: do not implement `MIGRATE` or
   `REPLICATE`, do not train anything, and investigate replay fidelity. The
   threshold is not revised after seeing results.

   Reported alongside, because a median can hide the shape of the distribution
   when some action pairs are naturally equivalent at some anchors:

   ```
   P_resolvable = P(|ΔJ| > η_J)   over all action contrasts
   ```

   e.g. "78% of action contrasts were resolvable at the D0 resolution". The
   primary go/no-go criterion remains `SNR_J ≥ 3` as preregistered.

   `η_J` itself is `Q_0.95` of same-anchor same-action objective differences.
   Those pairwise differences are **not independent** — 30 repeats give 435
   correlated pairs — so the band is reported as an operational resolution, and
   any interval for the band itself is obtained by resampling **anchors**, not
   by treating pairwise differences as independent observations.
2. `MIGRATE` and `REPLICATE`, with state-transfer and cold-start costs modelled.
3. **Full D0**: 20 × 5 × 30, freeze `η_J`.
4. Dataset, then the model.

## What could go wrong, in the order it probably will

- **The exact structural match may abort often.** That is the intended failure
  mode — a high abort rate says the substrate cannot hold a reproducible prefix,
  which is information, not an inconvenience to be tuned away with tolerance.
  The abort rate is reported alongside every replay result.
- **`η_J` may swamp the effect.** This is the project's principal empirical risk
  and the reason D0-lite exists: to find out cheaply.
- **The controller deadline may not survive real RPC latency.** The 100 ms p95
  budget was set against a 500 ms tick on paper; A1 is where it meets a network.
