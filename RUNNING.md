# RUNNING.md

How to start the system, and what your machine can and cannot certify.

---

## The build failure you hit

```
target edge-agent: failed to solve: failed to read dockerfile:
open Dockerfile.go: no such file or directory
```

Two separate mistakes, both mine, both now fixed.

1. **`docker-compose.yml` was left over from the very first scaffold.** It named
   services (`edge-agent`, `fault-injector`, …) and images (`deploy/Dockerfile.go`,
   `deploy/Dockerfile.py`) that were never written, and pulled NATS, Prometheus
   and Grafana that nothing in the code uses yet. It has been rewritten to match
   what exists.
2. **A Dockerfile must not be called `Dockerfile.go`.** The Go tool treats any
   file ending in `.go` as a source file, so `go test ./...` fails with
   `illegal character U+0023 '#'` before running a single test. It is now
   `deploy/go.Dockerfile`.

## Fastest check: no Docker at all

```bash
make build
./scripts/topology_smoke.sh
```

Starts broker, three edges, a gateway, the controller and the intelligence stub
as separate OS processes, runs traffic through them, then reroutes the gateway
and verifies the traffic actually moves:

```
--- before reroute: edge00=2879 edge01=0 ---
--- after reroute:  edge00=3191 edge01=1279 ---
gw00: REROUTE edge00 -> edge01
TOPOLOGY SMOKE OK
```

That second phase matters more than it looks. An earlier version published work
to one shared subject, so all three edges processed every event and the routing
table was decorative — `REROUTE` would have been a no-op wearing the costume of
an intervention. The gateway now publishes to `edge.work.<edgeID>`, and the test
fails if an unrouted edge does any work.

## If the image build fails inside `go build`

```
go.Dockerfile:19
RUN CGO_ENABLED=0 go build -trimpath -o /out/app ./cmd/${CMD_NAME}
did not complete successfully: exit code: 1
```

Two causes, both introduced by `make deps-adapters`, both now fixed.

**The go directive moved.** `go get` rewrites the `go` line in `go.mod` to the
toolchain that ran it. On a machine with Go 1.26 it wrote `go 1.26.0`, and the
image was building on `golang:1.23-alpine`, which refuses a module requiring a
newer language version. The error surfaces inside `go build`, so it reads like a
code problem and is not. The base image is now `golang:${GO_VERSION}-alpine`
with `GO_VERSION=1.26` and `GOTOOLCHAIN=auto`, so it also survives the next time
that directive moves.

**`go.sum` was not in the build context.** The Dockerfile copied only `go.mod`.
With module requirements present and no `go.sum`, `go build` fails verification
even for packages excluded by build tags. It now copies both and runs
`go mod download`.

`make docker-preflight` compares the two in about a second, so the mismatch is
caught before a five-minute build instead of after it:

```
go.mod requires go 1.26.0; image base is golang:1.26-alpine
```

Worth a moment's thought: nothing in this code needs Go 1.26. `go get` chose it,
and it now makes the project unbuildable on any older toolchain — including
whatever a reviewer or a CI runner happens to have. If the dependencies allow
it, lower it back:

```bash
go mod tidy -go=1.23 && go build ./... && go test -race ./...
```

If `nats-server` refuses, keep 1.26 and leave `GO_VERSION` matching it.

## Full topology

```bash
docker compose up --build
docker compose logs -f gateway00 edge00 controller
docker compose down -v
```

Three networks by design: `csc-net-device-gateway` (impaired),
`csc-net-gateway-edge` (bus), `csc-net-control` (RPC and telemetry). Impairment
must not reach the control plane, or a run that degraded the controller itself
would be reported as a data-plane fault experiment.

---

**Docker is not on the critical path for M2′.** `./scripts/topology_smoke.sh`
already gives what the methodology needs — separate OS processes, real sockets,
real interleaving — and it needs no daemon. If the image build keeps fighting
you, run M2′ against the process topology and treat the containers as the
packaging step they are.

## Two stacks, and only one of them is reportable

```bash
docker compose up --build                        # development: stdlib broker
make up-nats                                     # reportable:  NATS transport
```

Both files claim the same three network names, so bring one down before
starting the other (`make up-nats` does that for you).

The nodes take `-bus-impl tcp|nats`. The NATS transport is compiled in only with
`-tags=nats`, and a binary built without it **refuses** the flag rather than
falling back:

```
bus: transport "nats" is not compiled into this binary (available: [tcp]);
the NATS adapter requires -tags=nats
```

That refusal is deliberate. A node quietly running on the development bus
because a flag was misspelled is the one error this project cannot detect after
the fact — the numbers would look fine and belong to the wrong stack.

`make local-validate` step 6 stamps the development stack and then runs the
reportable check, which is **expected to fail** there:

```
NON-REPORTABLE SUBSTRATE
  - bus_type='stdlib-tcp' is the development implementation
  - impairment_mode='application_layer'
```

For a stack that passes:

