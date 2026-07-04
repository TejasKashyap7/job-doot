# Job Hunter — Pi Deployment Runbook

Single source of truth for moving this project from your Mac to your Raspberry Pi 5 and exposing it at `https://jobs.marutsut.me` via Cloudflare Tunnel. Read top to bottom; do each step in order.

Throughout this doc:
- `<pi-host>` = the Pi's hostname or IP (e.g. `pifive.local` or `192.168.1.42`)
- `<user>` = your Pi user account name (likely `tejas` or `pi`)
- `<tunnel-name>` = the existing cloudflared tunnel name on the Pi (find with `cloudflared tunnel list`)

---

## 0. One-time prereqs on the Pi

You said Docker and Cloudflare Tunnel are already up on the Pi (running `pifive.marutsut.me`). Verify:

```bash
ssh <user>@<pi-host>
docker version
docker compose version
cloudflared --version
ls ~/.cloudflared/   # config.yml + a tunnel JSON should exist
```

If any of those are missing, install them before proceeding. We are NOT installing conda on the Pi — everything runs in Docker on production.

---

## 1. Build images on Mac first (Stage 4)

Before pushing to Pi, confirm the stack builds and runs locally:

```bash
cd /Users/tejas/Documents/job-doot
docker compose build           # ~3–5 min first time (Tectonic download)
docker compose up -d
docker compose ps              # both containers should say "Up"
curl http://localhost:8080/health         # → {"status":"ok"}
docker compose logs --tail=50 backend     # look for "Scheduler started"
docker compose logs --tail=20 gmail-watcher  # look for "poll: ..."
docker compose down
```

If everything passes locally, you know the images are good. Now move to the Pi.

---

## 2. Copy project to Pi

From your Mac:

```bash
# Code + dummy data + master resume + Dockerfiles. Excludes runtime + secrets.
rsync -avz --delete \
  --exclude='.venv/' \
  --exclude='.git/' \
  --exclude='data/' \
  --exclude='backend/pdfs/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  /Users/tejas/Documents/job-doot/ \
  <user>@<pi-host>:/home/<user>/job-doot/
```

Then copy secrets separately so they only travel once and you can verify each:

```bash
# Pre-create data/ on Pi
ssh <user>@<pi-host> "mkdir -p /home/<user>/job-doot/data /home/<user>/job-doot/backend/pdfs"

# .env, OAuth credentials, OAuth token (token.json was generated on Mac — fully portable)
scp /Users/tejas/Documents/job-doot/.env \
    /Users/tejas/Documents/job-doot/data/credentials.json \
    /Users/tejas/Documents/job-doot/data/token.json \
    <user>@<pi-host>:/home/<user>/job-doot/data/

# Move .env up one level (it lives at project root, not in data/)
ssh <user>@<pi-host> "mv /home/<user>/job-doot/data/.env /home/<user>/job-doot/.env"
```

Lock down permissions on the secrets:

```bash
ssh <user>@<pi-host> "chmod 600 /home/<user>/job-doot/.env /home/<user>/job-doot/data/credentials.json /home/<user>/job-doot/data/token.json"
```

---

## 3. Build and start on Pi

```bash
ssh <user>@<pi-host>
cd /home/<user>/job-doot
docker compose build         # First time: ~10–15 min on Pi 5 (ARM build + Tectonic)
docker compose up -d
docker compose ps            # both should say "Up (healthy)" within ~30 s
docker compose logs -f       # Ctrl+C when you've confirmed both started cleanly
```

Test health from the Pi itself:

```bash
curl http://localhost:8080/health
# → {"status":"ok"}
```

---

## 4. Cloudflare Tunnel — expose at jobs.marutsut.me

Open the existing tunnel config:

```bash
sudo nano ~/.cloudflared/config.yml
```

You'll see something like:

```yaml
tunnel: <some-uuid>
credentials-file: /home/<user>/.cloudflared/<some-uuid>.json

ingress:
  - hostname: pifive.marutsut.me
    service: http://localhost:<existing-port>
  - service: http_status:404
```

Add a `jobs.marutsut.me` rule **before** the catch-all `http_status:404`:

```yaml
ingress:
  - hostname: pifive.marutsut.me
    service: http://localhost:<existing-port>
  - hostname: jobs.marutsut.me        # ← NEW
    service: http://localhost:8080    # ← matches docker-compose backend port
  - service: http_status:404
```

Add the DNS record so Cloudflare routes the hostname to your tunnel:

```bash
cloudflared tunnel route dns <tunnel-name> jobs.marutsut.me
```

Restart the tunnel daemon:

```bash
sudo systemctl restart cloudflared
sudo systemctl status cloudflared    # active (running)
```

---

## 5. Verify end-to-end

