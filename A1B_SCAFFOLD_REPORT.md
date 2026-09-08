# A1B_SCAFFOLD_REPORT.md

Two corrections to A1a, then adapter scaffolding. 2026-08-27.

---

## C1 — the epoch barrier was not sufficient on an asynchronous bus

**The defect.** The barrier released epoch `k` once every participant
acknowledged finishing its local work for ticks `< k`. On an async transport
that is not the same as the transport being empty: a gateway can truthfully
report finishing tick 99 while a message it published during tick 99 is still in
a socket buffer. Two branches would then show identical local counters and
differ in what is in flight — invisible to local bookkeeping, and presenting as
a perfectly valid common anchor right up until the branches diverge for reasons
nothing can account for.

**The fix.** A watermark protocol in `internal/epoch/quiescence.go`:

```
producer:  END_EPOCH(k, producer_id, subject, last_seq)
consumer:  DRAINED(k, producer_id, consumer_id, subject, consumed_through_seq)
anchor opens  ⟺  ∀ consumer, ∀ declaring producer:  consumed_through ≥ last_seq
```

The watermarks form a `TransportQuiescenceFingerprint` that must match exactly
alongside the structural one. A timeout never proceeds; it reports exactly who
is behind and by how much (`edge00 consumed gw00 through 97 of 100`). An epoch
nobody declared is **not** treated as trivially drained — "nothing declared" and
"everything consumed" are different states, and a test asserts it.

This is a completeness protocol, not a scheduler. Within an epoch, delivery and
processing keep real arrival order.

## C2 — the structural fingerprint was incomplete

**The defect, and why it was the more dangerous of the two.** Queue *depth* was
in the fingerprint; queue *contents* were not. Two prefixes holding
`[e1001..e1048]` and `[e1002..e1049]` both report 48 and hashed identically —
while having different futures. Unlike ordinary nondeterminism, this does not
look like noise. It looks like a valid common anchor.

**The fix.** `Structural` now carries, all exact:

| Added | Why it can change the future |
|---|---|
| queue content hash, head/tail event id | equal depth, different events |
| retry pending set, attempt counts, backoff deadlines (in logical time) | a retry due at tick 126 is not the same state as one due at 130 |
| rate-limiter **current tokens**, not only the configured limit | a bucket at 3 tokens behaves unlike one at 47 under the same rate |
| timeout deadlines | pending expiries shape the next ticks |
| service placement, replica state, pending migrations, edge capacity | `MIGRATE`/`REPLICATE` operate on exactly this |
| transport quiescence watermarks | see C1 |

A test walks every one of these and fails if a mutation leaves the hash
unchanged: a field that can change the future while leaving the fingerprint
alone is a hole in the methodology, not a detail. `Diff` reports *why* a branch
set was aborted — including the specific case "same length 48 but different
contents".

## Adapters, behind build tags

`internal/bus/nats.go` (`//go:build nats`) and `internal/rpc/grpc.go`
(`//go:build grpc`). The default build and `go test ./...` do not compile them,
so nothing in the restricted environment depends on modules it cannot fetch —
and, more to the point, no test suite passes on a machine that has never run
them. Both are marked `NEEDS_LOCAL_VALIDATION` in their package comments.

**Core NATS pub/sub only.** JetStream would add persistence, acknowledgement,
redelivery and replay semantics, all of which change the timing this project
measures. `η_J` would then describe a different system. Durability is not part
of the research question.

The RPC contract is frozen in `internal/rpc/rpc.go`, with a stdlib framed TCP
implementation and a stub server that is deterministic and obviously synthetic —
a stub that looked like a plausible model would invite someone to read meaning
into it. `Timing` separates `T_rpc` from `T_model` and `T_cf`, and the
manuscript's decomposition is now
`T_dec = T_feat + T_rpc + T_model + T_cf + T_gate`: once the intelligence plane
is its own process, folding serialisation and network time into the model term
would hide where a missed deadline came from. A test asserts that a slow reply
becomes a recorded fallback rather than a stalled controller.

## Reportability guard

`check_reportable_stack.py` refuses to let a reportable runner start unless the
validated-stack stamp says so. It rejects `bus_type=stdlib-tcp`,
`rpc_type=stdlib-framed-tcp` and `impairment_mode=application_layer` **even when
`reportable_stack_validated` is true** — a stamp is not a substitute for the
stack. What this prevents is concrete: 840 main-experiment runs executed
overnight against the development substrate, producing a complete, consistent,
entirely unpublishable result set in which nothing would look wrong.

`make local-validate` is now an executable gate rather than a list of commands,
ending in `REPORTABLE_STACK_VALIDATED`; `scripts/netem_smoke.sh` fails if the
qdisc appears on the control or bus network rather than only on the
device→gateway ingress.

## Manuscript sync

`gRPC calls over TCP` → `typed RPC calls over TCP`; Fig. 2 label `gRPC S_t` →
`RPC S_t`. The Prometheus claim is removed: `grep -ri prometheus --include='*.go'`
returns nothing, so the manuscript was describing an export that does not exist.
`check_stale.py` now fails on any concrete mention of NATS, gRPC or Prometheus
until local validation passes.

## An honest note on the guards

`check_stale.py` has now been clobbered **twice** by a stale copy pushed from a
scratch build directory, each time silently dropping its EXEMPT refinements. Both
times it caught itself on the next run. The file now says it is the canonical
copy and that a second one should be deleted. The guards work; the process
around them needed the same discipline they enforce.

## Status

31 Go files, 9 test files, 8 packages green under `-race`. Adapters written and
unvalidated by design.

**Next:** `make local-validate` on the target host, then M2′ (≥30 anchors, 10
repeats), then D0-lite with the preregistered `SNR_J ≥ 3` gate. Not before.
