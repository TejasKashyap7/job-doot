#!/usr/bin/env bash
# Auto-deploy for Vasu's PC — adapted from Tejas's Pi poller (~/job-doot-deploy.sh, not in git).
# Every few minutes: if origin/user/vasu-setup has a new commit -> pull, rebuild containers,
# health-check, roll back on failure, restart the applier if its code changed. Telegram on result.
# Install (inside WSL):  cp deploy/vasu/job-doot-deploy.sh ~/ && chmod +x ~/job-doot-deploy.sh
#                        (crontab -l 2>/dev/null; echo '*/3 * * * * $HOME/job-doot-deploy.sh >/dev/null 2>&1') | crontab -
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"   # so cron can talk to systemctl --user

REPO_DIR="$HOME/job-doot"
BRANCH="user/vasu-setup"
HEALTH_URL="http://localhost:8080/health"
LOG="$HOME/job-doot-deploy.log"

exec 9>"/tmp/job-doot-deploy.lock"
flock -n 9 || { echo "$(date '+%F %T') skip: already running" >>"$LOG"; exit 0; }

cd "$REPO_DIR"
BOT="$(grep -E '^TELEGRAM_BOT_TOKEN=' .env 2>/dev/null | cut -d= -f2-)"
CHAT="$(grep -E '^TELEGRAM_CHAT_ID=' .env 2>/dev/null | cut -d= -f2-)"
notify() {
  [ -n "${BOT:-}" ] && [ -n "${CHAT:-}" ] || return 0
  curl -fsS -X POST "https://api.telegram.org/bot${BOT}/sendMessage" \
    --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=$1" >/dev/null 2>&1 || true
}

# Never wipe work that isn't pushed yet (Vasu's Claude edits this same checkout).
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "$(date '+%F %T') skip: local uncommitted changes — commit+push them first" >>"$LOG"; exit 0
fi

git fetch --quiet origin "$BRANCH" || { echo "$(date '+%F %T') fetch failed" >>"$LOG"; exit 0; }
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse "origin/$BRANCH")"
[ "$LOCAL" = "$REMOTE" ] && exit 0
# Local commits not on GitHub yet: don't throw them away.
if ! git merge-base --is-ancestor "$LOCAL" "$REMOTE"; then
  echo "$(date '+%F %T') skip: local commits not pushed (HEAD ${LOCAL:0:7})" >>"$LOG"; exit 0
fi

SHORT="${REMOTE:0:7}"
echo "$(date '+%F %T') new commit $SHORT — deploying" >>"$LOG"
APPLIER_CHANGED="$(git diff --name-only "$LOCAL" "$REMOTE" -- applier/ requirements.txt | head -1)"
git reset --hard "origin/$BRANCH" >>"$LOG" 2>&1
MSG="$(git log -1 --pretty=%s)"

if ! docker compose build >>"$LOG" 2>&1; then
  git reset --hard "$LOCAL" >>"$LOG" 2>&1
  notify "❌ job-doot: build failed for $SHORT. Stayed on previous version."
  echo "$(date '+%F %T') build FAILED $SHORT — kept old version" >>"$LOG"; exit 1
fi

docker compose up -d >>"$LOG" 2>&1

ok=0
for _ in $(seq 1 20); do
  curl -fsS "$HEALTH_URL" >/dev/null 2>&1 && { ok=1; break; }; sleep 3
done

if [ "$ok" = 1 ]; then
  if [ -n "$APPLIER_CHANGED" ]; then
    "$HOME/.venvs/applier311/bin/pip" install -q -r requirements.txt >>"$LOG" 2>&1 || true
    systemctl --user restart applier >>"$LOG" 2>&1 || true
  fi
  notify "✅ job-doot deployed $SHORT: $MSG"; echo "$(date '+%F %T') OK $SHORT" >>"$LOG"
else
  git reset --hard "$LOCAL" >>"$LOG" 2>&1
  docker compose up -d --build >>"$LOG" 2>&1
  notify "⚠️ job-doot: $SHORT unhealthy — rolled back to ${LOCAL:0:7}."
  echo "$(date '+%F %T') UNHEALTHY $SHORT — rolled back" >>"$LOG"
fi