From your **phone on cellular** (proves it's coming in via Cloudflare, not your LAN):

1. `https://jobs.marutsut.me/health` → `{"status":"ok"}` ✓
2. `https://jobs.marutsut.me/` → redirects to `/login`
3. Enter your `DASHBOARD_PASSWORD` → dashboard loads, jobs visible

Trigger a manual ingest to populate jobs from the dummy CSV:

```bash
# From your phone or laptop, after logging in (browser keeps cookie automatically)
# Or from terminal:
curl -X POST -b 'jh_session=<cookie-from-browser-devtools>' https://jobs.marutsut.me/admin/trigger-scrape
```

Or just wait for **06:00 IST** — APScheduler will tick automatically.

### Optional: verify calendar reminder loop

1. Mark any job applied (checkbox) → archive
2. Click "+ event" → set type=Interview, date=today, time=now+35 min
3. Within ~5 min, your phone gets a Telegram message via the T-30min reminder. Proves the persistent jobstore + Telegram path both work through containers.

---

## 6. Day-2 Operations

### View logs
```bash
docker compose logs -f backend
docker compose logs -f gmail-watcher
docker compose logs -f --tail=100   # both, last 100 lines
```

### Apply a code change
Once the auto-deploy poller is set up (§ 10), you no longer rsync or touch the Pi:
just `git push` to `main` and the Pi pulls, rebuilds, and restarts itself within a
few minutes, pinging you on Telegram when it's live. Manual fallback on the Pi:
```bash
cd /home/<user>/job-doot && git pull && docker compose up -d --build
```

### Backup the database
```bash
cp data/jobs.db data/jobs.db.$(date +%Y-%m-%d).bak
```

Add a weekly cron entry on the Pi (`crontab -e`):
```cron
0 4 * * 0 cd /home/<user>/job-doot && cp data/jobs.db data/jobs.db.$(date +\%F).bak && find data/ -name 'jobs.db.*.bak' -mtime +60 -delete
```

### Refresh expired Gmail token
If the watcher logs `invalid_grant` (happens after ~7 days if you didn't publish your GCP OAuth app):

```bash
# On Mac
cd /Users/tejas/Documents/job-doot
conda activate job-doot
python tools/oauth_bootstrap.py --force --test

# Push fresh token to Pi
scp data/token.json <user>@<pi-host>:/home/<user>/job-doot/data/

# Restart watcher to pick it up
ssh <user>@<pi-host> "cd /home/<user>/job-doot && docker compose restart gmail-watcher"
```

To avoid the 7-day expiry permanently: in the GCP OAuth consent screen, click **Publish app**. See `SETUP.md` § 4c.

### Check scheduler health
```bash
docker compose exec backend python -c "
from scheduler import start_scheduler
import time; s=start_scheduler(); time.sleep(1)
for j in s.get_jobs(): print(j.id, j.next_run_time)
"
```

### Restart everything cleanly
```bash
docker compose down
docker compose up -d
```

---

## 7. When the friend's real scraper arrives (Sunday)

The friend's Selenium script outputs CSV with columns `title, company, location, salary, apply_url, description`. **No `easy_apply` column** — `services/ingest.py` already defaults missing values to `False`, so this is a zero-code change.

**One-time swap:**

1. Drop his CSV at `/home/<user>/job-doot/scraped_jobs.csv` (or whatever cadence he wants — daily overwrite, or appending; either works because we dedupe on `(title, company, apply_url)` hash).
2. Edit `.env` on Pi:
   ```
   JOBS_CSV_PATH=/app/scraped_jobs.csv
   ```
3. Edit `docker-compose.yml` on Pi — replace the dummy mount line:
   ```yaml
       - ./dummy_jobs.csv:/app/dummy_jobs.csv:ro
   ```
   with:
   ```yaml
       - ./scraped_jobs.csv:/app/scraped_jobs.csv:ro
   ```
4. Restart backend:
   ```bash
   docker compose up -d --force-recreate backend
   ```
5. Manually trigger ingest to verify:
   ```bash
   curl -X POST -b '<session-cookie>' https://jobs.marutsut.me/admin/trigger-scrape
   ```
   Should return `{"inserted": <N>, "skipped": 0}` on first run.

If his scraper runs on a different machine and pushes the CSV via SSH, set up a tiny `scp` cron on his side dropping into `/home/<user>/job-doot/scraped_jobs.csv`. APScheduler will read it at 6 AM IST.

If you'd rather his scraper POST to a webhook than write a CSV, the endpoint already exists:
```
POST https://jobs.marutsut.me/webhook/jobs
Content-Type: application/json
{"jobs": [{"title": "...", "company": "...", ...}, ...]}
```

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker compose build` fails on Tectonic download | Pi can't reach github.com release CDN | Check `curl -I https://github.com`; switch DNS or retry |
| Backend container restart-loops | Missing `.env` or unreadable `data/token.json` | `docker compose logs backend`; verify file perms |
| `https://jobs.marutsut.me/` returns 502 | Cloudflare reaches tunnel but backend is down | `docker compose ps`; check backend logs |
| `https://jobs.marutsut.me/` returns 1033 | DNS not yet routed to tunnel | Re-run `cloudflared tunnel route dns ...` |
| Login form 500 errors | `SESSION_SECRET` empty in `.env` | Set it; restart backend |
| Telegram reminders never fire | APScheduler jobstore not persisting | `docker compose exec backend ls -la data/jobs.db`; confirm volume mounted |
| Watcher logs `invalid_grant` | Token expired | See § 6 "Refresh expired Gmail token" |
| PDFs don't render | Tectonic missing in image (rebuilt without it) | Rebuild: `docker compose build --no-cache backend` |
| Master resume edit on host doesn't reflect | Old image cached the file | Mount overlay should handle this; if not, `docker compose up -d --build` |

---

## 8.5 ⚠️ Self-healing scraper agent — re-enforce its sandbox BEFORE running it on the Pi

> Read this before enabling the scraper-agent (`.claude/specs/scraper-agent/`) on the Pi.
> It is easy to forget and the failure is silent.

On the Mac, the dev/auditor scraper agent runs **through Claude Code**, and Claude Code's
permission rules in `.claude/settings.local.json` are what physically stop the dev agent from
writing anywhere except the scraper modules — it cannot touch `data/` or `database/`. That
wall is enforced by the Claude Code **harness**, not by the agent's prompt.

**On the Pi, if the dev agent runs as a standalone Groq-Llama process (outside Claude Code),
that wall is GONE.** Settings rules only bind agents the Claude Code harness runs. A plain
Python process calling Groq is not bound by them, so nothing stops a confused or
prompt-injected agent from writing to `data/jobs.db` or deleting files.

**What must be done before the on-Pi agent is allowed to write code:**
- Re-implement the path restriction **in the agent's own runner code**: the program that
  applies the agent's output must check every target path against an allowlist
  (`backend/services/sources/**` only) and refuse anything touching `data/`, `database/`, or
  `.env`. Same effect as the harness deny-rules, enforced in code.
- Keep git rollback as the second net (the repo is already version-controlled — see
  SA-Flaw 7).
- Until that runner-level guard exists, run the on-Pi agent in **propose-only** mode (it
  emits a diff; a human/Claude applies it), never auto-write.

Background and the deeper concept: `.claude/specs/scraper-agent/flaws.md` (SA-Flaw 8) and
`.claude/specs/scraper-agent/concepts.md` (Concept 1 — permissions are enforced by the
harness, and a security boundary is tied to the runtime that enforces it; change the runtime
and you can silently lose the boundary).

---

## 9. What's NOT covered here (deliberately)

- **Phase 2 — LinkedIn Easy Apply**: schema hooks exist (`Job.easy_apply`, `application_attempts` table) but no UI yet. Defer until pipeline is stable on Pi for ≥1 week.
- **HTTPS on the backend**: Cloudflare Tunnel handles TLS. Backend speaks plain HTTP on `:8000` and only Cloudflare can reach it (via the tunnel daemon's loopback connection).
- **Multi-user auth**: single hardcoded password from `.env`. You're the only user.
- **Database migrations**: schema is small and you're the only user. If the schema changes meaningfully, simplest path is `rm data/jobs.db && docker compose restart backend`. The CSV ingest will repopulate on the next scheduler tick.

---

## 10. Auto-deploy (git poller)

Replaces the rsync workflow. The Pi becomes a **git clone** of the private repo and runs a small script on a cron timer that pulls, rebuilds, and restarts itself when `main` changes. **Deploying = `git push` to `main`.** No SSH, no manual steps.

**How it works (Pi-local script `~/job-doot-deploy.sh`, cron every 3 min):**
1. `git fetch` — if `origin/main` is unchanged, exit (the common case, costs nothing).
2. New commit → `git reset --hard origin/main` (the Pi never carries local commits; Pi-only config lives in `docker-compose.override.yml`, which is gitignored).
3. `docker compose build` — **if build fails, roll back to the previous commit and keep the old containers running.** A broken push can't take the site down.
4. `docker compose up -d` — swap to the new version.
5. Poll `http://localhost:8080/health` for ~60s. Healthy → Telegram "✅ deployed". Unhealthy → **auto-rollback** to the previous commit + rebuild, Telegram "⚠️ rolled back".

**Guarantees / notes:**
- Only *code* moves. `.env`, `data/`, `credentials.json`, `token.json` are gitignored and live on volumes — never touched by a deploy. The DB self-migrates on backend startup (`database/db.py::_ensure_columns`), so schema changes apply with no manual step.
- A `flock` lock means overlapping cron ticks skip instead of stacking builds.
- Read access to the private repo is via a **read-only deploy key** (SSH), scoped to this repo only.
- `main` = what's live. Push WIP to other branches freely; merge to `main` to deploy.
- One-time setup is done by the Pi's own Claude Code — see the setup prompt kept alongside this project.
