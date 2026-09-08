# CSC completion runbook — 2026-09-05

## Verdict

The repaired epoch/watermark implementation is a substantial improvement. The
new Mac NATS anchor (`end:gw00=800`, `drained:edge00:gw00=800`) is internally
quiescent, and the identical local smoke hash on macOS and Ubuntu is useful
cross-platform diagnostic evidence. Neither result is yet reportable M2'.

The reported 48-run burn-in and 108-branch pilot are not present as raw branch
directories in the supplied archives, so their aggregate claims cannot be
independently reproduced from this delivery. Treat them as development
diagnostics, not manuscript findings.

The old stack stamp and anchor have been moved to `_quarantine`: a root qdisc on
the gateway shapes gateway egress, while the declared data direction is
device-sim to gateway. The repaired configuration shapes the device simulator's
device-network egress and verifies that its control interface is untouched.
This creates a new `runtime_stack_id`; old and new results must never be pooled.

## What this repair changes

- reportable NATS branches use a dedicated runner; the local runner now rejects
  `BUS_IMPL=nats` instead of starting a stdlib broker beside NATS;
- every reportable branch recreates NATS and every process, preventing counters,
  queues, routing and backlog from leaking between run IDs;
- `netem` has a fixed, recorded seed and acts in the forward data direction;
- action application has a run-scoped command/ack protocol; no next epoch until
  the gateway confirms that routing or admission state changed;
- anchors are append-only and their serialized structural state is rehashed by
  the Python validator;
- exact float state is hashed by IEEE-754 bits rather than rounded to six
  decimals;
- matrix completeness, stack identity, action acknowledgement and action-state
  mutation are hard failures;
- `J_m2_diag = processed - admission_backlog` is explicitly quarantined from
  the paper's lower-is-better `J_obs`;
- diagnostic dispersion now uses the frozen pairwise-Q0.95 definition and
  handles `eta=0` correctly.

## Interpret the shell errors correctly

- `fatal: not a git repository` is expected after `make deploy`: the deployment
  intentionally excludes `.git`. Git was already installed; reinstalling it
  cannot restore repository history. Use `SOURCE_REVISION`, or deploy with
  `git clone` when history is required.
- `<sha>` is a placeholder. Typed literally, `<` is shell redirection and causes
  `sha: No such file or directory`.
- `apt get` is a typo; `apt-get` is the valid command.
- a missing `.git/index.lock` is not a fault. Do not use `lsof ... || rm ...` as
  a routine preamble. If the file actually exists, first verify no Git process
  owns it, then remove that exact stale file.
- `bin/csc-orchestrator: No such file` was resolved correctly by `make build`.

## Gate 0 — validate this source on Ubuntu

Run from the directory containing `go.mod`, not merely a directory named
`csc-iot`:

```bash
cd ~/csc-iot
test -f go.mod && pwd
chmod +x scripts/*.sh analysis/*.py

gofmt -w cmd/csc-node/main.go cmd/csc-orchestrator/main.go \
  cmd/csc-act/main.go cmd/csc-stackstamp/main.go \
  cmd/csc-stackstamp/main_test.go internal/bus/action.go internal/bus/action_test.go internal/bus/bus.go \
  internal/fingerprint/fingerprint.go internal/fingerprint/fingerprint_test.go

make audit
go test -race ./...
go test -tags=nats -race ./...
go vet ./...
go vet -tags=nats ./...
python3 -m pytest intelligence/tests -q
python3 -m py_compile analysis/*.py check_reportable_stack.py
bash -n scripts/m2prime_matrix.sh scripts/m2prime_nats_matrix.sh \
  scripts/netem_smoke.sh
```

Stop on any failure and preserve the output. The current review environment did
not contain Go or Docker, so the Go compilation and live container checks must
be completed on this Ubuntu host before the patch is considered executable.

## Gate 1 — create the corrected reportable stack

```bash
make up-nats
NETEM_SEED=424242 make stack-nats
python3 check_reportable_stack.py
STACK_ID=$(python3 check_reportable_stack.py --print-stack-id)
echo "$STACK_ID"
```

Required observations:

1. output names `device-sim`, not `gateway00`, as the shaped container;
2. the device-network and control interfaces are different;
3. qdisc output includes `seed 424242`;
4. manifest has non-empty `transport_config_hash`, `netem_config`, images and
   zero blockers;
