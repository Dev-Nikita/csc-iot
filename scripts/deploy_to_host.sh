#!/usr/bin/env bash
# Copy the project to a Linux host and verify it there.
#
# rsync rather than scp: it excludes what must not travel and, on a second run,
# sends only what changed. Three categories are deliberately left behind:
#
#   .git, bin, data/raw   -- rebuilt or regenerated on the far side
#   go.sum is KEPT        -- the far side may have no module proxy access, and
#                            go.sum is what lets `go mod download` verify
#   experiments/manifests/reportable_stack.json -- a stack stamp belongs to the
#                            machine that produced it. Copying one across hosts
#                            is how an eta_J gets attributed to hardware that
#                            never ran it.
set -euo pipefail

HOST="${1:-cybernord}"
DEST="${2:-~/csc-iot}"

if [[ -n "${SSH_IDENTITY:-}" ]]; then
  [[ -f "$SSH_IDENTITY" ]] || { echo "SSH_IDENTITY not found: $SSH_IDENTITY" >&2; exit 2; }
else
  for candidate in "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_ecdsa" "$HOME/.ssh/id_rsa"; do
    if [[ -f "$candidate" ]]; then
      SSH_IDENTITY="$candidate"
      break
    fi
  done
fi
[[ -n "${SSH_IDENTITY:-}" ]] || { echo "no SSH identity found; set SSH_IDENTITY=/path/to/key" >&2; exit 2; }
SSH_OPTIONS=(-o IdentitiesOnly=yes -i "$SSH_IDENTITY")

# --delete removes anything on the host that is not here, which twice destroyed
# work generated ON the host inside a synced directory: first logs/, now the
# scenario files drawn there by gen_scenarios.py. 'protect' stops the deletion
# while still transferring the copies that do live in this repo. A generated
# scenario set loses nothing by being recreated -- it is a pure function of its
# seed, and each run copies it into its own output directory -- but losing it
# mid-workflow reads as a missing file rather than as a deleted one.
echo "syncing to $HOST:$DEST"
rsync -e "ssh -o IdentitiesOnly=yes -i $SSH_IDENTITY" -avz --delete \
  --exclude '.git' \
  --exclude 'bin/' \
  --exclude 'data/raw/' \
  --exclude 'data/processed/' \
  --exclude 'logs/' \
  --exclude '_to_delete/' \
  --exclude 'experiments/manifests/reportable_stack.json' \
  --exclude 'paper/main.pdf' \
  --exclude 'paper/*.aux' --exclude 'paper/*.log' --exclude 'paper/*.fls' \
  --exclude 'paper/*.fdb_latexmk' --exclude 'paper/*.synctex.gz' \
  --exclude '.DS_Store' \
  --filter='protect configs/scenarios-*.json' \
  --filter='protect configs/budgets-*.json' \
  ./ "$HOST:$DEST/"

echo
echo "verifying on $HOST"
# Invoked through bash, not as ./: an editor, a filesystem or an rsync that
# drops the executable bit would otherwise fail the deploy with "Permission
# denied" and say nothing about what is actually wrong. The mode is also restored
# on the remote, because a script that must be executable there should not depend
# on how it travelled.
ssh "${SSH_OPTIONS[@]}" "$HOST" "cd $DEST && chmod +x scripts/*.sh 2>/dev/null; bash scripts/audit_repo.sh"

# bin/ is excluded from the sync, so a deploy that carries newer Go sources
# leaves a binary older than them. The runner catches that and says so, but only
# after the next run is attempted, which costs a round trip for something the
# deploy can simply do. The binary is a function of the sources; a deploy that
# updates one and not the other is half a deploy.
echo
echo "rebuilding the host binaries (bin/ is not synced)"
ssh "${SSH_OPTIONS[@]}" "$HOST" "cd $DEST && make build TAGS=nats" || {
  echo
  echo "the host build FAILED. The sources are synced but bin/ is stale, so the"
  echo "matrix runner will refuse to start. Fix the build on the host before"
  echo "running anything: ssh $HOST; cd $DEST; make build TAGS=nats"
  exit 2
}

echo
echo "next, on the host:"
echo "  ssh $HOST"
echo "  cd $DEST"
echo "  make deps-adapters      # if go.mod loses its requires"
echo "  make build && ./scripts/topology_smoke.sh"
echo "  make up-nats && make stack-nats && make m2prime-nats"
