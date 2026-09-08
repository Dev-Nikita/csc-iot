# LOCAL_VALIDATION.md

Commands that must pass on a Linux host with Go module access and root, before
any measurement in this project counts as reportable.

Nothing below has been run in the build environment used so far: it cannot
reach `proxy.golang.org`, and it is not privileged. Every item is therefore
`NEEDS_LOCAL_VALIDATION` until you run it.

---

## 1. The substrate already built here

```bash
make build
make test          # go test -race ./... plus pytest intelligence/tests
make determinism   # same seed reproduces the run
make experiment-smoke
make replay        # M2 on the deterministic core
```

Expected: all green; the two smoke runs print the same `determinism sha256`.

## 2. A1b — adapters that could not be built here

```bash
make deps-adapters      # go get nats.go + nats-server, then go mod tidy
make local-validate
```

`make local-validate` now refuses early with an instruction rather than a raw
`no required module provides package` error. Expect the first tagged build to
surface **real compile errors** in `internal/bus/nats.go`: it has never been
compiled anywhere. Fixing them is the work of A1b, not a sign something is wrong.

`internal/bus/nats_test.go` runs an **embedded** NATS server, so no external
process is needed. It covers publish/subscribe, per-edge subject isolation,
per-producer ordering, concurrent publishers, the slow-consumer path, and a
descriptor check asserting that JetStream stays off.

Then implement, against the existing interfaces and without touching business
logic:

- `internal/bus/nats.go` — `Descriptor()` must return `nats` and the real server
  version. If it ever returns `stdlib-tcp`, a measurement could be attributed to
  the wrong stack.

**gRPC is off the critical path.** The paper claims a *typed RPC boundary*, and
`internal/rpc.framedClient` already is one: tested, measuring `T_rpc` apart from
`T_model`, and turning a missed deadline into a recorded fallback. That is
everything the methodology asks. `internal/rpc/grpc.go` documents what
implementing it would involve and deliberately compiles to nothing rather than
sitting in the tree as a sketch that looks finished.

## 3. Kernel network impairment

```bash
sudo tc qdisc add dev <device-egress-if> root netem loss 5% delay 20ms 5ms seed 424242
sudo tc qdisc show dev <device-egress-if>
sudo tc qdisc del dev <device-egress-if> root
```

Impairment belongs to the **device→gateway** path and a root qdisc is therefore
installed on the device sender's egress. `REROUTE` changes the
gateway→edge compute assignment and must leave impairment untouched — M2
confirmed the implementation behaves this way and the SCM in the manuscript now
says so. Applying loss to the edge selection would reintroduce that mismatch.

A run with kernel impairment records `impairment_mode = kernel_netem`. Without
`NET_ADMIN` it records `application_layer`, and such runs are never mixed into
reported comparisons.

## 4. Full topology

```bash
docker compose up --build
```

Expected: one process per role — device-sim, three gateways, three edges,
controller, intelligence, broker — with telemetry flowing and manifests written.

## 5. Gate before anything is reportable

Record, from the running system:

```
go version, uname -r, bus type and version, transport config hash,
rpc type, container image digests, netem config, process topology
```

These become `runtime_stack_id`. Every subsequent `η_J` is a property of that
id. **Change the transport and D0 must be re-run** — an `η_J` measured over the
stdlib broker cannot be published for a NATS deployment.

## 6. Then, and only then

1. **M2′** — ≥30 anchors across pre-fault, transition and degraded regions of F1
   and F2; `NO_OP`/`REROUTE`/`THROTTLE`; 10 repeats each. Record structural and
   runtime fingerprints, trajectories, percentiles, SLA outcome, cost, raw
   execution hash and `runtime_stack_id`. Acceptance: exact structural match
   before branching, no silent non-`NO_OP` actions, measurable action-dependent
   divergence, and a reported prefix-abort rate. **No `η_J` is frozen here.**
2. **D0-lite** — 10 × 3 × 20. Compute `η_J = Q_0.95` of same-anchor same-action
   objective differences and `SNR_J` as defined in `A1_PLAN.md`.
   **Gate: `SNR_J ≥ 3`.** Below it, stop — do not implement `MIGRATE` or
   `REPLICATE`, do not train anything, investigate replay fidelity. The
   threshold is not revised after seeing the number.
3. `MIGRATE` and `REPLICATE`, with state-transfer and cold-start costs modelled.
4. **Full D0** — 20 × 5 × 30 — freeze `η_J` with its `runtime_stack_id`.
5. Dataset, then the model.