5. `reportable_stack_validated=true`.

## Gate 2 — reportable prefix burn-in (48 branches)

```bash
make build TAGS=nats
STACK_ID=$(python3 check_reportable_stack.py --print-stack-id) \
EXPERIMENT=burnin-nats-v2 ANCHORS=8 REPEATS=6 ACTIONS=NO_OP HORIZON=0 \
NETEM_SEED=424242 scripts/m2prime_nats_matrix.sh
```

Accept only if all 48 directories exist, none contains `REFUSED.txt`, every
branch stack has the same expected ID, and every anchor reports `distinct=1`.
The runner fails fast and leaves the incomplete experiment for diagnosis.

## Gate 3 — action protocol acceptance (27 branches)

```bash
STACK_ID=$(python3 check_reportable_stack.py --print-stack-id) \
EXPERIMENT=actions-nats-v2 ANCHORS=3 REPEATS=3 \
ACTIONS="NO_OP THROTTLE REROUTE" HORIZON=3 NETEM_SEED=424242 \
scripts/m2prime_nats_matrix.sh
```

Accept only if each non-NO_OP `branch.json` contains `action_ack.applied=true`,
REROUTE outcomes contain `routing[gw00/edge]=edge01`, THROTTLE outcomes contain
`rate_limits[gw00/admit]=50`, and prefix hashes remain exact. A zero REROUTE
throughput effect is expected on homogeneous edges and is not an M2 failure if
the route mutation is verified.

## Do not run M2'-900 until these two implementation gaps close

1. **Informative anchors and heterogeneous paths.** Add at least an edge service
   rate/capacity or controlled compute-load difference, plus pre-fault,
   transition and degraded anchor regions. REROUTE should change real queueing
   or latency through the environment, not through arbitrary objective weights.
2. **Full observed objective.** Persist per-branch failure indicator, normalized
   end-to-end latency and realized action cost, then compute
   `J_obs = 0.6 Y + 0.2 L_tilde + 0.2 C_obs`. Until these fields exist,
   `analysis/m2prime_report.py` is mechanics-only and cannot license D0-lite.

After those gaps are tested, run M2'-900:

```bash
STACK_ID=$(python3 check_reportable_stack.py --print-stack-id) \
EXPERIMENT=m2prime-900-v2 ANCHORS=30 REPEATS=10 \
ACTIONS="NO_OP THROTTLE REROUTE" HORIZON=3 NETEM_SEED=424242 \
scripts/m2prime_nats_matrix.sh
```

Do not assume a two-hour runtime. Recreating and stamping 900 topologies on four
vCPUs may take substantially longer; measure the 27-branch acceptance wall time
and extrapolate before starting.

## Remaining path to a complete paper

1. Implement the two M2' gaps above and pass M2'-900.
2. Run D0-lite: 10 anchors x 3 actions x 20 repeats using full `J_obs`; require
   preregistered `SNR_J >= 3`. If `eta_J=0` and signal is positive, SNR is
   positive infinity; if both are zero, the design is non-informative.
3. Only after D0-lite passes, implement real MIGRATE and REPLICATE side effects,
   including placement/routing, startup, transfer, temporary capacity and cost.
4. Run full D0: 20 x 5 x 30; freeze `eta_J` for this one runtime stack.
5. Implement F3-F7 and validate each telemetry signature; then build exhaustive
   interventional training branches and run leakage tests.
6. Train/freeze the temporal predictor, dynamic SCM, ensemble uncertainty, CRC
   threshold and MNI selector in that order. B5 is the kill test: report honestly
   if the action-conditioned associative predictor matches the SCM.
7. Add B1-B5, ablations, pilot/freeze, then the paired main experiment, shift,
   scale, statistics and autogenerated figures/tables.
8. Write Results, Abstract and the measured Conclusion only from validated
   generated artifacts. The current TODOs must remain until then.

The paper is therefore not “almost finished” experimentally. Its methodological
core is strong and now better aligned with the code, but the complete system,
full objective, five actions, scenarios, ML/control stack, baselines and main
results remain. The correct completion strategy is gated progress, not filling
the Results section from the current diagnostics.