```bash
make up-nats      # NATS transport, one process per role
make stack-nats   # applies impairment, stamps, validates
```

`make netem-nats` verifies impairment **and removes it** — right for a smoke
test, wrong before a stamp, because `csc-stackstamp` has to see the qdisc to
record `impairment_mode=kernel_netem`. `make stack-nats` depends on
`netem-apply` (`KEEP=1`), which leaves it in place. Applying impairment and
tearing it down a second before stamping is how a correctly impaired stack
reports itself as application-layer.

The stamp distinguishes **blockers** from **notes**. `rpc_type=stdlib-framed-tcp`
is a note: the manuscript claims a typed RPC boundary and the framed adapter is
one — tested, measuring `T_rpc` apart from `T_model`, turning a missed deadline
into a recorded fallback. Blocking it would have been the checker enforcing a
claim the paper does not make. If a draft ever names gRPC, run the checker with
`--require-rpc grpc` and that stops being true.

`csc-stackstamp` records the facts and refuses to run without `-bus`, so the
transport can never be defaulted into the manifest;
`check_reportable_stack.py` judges them. Keeping those apart matters: a tool
that both gathered the evidence and blessed it could be talked into blessing
anything.

## M2′ on the reportable stack

```bash
make up-nats        # recreates nats with port 4222 published to the host
make stack-nats     # impairment + stamp + validation
make m2prime-nats   # prefix equality against the NATS stack
```

Two things had to change for the orchestrator to reach that stack, and both are
worth knowing because they look like different failures than they are.

`make m2prime-nats` runs `go run **-tags=nats**`. Without the tag the binary
refuses the transport by name — the guard working correctly on a target that had
forgotten to ask for it. `make build TAGS=nats` does the same for the local
binaries.

NATS publishes `4222` to the host, because the orchestrator runs there
rather than in a container. Only control traffic crosses that port; the data
path stays inside the compose networks. Because a root qdisc shapes egress,
`netem` is installed on the device simulator's device-network interface, which
is the declared device→gateway direction; installing it on the gateway would
shape the reverse direction. Its control interface is checked to be unshaped.

The two-run `make m2prime-nats` command is only a smoke. The reportable burn-in
and M2' matrix recreate every container for every branch so counters, queues and
routing cannot leak between run IDs:

```bash
make up-nats
NETEM_SEED=424242 make stack-nats
make build TAGS=nats
STACK_ID=$(python3 check_reportable_stack.py --print-stack-id) \
  EXPERIMENT=burnin-nats ANCHORS=8 REPEATS=6 ACTIONS=NO_OP HORIZON=0 \
  scripts/m2prime_nats_matrix.sh

STACK_ID=$(python3 check_reportable_stack.py --print-stack-id) \
  EXPERIMENT=m2prime-900 ANCHORS=30 REPEATS=10 \
  ACTIONS="NO_OP THROTTLE REROUTE" HORIZON=3 \
  scripts/m2prime_nats_matrix.sh
```

Do not pass `BUS_IMPL=nats` to `scripts/m2prime_matrix.sh`: that script starts
the local stdlib broker and is deliberately restricted to development TCP.

The NATS adapter also flushes on `Subscribe`. Subscriptions register
asynchronously, so a publisher starting immediately afterwards can beat the
registration to the server and its first messages are never delivered — in an
epoch barrier that appears as a node "not acknowledging", which reads exactly
like a logic bug in that node.

## Moving to a Linux host

```bash
make deploy HOST=cybernord
```

The deployment intentionally excludes `.git`; therefore `git log` and
`git show` are unavailable on the server. Use `SOURCE_REVISION` for provenance,
or clone the repository instead of deploying an archive. In examples,
`<sha>` is a placeholder to replace with a real commit, not literal shell text.

or directly:

```bash
rsync -avz --delete \
  --exclude '.git' --exclude 'bin/' \
  --exclude 'data/raw/' --exclude 'data/processed/' --exclude '_to_delete/' \
  --exclude 'experiments/manifests/reportable_stack.json' \
  --exclude 'paper/main.pdf' --exclude 'paper/*.aux' --exclude 'paper/*.log' \
  ~/"Science Article 2025-/Counterfactual Shadow Control Uncertainty-Aware Proactive SelfHealing for Mobile Edge IoT Systems/csc-iot"/ \
  cybernord:~/csc-iot/
```

Then on the host:

```bash
ssh cybernord
cd ~/csc-iot
./scripts/audit_repo.sh                     # 25 invariants, one second
make build && ./scripts/topology_smoke.sh   # no Docker needed
make up-nats && make stack-nats && make m2prime-nats
```

**`reportable_stack.json` is deliberately not copied.** A stack stamp belongs to
the machine that produced it: it names that kernel, those image digests, that
process topology. Carrying one across hosts is precisely how an `η_J` ends up
attributed to hardware that never ran it. Re-stamp on the host with
`make stack-nats`; the `runtime_stack_id` will differ from the Mac's, and that
difference is the point.

