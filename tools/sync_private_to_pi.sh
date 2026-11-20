#!/usr/bin/env bash
# Copy the git-ignored confidential profile notes (.claude/research/private/) to the Pi
# over Tailscale SSH. Lands OUTSIDE the repo (~/profile-private/) so git pulls,
# `git reset --hard` and Docker builds on the Pi never touch it. Run from repo root.
set -euo pipefail
SRC=".claude/research/private/"
DEST="tejas@pi5:~/profile-private/"
ssh -o ConnectTimeout=8 -o HostKeyAlias=pi5.local tejas@pi5 'mkdir -p ~/profile-private && chmod 700 ~/profile-private'
rsync -av -e "ssh -o ConnectTimeout=8 -o HostKeyAlias=pi5.local" "$SRC" "$DEST"
ssh -o ConnectTimeout=8 -o HostKeyAlias=pi5.local tejas@pi5 "chmod -R go-rwx ~/profile-private && ls -la ~/profile-private"
echo "synced → $DEST"
