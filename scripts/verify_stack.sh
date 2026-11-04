#!/usr/bin/env bash
# Stamp the live stack into a SCRATCH file and compare it with the recorded one.
#
#   bash scripts/verify_stack.sh 99982ee46a1999be
#
# Written because the campaign chain verified the substrate by running
# `make stack-nats`, which overwrites experiments/manifests/reportable_stack.json
# -- the only record of what the campaign's own stack was made of. The guard
# fired correctly and destroyed the evidence needed to say what had changed. A
# check must not consume the thing it checks against.
#
# This stamps to a temporary file, prints a field-by-field comparison, and exits
# non-zero on a mismatch. It never writes the recorded stamp. Promoting a new
# stamp stays a deliberate `make stack-nats`.
set -uo pipefail
cd "$(dirname "$0")/.."

EXPECT="${1:-}"
RECORDED="${RECORDED:-experiments/manifests/reportable_stack.json}"
TMP="$(mktemp -t stackstamp.XXXXXX.json)"
trap 'rm -f "$TMP"' EXIT

COMPOSE_FILE=docker-compose.nats.yml go run ./cmd/csc-stackstamp \
  -bus nats \
  -bus-version "$(docker compose -f docker-compose.nats.yml exec -T nats nats-server -v 2>/dev/null | tr -d '\r' || echo unknown)" \
  -transport-hash "$(python3 -c 'import hashlib; print(hashlib.sha256(b"nats-core-pubsub;jetstream=false").hexdigest()[:16])')" \
  -netem-service device-sim \
  -out "$TMP" >/dev/null || { echo "FAIL: could not stamp the live stack"; exit 2; }

python3 - "$TMP" "$RECORDED" "$EXPECT" <<'PY'
import json, os, sys

live = json.load(open(sys.argv[1]))
recorded = json.load(open(sys.argv[2])) if os.path.exists(sys.argv[2]) else None
expect = sys.argv[3] or None

print(f"live stack      {live['runtime_stack_id']}  stamped {live['stamped_at']}")
if recorded:
    print(f"recorded stack  {recorded['runtime_stack_id']}  stamped "
          f"{recorded['stamped_at']}  ({sys.argv[2]})")
if expect:
    print(f"expected stack  {expect}")

scalar = ["go_version", "kernel", "bus_type", "bus_version",
          "transport_config_hash", "rpc_type", "process_topology", "netem_config"]
if recorded:
    diffs = [(k, recorded.get(k), live.get(k))
             for k in scalar if recorded.get(k) != live.get(k)]
    ri, li = recorded.get("container_images", {}), live.get("container_images", {})
    for svc in sorted(set(ri) | set(li)):
        if ri.get(svc) != li.get(svc):
            diffs.append((f"image[{svc}]", ri.get(svc), li.get(svc)))
    if diffs:
        print("\nthe substrate differs in:")
        for k, old, new in diffs:
            print(f"  {k}\n    recorded {old}\n    live     {new}")
    else:
        print("\nevery stamped field matches the recorded stamp.")

if expect and live["runtime_stack_id"] != expect:
    print(f"\nMISMATCH: the live stack is {live['runtime_stack_id']}, not {expect}.")
    print("eta_J belongs to one stack and does not transfer to another.")
    sys.exit(1)
if live.get("blockers"):
    print("\nBLOCKERS: " + "; ".join(live["blockers"]))
    sys.exit(1)
print("\nOK")
PY
