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

echo "syncing to $HOST:$DEST"
rsync -e "ssh -o IdentitiesOnly=yes -i $SSH_IDENTITY" -avz --delete \
  --exclude '.git' \
  --exclude 'bin/' \
  --exclude 'data/raw/' \
  --exclude 'data/processed/' \
  --exclude '_to_delete/' \
  --exclude 'experiments/manifests/reportable_stack.json' \
  --exclude 'paper/main.pdf' \
  --exclude 'paper/*.aux' --exclude 'paper/*.log' --exclude 'paper/*.fls' \
  --exclude 'paper/*.fdb_latexmk' --exclude 'paper/*.synctex.gz' \
  --exclude '.DS_Store' \
  ./ "$HOST:$DEST/"

echo
echo "verifying on $HOST"
ssh "${SSH_OPTIONS[@]}" "$HOST" "cd $DEST && ./scripts/audit_repo.sh"
echo
echo "next, on the host:"
echo "  ssh $HOST"
echo "  cd $DEST"
echo "  make deps-adapters      # if go.mod loses its requires"
echo "  make build && ./scripts/topology_smoke.sh"
echo "  make up-nats && make stack-nats && make m2prime-nats"
