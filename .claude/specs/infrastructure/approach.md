# Infrastructure — Approach

## Status
DEPLOYED — live at `jobs.marutsut.me` on the Pi since 2026-07-04. Local Mac dev still
uses conda directly. Deploys are hands-free via the auto-deploy poller (see below).

## Overview
Two Docker containers sharing one SQLite database file via a named volume.
Local Mac development uses conda directly (no Docker needed). Pi runs Docker.

## Containers

### backend
- Image base: `python:3.11-slim`
- Runs: FastAPI app + APScheduler (single process, uvicorn)
- Port: 8765 (mapped to host)
- Mounts: `jobs_data` volume at `/app/data`
- Tectonic binary: fetched directly in Dockerfile (not pip)
- PDF output: `backend/pdfs/` (inside container, persisted via volume or bind mount)

### gmail-watcher
- Image base: `python:3.11-slim`
- Runs: `watcher.py` as a plain Python process (no web server)
- Mounts: same `jobs_data` volume at `/app/data` (shares DB + token.json)
- No exposed ports

## Database
- Single SQLite file: `data/jobs.db`
- WAL mode enabled — allows one writer + multiple concurrent readers without locking
- Both containers share it via Docker named volume `jobs_data`
- APScheduler also persists its job store in the same file (`apscheduler_jobs` table)
- Schema created by `init_db()` on backend startup — safe to run repeatedly (CREATE IF NOT EXISTS)

## Local dev (Mac)
```bash
conda activate job-doot
cd /Users/tejas/Documents/personal-projects/job-doot/backend
set -a && source ../.env && set +a
export DATABASE_URL=sqlite:////Users/tejas/Documents/personal-projects/job-doot/data/jobs.db
export JOBS_CSV_PATH=/Users/tejas/Documents/personal-projects/job-doot/dummy_jobs.csv
export PDFS_DIR=/Users/tejas/Documents/personal-projects/job-doot/backend/pdfs
uvicorn main:app --host 127.0.0.1 --port 8765
```
The `/app/...` paths in `.env` are container-only. Local overrides above take precedence.

## Conda env (Mac dev)
- Name: `job-doot`, Python 3.11
- All Python deps: `pip install -r requirements.txt` (one canonical file)
- Native binaries via conda-forge: `tectonic`
- Never use system `python3` or `pip` — always use env binary explicitly

## Scheduler
- APScheduler BackgroundScheduler, timezone `Asia/Kolkata`
- Daily scrape job: 06:00 IST (configurable via `SCRAPE_HOUR` / `SCRAPE_MINUTE` env vars)
- Calendar reminder jobs: persisted in `apscheduler_jobs` table, survive backend restarts
- Starts on FastAPI lifespan startup, shuts down gracefully on app shutdown

## Pi deployment (LIVE since 2026-07-04)
- Pi OS Bookworm, Python 3.11 (matches Docker base). NVMe SSD, not SD card.
- Project lives at `/home/tejas/job-doot` on Pi as a **git clone** of the private repo
  (read-only deploy key). Secrets (`.env`, `data/credentials.json`, `data/token.json`)
  live only on the Pi, gitignored, chmod 600.
- Public URL: `jobs.marutsut.me` via Cloudflare Tunnel. The tunnel is **remotely managed
  via the Cloudflare API, NOT `~/.cloudflared/config.yml`** — editing config.yml is
  overridden. Coexists with the ML server (`pifive.marutsut.me`) and other subdomains.

### Auto-deploy (git poller) — deploying = `git push` to `main`
- A cron job (`*/3 * * * *`) runs `~/job-doot-deploy.sh`: git fetch → if `origin/main`
  changed, `git reset --hard` → `docker compose build` → `up -d` → poll
  `localhost:8080/health` for 60s → Telegram "✅ deployed" / "⚠️ rolled back".
- **Build-then-swap + auto-rollback**: a failed build or unhealthy start rolls back to
  the previous commit and keeps the old containers running — a bad push can't take the
  site down. `flock` prevents overlapping runs.
- The DB self-migrates on backend startup (`database/db.py::_ensure_columns`), so schema
  changes apply on redeploy with no manual step. Pushing from the Mac uses SSH host alias
  `github-tk7` (personal account, separate from the Blu Parrot work accounts).
- Full runbook: `DEPLOY.md` §10 in repo root.

### Self-service LinkedIn cookie
- The `li_at` session cookie expires every 1–2 weeks; when it does, the dashboard shows a
  red "scraper paused" banner linking to `/admin/linkedin-cookie` (login-gated). Pasting a
  fresh `li_at` there writes `data/li_cookies.json` (chmod 600) and clears the alert; the
  drip loop re-reads it on its next tick and resumes. No SSH needed.

## Environment variables (key ones)
```
DATABASE_URL          sqlite:////app/data/jobs.db
JOBS_CSV_PATH         /app/jobs.csv
PDFS_DIR              /app/pdfs
DASHBOARD_PASSWORD    <single password for web UI>
GROQ_API_KEY          <from tejaskashyap31@gmail.com Groq account>
GROQ_MODEL            llama-3.3-70b-versatile
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
GOOGLE_TOKEN_PATH     /app/data/token.json
SCHEDULER_TIMEZONE    Asia/Kolkata
SCRAPE_HOUR           6
SCRAPE_MINUTE         0
GMAIL_POLL_SEC        7200
GMAIL_MAX_RESULTS     50
```
