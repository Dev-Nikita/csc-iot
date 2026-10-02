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
  --filter='protect SOURCE_REVISION' \
  ./ "$HOST:$DEST/"

# The revision the host records for every branch it runs. It was a file kept by
# hand, last updated at protocol-0.9, and then forgotten: `git rev-parse` fails
# on the host (.git is not synced), the runner fell back to that file, and every
# manifest since 2026-09-25 recorded "protocol-0.9" as the commit that produced
# it. The measurements are unaffected; the provenance label was wrong, which is
# the one field whose whole purpose is to be right. It is now derived here, on
# every deploy, from the tree actually being sent -- never typed, never
# committed, so it cannot go stale and cannot be overwritten by an older copy.
REVISION="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
DESCRIBE="$(git describe --tags --always --dirty 2>/dev/null || echo unknown)"
if [ "$REVISION" = unknown ]; then
  echo "FAIL: cannot read a git revision for this tree, so the host would record"
  echo "      an unverifiable provenance for every branch it runs. Deploy from a"
  echo "      git checkout."
  exit 2
fi
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "note: the tree is dirty; the host will record $DESCRIBE, which says so."
fi
echo "recording SOURCE_REVISION=$REVISION on $HOST"
ssh "${SSH_OPTIONS[@]}" "$HOST" "cat > $DEST/SOURCE_REVISION" <<EOF_REV
$REVISION
# Written by scripts/deploy_to_host.sh. Line 1 is what the runner reads.
# describe: $DESCRIBE
# deployed: $(date -u +%Y-%m-%dT%H:%M:%SZ) from $(hostname -s 2>/dev/null || echo unknown)
EOF_REV

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
# bash -lc, not a bare command: a non-interactive ssh runs neither the login
# profile nor .bashrc, so a Go installed under /usr/local/go -- with its PATH set
# in a profile, as the usual tarball install does -- is simply absent. The first
# attempt reported 'go: command not found' on a host where go builds fine
# interactively, which is a PATH difference wearing the costume of a missing
# toolchain. The explicit paths are a fallback for a host whose profile does not
# set them either.
GO_PATHS='export PATH="$PATH:/usr/local/go/bin:$HOME/go/bin:/usr/lib/go/bin"'
if ! ssh "${SSH_OPTIONS[@]}" "$HOST" \
     "bash -lc '$GO_PATHS; cd $DEST && make build TAGS=nats'"; then
  echo
  if ssh "${SSH_OPTIONS[@]}" "$HOST" "bash -lc '$GO_PATHS; command -v go'" \
       >/dev/null 2>&1; then
    echo "the host build FAILED with a working Go toolchain, so this is a real"
    echo "compile error. Read it above; the sources are synced but bin/ is stale,"
    echo "and the matrix runner will refuse to start until it is rebuilt."
  else
    echo "no Go toolchain found on $HOST, even through a login shell. Install it,"
    echo "or add its bin directory to the profile, then: make build TAGS=nats"
  fi
  exit 2
fi

echo
echo "next, on the host:"
echo "  ssh $HOST"
echo "  cd $DEST"
echo "  make deps-adapters      # if go.mod loses its requires"
echo "  make build && ./scripts/topology_smoke.sh"
echo "  make up-nats && make stack-nats && make m2prime-nats"
