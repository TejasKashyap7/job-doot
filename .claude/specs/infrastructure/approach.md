# Infrastructure — Approach

## Status
BUILT (local Mac dev) | NOT DEPLOYED (Pi deployment pending)

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

## Pi deployment
- Pi OS Bookworm, Python 3.11 (matches Docker base)
- Project lives at `/home/<user>/job-doot` on Pi
- Deploy: `rsync` code + `scp` secrets (`data/credentials.json`, `data/token.json`, `.env`)
- Build on Pi: `docker-compose build && docker-compose up -d`
- Public URL: `jobs.marutsut.me` via Cloudflare Tunnel (separate tunnel from the existing
  ML inference server at `pifive.marutsut.me`)
- Full runbook: `DEPLOY.md` in repo root

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
