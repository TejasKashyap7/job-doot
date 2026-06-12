# Job Hunter — project conventions for Claude Code

These are hard rules. Don't deviate without asking.

## Python environment

- **Conda env name: `job-doot`** (Python 3.11). Created with `conda create -n job-doot python=3.11`.
- **Every Python / pip command in this project MUST run inside this env.** Use one of:
  - `source /opt/anaconda3/etc/profile.d/conda.sh && conda activate job-doot && <command>`
  - `/opt/anaconda3/envs/job-doot/bin/python <script>`
  - `/opt/anaconda3/envs/job-doot/bin/pip install <pkg>`
- Never use `python3` (resolves to system / anaconda base on this Mac), never use `pip` from outside the env. Don't create a `.venv` — conda is the source of truth.
- The `python:3.11-slim` Docker base image matches this env so behavior is identical in containers and on the Pi (Pi OS Bookworm ships Python 3.11).

## Dependency hygiene

- **One canonical file: `/Users/tejas/Documents/job-doot/requirements.txt`** at repo root.
- Both Docker images and the conda env install from this single file.
- **Any time a new library is added (`pip install <pkg>`), append a pinned line to `requirements.txt` immediately, in the same change.** Don't defer this — drift between the env and the file is the bug we're preventing.
- Use exact pins: `pkg==X.Y.Z` (not `>=`, not unpinned). Get the version from `pip show <pkg>` after install.
- Keep the file grouped by purpose with comments (web framework / database / LLM / google APIs / scheduling / HTTP) — see existing layout.
- After installing, sanity-check with: `python -c "import <pkg>"` inside the env.
- Goal: a fresh `pip install -r requirements.txt` on the Pi (or any other machine) produces an identical working environment with no surprises.

## Running things locally on Mac

Standard local-dev shell prelude (paths differ from container view):
```
conda activate job-doot
cd /Users/tejas/Documents/job-doot/backend
set -a && source ../.env && set +a
export DATABASE_URL=sqlite:////Users/tejas/Documents/job-doot/data/jobs.db
export JOBS_CSV_PATH=/Users/tejas/Documents/job-doot/dummy_jobs.csv
export PDFS_DIR=/Users/tejas/Documents/job-doot/backend/pdfs
uvicorn main:app --host 127.0.0.1 --port 8765
```

The `/app/...` paths in `.env` are container-only; locally the env vars above override.

## Repo layout (what lives where)

- `backend/` — FastAPI app (main.py, scheduler.py, agents/, services/, database/, templates/, static/, pdfs/, master_resume.tex)
- `gmail-watcher/` — separate Docker container, polls Gmail every 15 min (Sunday)
- `tools/` — one-off scripts (oauth_bootstrap.py, etc.) — run from repo root
- `data/` — runtime data: jobs.db (SQLite WAL), credentials.json, token.json. Gitignored.
- `dummy_jobs.csv` — placeholder until friend's Selenium scraper drops a real CSV here Sunday. Same column names, no pipeline change.
- `master_resume.tex` (under backend/) — source of truth, never modified by agents

## Non-Python tools (system binaries)

- **Tectonic** (LaTeX → PDF, Rust binary): installed via `conda install -c conda-forge tectonic -y` into the `job-doot` env. NOT in requirements.txt (not a pip package). The Docker image fetches the static binary directly (see `backend/Dockerfile`).
- **Docker** + **docker-compose**: required for production deploys; not needed for local agent dev.

### Rule: pip vs conda-forge
- **Python libraries** → always `pip install <pkg>` AND append pinned line to `requirements.txt`.
- **Native binaries** with no pip equivalent (tectonic, ffmpeg, etc.) → `conda install -c conda-forge <pkg>`. Track these in this section of CLAUDE.md so the install set is reproducible.

### Currently installed via conda-forge
- `tectonic` (LaTeX compiler)

## What NOT to do

- Don't add APIFY_API_KEY back — Apify is removed; scraping is via friend's Selenium script (Sunday).
- Don't modify `backend/master_resume.tex` programmatically — it's the source of truth. The improver agent reads it and writes a *copy* per job into `Resume.latex_content`.
- Don't bypass the locked skill set in `agents/prompts.py`. If a JD asks for something we don't have, the improver should mark it UNFIXABLE rather than fabricating.
- Don't commit `.env`, `data/credentials.json`, `data/token.json`, or anything in `data/*.db*`. All gitignored.
- Don't add Python deps via conda (`conda install`) — only via pip, so requirements.txt stays the single truth.

## Pi deployment

Full runbook at `DEPLOY.md` (rsync, scp secrets, build on Pi, Cloudflare tunnel ingress for `jobs.marutsut.me`, ops cheatsheet, friend-scraper swap-in instructions). Project lives at `/home/<user>/job-doot` on Pi.

## Phase 2 (deferred)

LinkedIn Easy Apply automation. Schema hooks already exist (`Job.easy_apply`, `application_attempts` table). Don't build until Phase 1 is stable on Pi.
