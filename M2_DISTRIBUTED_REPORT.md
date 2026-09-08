# M2_DISTRIBUTED_REPORT.md

M2′ step one: **can two runs of the distributed system, started from the same
prefix specification, reach the same structural state at the same anchor?**

Answer, on the local process topology: **yes** — but only after four separate
defects were found and fixed, and each was found by the measurement itself
rather than by reading the code.

---

## Result

```
run A anchor hash: d408c405fd7b0226874cac1ffff11c8e
run B anchor hash: d408c405fd7b0226874cac1ffff11c8e
MATCH: two distributed runs reached an identical structural state at the anchor.
```

Stable across six run-pairs at two anchor depths (epoch 3 of 4, epoch 4 of 6).
Separate OS processes, real TCP sockets, the broker's fan-out order left
unfixed. Reproduce with `make m2prime-local` — no Docker required.

**This is the local stdlib-broker topology.** It is not the reportable stack and
no `η_J` follows from it. The same check against NATS is `make m2prime-nats`,
and it may well answer differently: that is the point of asking it there too.

## How the anchor is taken

The orchestrator drives epochs. At each one the coordinator waits for every
participant to acknowledge, then the watermark protocol waits for the transport
to drain, and only then are all nodes asked for their slice of the structural
state. Slices are combined with node-namespaced keys, so two nodes cannot
silently overwrite each other's entry, and hashed.

## What the measurement found

**1. The workload was driven by the wall clock.** First run: the two executions
recorded 10,137 and 10,162 events at the same anchor — 0.25% apart. `device-sim`
emitted on a `time.Ticker`, so how many events existed when the anchor was taken
depended on how fast the machine happened to be. No amount of fingerprint
precision can repair a workload whose size is a function of real time. It now
emits exactly `events-per-epoch` per epoch and acknowledges only afterwards, so
the count at epoch *k* is a property of *k*.

**2. Quiescence was a warning, not a gate.** With the workload fixed the gap
narrowed to 600 versus 561 — the gateway had published identically, but the edge
had not finished consuming, and the fingerprint recorded the difference as
though it were state. The orchestrator now refuses to fingerprint an undrained
transport at an anchor.

**3. The epoch boundary could not be signalled out of band.** Still 506 versus
518. The gateway declared its end-of-epoch sequence from the barrier callback
while its ingress reader was a separate goroutine behind it: it announced a
`last_seq` lower than what it would go on to publish, the edge confirmed that
lower number, and quiescence was satisfied with events still in flight. A side
channel cannot tell a stage that a stream has ended — only the stream can. The
epoch marker now rides the ingress socket behind that epoch's events, so a
gateway that has seen the marker has necessarily seen all of them.

**4. One idle node stalled everyone.** `gw01` has an ingress listener but no
`device-sim` attached, so it waited for a marker that would never arrive and the
barrier timed out naming it. Waiting is now conditional on actually having a
producer.

Defects 1 and 3 are the interesting ones. Both would have produced a system that
looked correct — processes running, events flowing, fingerprints computed — while
quietly comparing states that were never the same. Neither is visible in a code
review; both are obvious the moment two runs are hashed against each other.

## A rule the fingerprint enforces in both directions

The controller's count of telemetry samples was in the fingerprint and varied
between runs. It came out — not because it was inconvenient, but because it is
not future-relevant: the controller's tally does not influence how the system
evolves. Everything future-relevant must be in the fingerprint, and nothing else
may be. A field that varies without changing the future would abort branch sets
for no reason, which is as damaging as a missing field that changes it silently.

Edge telemetry is now emitted once per epoch for the same reason a workload is:
how many samples exist by a given anchor must be a property of the epoch.

## What this does and does not establish

Established: the prefix of a distributed run over real processes and sockets can
be reproduced exactly, in every field the methodology calls future-relevant, and
verified before branching.

Not established, and next:

1. the same check on the **NATS stack** (`make m2prime-nats`) — the answer there
   is the one that matters, since `η_J` belongs to that stack;
2. **branching**: execute `NO_OP` / `REROUTE` / `THROTTLE` from a verified
   anchor and record the outcomes;
3. ≥30 anchors across pre-fault, transition and degraded regions of F1 and F2,
   10 repeats, with the **prefix-abort rate reported** — a high abort rate is
   information about the substrate, not an inconvenience to tune away;
4. only then **D0-lite** and its pre-registered `SNR_J ≥ 3` gate.

No machine learning until `η_J` is frozen on the reportable stack.
