# A1A_REPORT.md

Distributed semantics, built and tested where they can be tested. 2026-08-26.

**A1a is the development substrate. It is not the reportable one.** No `η_J`,
no `SNR_J` and no experimental claim may come from it. What it establishes is
that the distributed *semantics* — transport abstraction, epoch barrier, exact
structural fingerprinting — work, so that A1b has only to swap adapters.

---

## What was built

| Package | What it does |
|---|---|
| `internal/bus` | Transport contract (`Publish`/`Subscribe`/`Close`/`Descriptor`) plus a stdlib TCP broker and client. Separate OS processes, real sockets. |
| `internal/epoch` | The logical anchor barrier: the coordinator declares epoch `k` only after every participant acknowledges finishing ticks `< k`. |
| `internal/fingerprint` | `Structural` (exact, gates branching, with a `Diff` that says which field disagreed), `RuntimeObservation` (varies, recorded, never gates), `RuntimeStack` (identifies what `η_J` belongs to). |

Seven test packages, all green under `go test -race`.

## Three decisions worth defending

**The transport sits behind an interface, and the stdlib broker never claims to
be NATS.** `Descriptor()` returns `stdlib-tcp` and a test asserts it. This is
not fastidiousness: `η_J` is shaped by buffering, scheduling and backpressure,
so a band measured over this broker does not transfer to a NATS deployment.
`RuntimeStack.ID()` folds transport type, version, config hash, RPC type,
kernel, images, netem config and process topology into one identifier recorded
beside every measurement, and a test asserts that changing the bus type changes
the id. Changing the stack invalidates D0.

**Message identity does not reorder the live stream.** Every envelope carries
`experiment_id`, `logical_tick`, `producer_id`, `seq`, `event_id` — used for
alignment, deduplication, replay matching and fingerprints. They are *not* used
to sort delivery into a deterministic order. Reordering everything would strip
out the nondeterminism D0 exists to measure and turn physically separate
processes back into the in-process emulator, producing a flattering `η_J` that
means nothing. Broker fan-out order across subscribers is left unfixed for the
same reason. What *is* asserted is per-producer ordering, because sequence
positions would otherwise be useless for fingerprinting.

**The structural fingerprint has no tolerance.** Queue depths of 48 and 54 are
different counterfactual starting states. Allowing a tolerance there would make
`η_J` a mixture of post-action nondeterminism, which it must measure, and
pre-action mismatch, which it must not — a resolution band partly measuring its
own sloppiness. A test asserts that a six-unit queue difference changes the
hash, and another walks every structural field to confirm none is silently
excluded. Tolerance lives only in `RuntimeObservation`.

The corollary is that branch sets will sometimes abort. That is the intended
failure mode: a high abort rate is evidence the substrate cannot hold a
reproducible prefix. It is reported, not tuned away.

## The barrier

Branching at an arbitrary wall-clock instant would find components at different
points in their own work, so "the same prefix" would mean different things in
different branches. The coordinator declares epoch `k` only when every
participant has acknowledged completing ticks `< k`, and the action is applied
before `k` is processed. A timeout fails and names who did not acknowledge — a
barrier that proceeded quietly with a participant missing would produce branches
whose prefixes were never equal, which is precisely the defect the package
exists to prevent.

This is the only synchronisation point in the system, by design.

## What is not built, and why

`nats.go`, `google.golang.org/grpc` and `protobuf` cannot be fetched in this
build environment (`proxy.golang.org` is outside its egress allowlist), so they
cannot be compiled, race-tested, or exercised for reconnect, ordering, shutdown
or backpressure. Writing them anyway would produce code that looks finished and
has never run. A1a therefore uses a stdlib framed RPC adapter for the
intelligence boundary, and the manifest records `rpc_type` honestly.

The manuscript has been changed to match: it no longer names NATS or gRPC, and
says instead that the prototype uses a message bus and a typed RPC boundary
whose concrete implementations and versions are recorded in each manifest,
together with a runtime-stack identifier.

## Next: A1b, on a host with module access

See `LOCAL_VALIDATION.md`. Implement the NATS and gRPC adapters against the
existing interfaces — the business logic does not change — and run the listed
commands. Until they pass, `NEEDS_LOCAL_VALIDATION` stands and no reportable
M2′, D0-lite or D0 may run.

Then, in order: M2′ (≥30 anchors, 10 repeats), D0-lite with the pre-declared
`SNR_J ≥ 3` gate, `MIGRATE`/`REPLICATE`, full D0, and only then a dataset.
