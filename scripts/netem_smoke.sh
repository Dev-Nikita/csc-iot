#!/usr/bin/env bash
# Apply and verify kernel impairment on the device->gateway data path only.
#
# A root qdisc shapes egress, so it goes inside the device simulator on the
# interface attached to the device-gateway network. Docker bridges live inside
# a VM on macOS/Windows, making the per-container form portable across hosts.
#
# The check that matters is the negative one: impairment must NOT appear on the
# bus or control interfaces. A run that degraded the controller's own RPC
# alongside the data plane, and reported itself as a data-plane fault
# experiment, would be wrong in a way nobody could see in the numbers.
set -euo pipefail

# netem is an egress qdisc. The measured direction is device-sim -> gateway00,
# therefore shaping gateway00's device-network interface would shape the reverse
# direction (principally TCP ACKs), not the declared data flow.
SVC="${SVC:-device-sim}"
LOSS="${LOSS:-5%}"
DELAY="${DELAY:-20ms}"
JITTER="${JITTER:-5ms}"
NETEM_SEED="${NETEM_SEED:-424242}"
INGRESS_NET="${INGRESS_NET:-csc-net-device-gateway}"
BUS_NET="${BUS_NET:-csc-net-control}"
COMPOSE="${COMPOSE:-docker compose}"
# KEEP=1 leaves the qdisc in place. The default removes it, which is right for a
# smoke test and wrong for the workflow: csc-stackstamp runs afterwards and has
# to SEE the impairment to record impairment_mode=kernel_netem. Applying it and
# tearing it down before the stamp is how a correctly impaired stack reports
# itself as application-layer.
KEEP="${KEEP:-0}"

CID="$($COMPOSE ps -q "$SVC")"
[ -n "$CID" ] || { echo "FAIL: service $SVC is not running under '$COMPOSE'"; exit 1; }

# Resolve the in-container interface for a Docker network.
#
# `ip -o link` prints the name as "eth0@if84:" -- the peer suffix and the colon
# are both part of field 2, and passing that straight to `tc` gives
# "Cannot find device". Split on @ or : and keep the first token.
iface_for_net() {
  local net="$1" mac name ip
  mac="$(docker inspect -f "{{with index .NetworkSettings.Networks \"$net\"}}{{.MacAddress}}{{end}}" "$CID" 2>/dev/null || true)"
  if [ -n "$mac" ]; then
    name="$(docker exec "$CID" sh -c \
      "ip -o link | awk -v m='$mac' 'tolower(\$0) ~ tolower(m) {split(\$2,a,/[@:]/); print a[1]; exit}'")"
    [ -n "$name" ] && { echo "$name"; return 0; }
  fi
  # Fallback: match by the container's IP on that network. Some platforms report
  # an empty MAC in the inspect output.
  ip="$(docker inspect -f "{{with index .NetworkSettings.Networks \"$net\"}}{{.IPAddress}}{{end}}" "$CID" 2>/dev/null || true)"
  [ -n "$ip" ] || return 1
  docker exec "$CID" sh -c \
    "ip -o -4 addr show | awk -v a='$ip/' '\$0 ~ a {split(\$2,b,/[@:]/); print b[1]; exit}'"
}

IF_INGRESS="$(iface_for_net "$INGRESS_NET" || true)"
IF_BUS="$(iface_for_net "$BUS_NET" || true)"
[ -n "$IF_INGRESS" ] || { echo "FAIL: cannot resolve the ingress interface in $SVC"; exit 1; }
echo "data_egress=$IF_INGRESS control_or_bus=${IF_BUS:-<none>}"
[ "$IF_INGRESS" != "${IF_BUS:-}" ] || { echo "FAIL: ingress and bus share one interface; impairment cannot be isolated"; exit 1; }

# Confirm the interface really exists before trying to shape it, so a parsing
# mistake fails here with a clear message rather than inside tc.
docker exec "$CID" ip link show "$IF_INGRESS" >/dev/null 2>&1 \
  || { echo "FAIL: resolved '$IF_INGRESS' but the container has no such device"; \
       docker exec "$CID" ip -o link | sed 's/^/    /'; exit 1; }

cleanup() {
  if [ "$KEEP" = "1" ]; then
    echo "KEEP=1: leaving the qdisc on $IF_INGRESS for the stack stamp"
    return
  fi
  docker exec "$CID" tc qdisc del dev "$IF_INGRESS" root 2>/dev/null || true
}
trap cleanup EXIT

docker exec "$CID" tc qdisc replace dev "$IF_INGRESS" root netem \
  loss "$LOSS" delay "$DELAY" "$JITTER" seed "$NETEM_SEED"
docker exec "$CID" tc qdisc show dev "$IF_INGRESS" | grep -q netem \
  || { echo "FAIL: netem not applied"; exit 1; }
if [ -n "${IF_BUS:-}" ] && docker exec "$CID" tc qdisc show dev "$IF_BUS" | grep -q netem; then
  echo "FAIL: netem leaked onto the bus interface $IF_BUS"; exit 1
fi

# Record exactly what was applied. A manifest that says "netem" without the
# parameters cannot be checked by anyone, including us in three months.
docker exec "$CID" tc qdisc show dev "$IF_INGRESS"
echo "OK: impairment confined to $IF_INGRESS in $SVC (loss=$LOSS delay=$DELAY jitter=$JITTER seed=$NETEM_SEED)"
