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
```bash
# Edit on Mac, rsync up (same command as Step 2), then on Pi:
docker compose up -d --build
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

## 9. What's NOT covered here (deliberately)

- **Phase 2 — LinkedIn Easy Apply**: schema hooks exist (`Job.easy_apply`, `application_attempts` table) but no UI yet. Defer until pipeline is stable on Pi for ≥1 week.
- **HTTPS on the backend**: Cloudflare Tunnel handles TLS. Backend speaks plain HTTP on `:8000` and only Cloudflare can reach it (via the tunnel daemon's loopback connection).
- **Multi-user auth**: single hardcoded password from `.env`. You're the only user.
- **Database migrations**: schema is small and you're the only user. If the schema changes meaningfully, simplest path is `rm data/jobs.db && docker compose restart backend`. The CSV ingest will repopulate on the next scheduler tick.
