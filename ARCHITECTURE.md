# ARCHITECTURE.md

Two planes. **Go is the execution/control plane** — it owns time, concurrency, the network, and every side effect on the running system. **Python is the intelligence plane** — it owns the predictor, the SCM, calibration, and counterfactual evaluation, and owns no side effects at all. The boundary is a gRPC contract (`proto/csc.proto`); nothing crosses it except typed messages.

That split is not decoration. It is what makes the runtime-overhead measurement meaningful: the decision path is a measurable RPC with a measurable deadline, not a function call inside a notebook.

```
 Virtual IoT devices (Go)            device-sim
   events, mobility, workload classes
             |
             v
 Gateway plane (Go)                  gateway
   routing, queueing, retries, backpressure, handover
             |
             v
 Edge plane (Go)                     edge-agent
   service execution, queue depth, replication state
             |
   telemetry (100 ms)
             v
 Telemetry collector (Go) --> temporal state store --> Prometheus
             |
             | gRPC: StateSnapshot
             v
 Intelligence service (Python)       intelligence/
   temporal predictor  ->  SCM / do(a)  ->  conformal calibration
             |
             | gRPC: ActionRanking [{action, risk, upper_bound, width, cost}]
             v
 Safety gate + MNI selector (Go)     controller
   admissible = {a : R_hat(a) <= tau_hat and U_hat(a) <= U_max}   # tau_hat: CRC-calibrated offline, frozen
   a* = argmin cost over admissible, else fallback (abstain; NOT covered by the CRC guarantee)
             |
             v
 Runtime controller (Go)  -> NO_OP | REROUTE | MIGRATE | THROTTLE | REPLICATE
             |
             v
 Closed-loop observation (Go -> Python): predicted vs observed at t+delta
```

Fault injection (`fault-injector`, Go) drives `tc`/`netem` where privileged, and an explicitly-labelled application-layer impairment path where not. The distinction is recorded per run in the manifest — the paper must never present application-layer impairment as kernel-network impairment.

Replay (`replay-orchestrator`, Go + `internal/snapshot`) reconstructs an environment deterministically from logged configuration and state and executes one branch per candidate action. It does not snapshot process memory.

## Where the safety gate lives, and why

The gate and the MNI selector are **in Go, in the controller**, not in Python. The intelligence service returns a ranking with bounds and costs; it never returns "do this". Two reasons: the component that can refuse to act must not be the component that might be miscalibrated, and a controller that keeps acting when the intelligence service is slow or down (by falling back) is the only honest way to measure decision overhead as a deadline rather than a wish.

## Messaging and transport

- Go ↔ Python: **gRPC + Protobuf**. Typed schema, streaming, low latency, and a contract a reviewer can read.
- Event bus: **NATS**. Small, fast, Go-native. MQTT stays an optional adapter for IoT realism, not a dependency.
- Metrics: Prometheus (`csc_event_latency_seconds`, `csc_queue_depth`, `csc_packet_loss`, `csc_retry_total`, `csc_intervention_total`, `csc_failure_total`, `csc_shadow_latency_seconds`, `csc_abstention_total`).

## Decision latency budget

`T_decision = T_features + T_model + T_CF + T_gate`, measured separately, reported as a table. `T_CF` scales with |A| = 5 and is the quantity RQ4 is really about. The controller enforces a deadline; a missed deadline is recorded as a fallback, not silently awaited.

## Determinism substrate

Three mechanisms, all in Go, all prerequisites for replay:

- **Experiment clock.** Every event carries `experiment_time`, `sequence_number` and `wall_clock_time`. Ordering and schedules are driven by the first two; wall clock is used only for runtime performance measurement. Code that branches on `time.Now()` is not replayable and is rejected in review.
- **Per-component RNG streams.** `seed_i = SHA256(master_seed || component)` for `workload`, `mobility`, `network`, `service`, `fault`, `controller` and `behaviour`. A single global stream is forbidden: adding one draw in mobility would otherwise reshuffle the fault schedule, and reproducibility would break on an innocent refactor.
- **Content-addressed anchors.** `sid = SHA256(config || seed || decision_tick || action_history)`, `bid = (sid, action)`. Branches are identified by what produced them, so two branches can never be silently confused.

Replay reconstructs the run prefix from these and replaces only the action at the anchor. It does not snapshot process or container memory — TCP congestion state, goroutine scheduling, broker buffers and in-flight packets are not capturable, and pretending otherwise is the fastest way to lose a reviewer.

## Deployment

`docker compose up` must bring up a working system on one machine. Kubernetes is optional and only for the largest scalability points. The reproducibility pipeline must never require a cluster.
