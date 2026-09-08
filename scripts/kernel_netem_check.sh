#!/usr/bin/env bash
# Does this host's container kernel actually support netem?
#
# Docker Desktop on macOS runs a LinuxKit VM. Containers are Linux, so tc works
# in principle -- but sch_netem must be present in that kernel, and it is not
# guaranteed. Better to learn this in five seconds than after a scheduled run.
set -euo pipefail
IMG="${IMG:-alpine:3.20}"
echo "kernel seen by containers: $(docker run --rm "$IMG" uname -a)"
if docker run --rm --cap-add=NET_ADMIN "$IMG" sh -c \
   'apk add --no-cache iproute2 >/dev/null 2>&1 && tc qdisc replace dev eth0 root netem loss 1% && tc qdisc show dev eth0 | grep -q netem'; then
  echo "OK: sch_netem is available and NET_ADMIN is sufficient"
else
  echo "UNAVAILABLE: this host's container kernel cannot apply netem."
  echo "Runs here must record impairment_mode=application_layer and are NOT reportable."
  exit 1
fi