`go.sum` **is** copied. If the host cannot reach the module proxy, `go.sum` is
what lets `go mod download` verify what it already has.

Expect the Linux `runtime_stack_id` to be the one that goes in the paper: the
LinuxKit kernel inside Docker Desktop is a legitimate stack to record but an
awkward one to defend, and the reported `η_J` should come from a plain kernel.

## macOS on Apple silicon: yes, with one caveat that matters

**Development and M2′: yes, natively.** Docker Desktop runs a Linux VM, so the
containers are Linux and `tc`/`netem` work inside them. Everything builds arm64
without emulation. Nothing about the replay machinery needs a different host.

Check the one thing that can bite:

```bash
./scripts/kernel_netem_check.sh
```

It reports the kernel your containers see and tries to apply a qdisc.
**Confirmed working on an M1 Pro under Docker Desktop:**

```
qdisc netem 8001: root refcnt 11 limit 1000 delay 20ms 5ms loss 5% seed 424242
OK: impairment confined to eth0 in device-sim
```

If `sch_netem` were missing from the LinuxKit kernel, runs on that host would
have to record `impairment_mode=application_layer` and would not be reportable —
the script says so and exits non-zero.

**Impairment is applied inside the container**, on the interface attached to the
device-gateway network, not on a host bridge. The root qdisc is on the sender's
egress; on Linux the container and equivalent host-bridge arrangements can be made equivalent;
on macOS the bridges live inside the VM where the host cannot address them, so
the in-container form is the only one that works on both. `scripts/netem_smoke.sh`
applies it and then checks the negative: that the qdisc did *not* appear on the
bus interface.

**The caveat, for the D0 that goes in the paper.** `η_J` is a property of one
runtime stack, and the LinuxKit kernel inside Docker Desktop, its virtualised
networking and its scheduler are not the stack a reviewer will picture. It is a
legitimate stack if you say so — `runtime_stack_id` records the kernel and every
image digest — but "macOS/Docker Desktop VM" invites a question that a plain
Linux host does not. Recommended split:

| Stage | Where | Why |
|---|---|---|
| A1a/A1b development, M2′ | M1 Pro, Docker Desktop | fast, native arm64, everything works |
| D0-lite | either, stack recorded | it is a go/no-go, not a published number |
| **Full D0 and main experiments** | **a plain Linux host** | the stack `η_J` is reported for |

A Linux VM on the Mac (UTM/Lima/Multipass) is a middle option, but it is another
virtualised kernel — it does not remove the question, only moves it. If you have
no Linux machine, run everything on the Mac and record the stack honestly;
that is defensible, and hiding it would not be.

---

## What still cannot run anywhere yet

`internal/bus/nats.go` and `internal/rpc/grpc.go` are behind `//go:build nats`
and `//go:build grpc`. The environment this was developed in cannot reach the Go
module proxy, so they have never been compiled. On your machine:

```bash
go get github.com/nats-io/nats.go google.golang.org/grpc google.golang.org/protobuf
go test -tags=nats -race ./internal/bus/
go test -tags=grpc -race ./internal/rpc/
```

Until those pass, `check_reportable_stack.py` refuses to let a reportable run
start, and it rejects `bus_type=stdlib-tcp` and `impairment_mode=application_layer`
even when the validated flag is set to true. A stamp is not a substitute for a
stack.

---

## First thing to run after any update from the session

```bash
make audit
```

Thirteen invariants, one second, each one a regression that has actually
happened here. Three times an archive unpacked over the repository carried an
older copy of a file that had been fixed on this machine — `check_stale.py`
twice, then `go.mod` and `deploy/go.Dockerfile` together — and each was found
by a different failing build minutes apart. `make audit` finds all of them at
once, and now runs first in `local-validate`.

## If `check-adapter-deps` fires after an update from the session

```
The NATS and gRPC adapters are behind build tags and their modules
are not in go.mod yet.
```

but `go get` was already run: something overwrote `go.mod`. An archive extracted
over the repository carried its own copy, wiping the `require` blocks and
reverting the `go` directive. `go.sum` normally survives, so one command
restores it:

```bash
make deps-adapters
```

`make check-modfile` now runs first in `local-validate` and names this cause
directly, because the generic "modules are not in go.mod yet" message sends you
looking in the wrong place.

## Leftover empty directories

`cmd/controller`, `cmd/device-sim`, `cmd/edge-agent`, `cmd/fault-injector`,
`cmd/gateway` and `cmd/replay-orchestrator` are empty placeholders from the very
first scaffold — the same batch that produced the broken compose file. The
working binaries are `csc-broker`, `csc-intelligence`, `csc-node`, `csc-act`,
`csc-sim` and `csc-replay`. Delete the empty ones locally:

```bash
rmdir cmd/controller cmd/device-sim cmd/edge-agent \
      cmd/fault-injector cmd/gateway cmd/replay-orchestrator
rm -rf _to_delete
```

(They cannot be removed from the session that wrote them: this environment can
create files on your disk but not delete them.)
