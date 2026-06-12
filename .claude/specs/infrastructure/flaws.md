# Infrastructure — Flaws

---

## FLAW-1: SQLite shared between two containers — theoretical write contention
**Status: OPEN — very low risk, WAL mode handles it, documented for awareness**

**The problem:**
Both containers write to the same SQLite file via a Docker volume. WAL (Write-Ahead Log)
mode allows concurrent reads but still serialises writes. The gmail-watcher writes to
`email_log`. The backend writes to `jobs`, `resumes`, `calendar_events`. They write to
different tables, so contention is near-zero in practice — but not mathematically zero.

**Example:**
At exactly 06:00 IST, the scheduler is writing 15 new Job rows while the gmail-watcher
is mid-write on an EmailLog row. SQLite WAL serialises them — one waits microseconds
for the other. In practice: invisible. In theory: if either side sets a very short
`busy_timeout`, it could raise `OperationalError: database is locked`.

**Options:**
- **Option A — Accept it.** SQLAlchemy's default connection pool already handles this
  for the backend. The watcher uses a simple engine with no pool. Real contention in
  this write pattern is effectively impossible. No action needed.
- **Option B — Set `busy_timeout=5000` (5s) on both SQLite connections** as a safety
  net. Adds 2 lines of code, eliminates any theoretical locking error completely.
- **Option C — Migrate to PostgreSQL.** Proper multi-writer DB. Massively over-engineered
  for a single-user Pi project. Don't do this.

---

## FLAW-2: No health monitoring for the Pi — silent container death goes unnoticed
**Status: OPEN — must resolve before Pi deployment**

**The problem:**
If either Docker container crashes on the Pi (OOM kill, uvicorn segfault, OAuth failure),
nothing alerts you. You'd only find out when you try to open the dashboard and get a
connection refused, or when you notice no new jobs have appeared in days.

**Example:**
Pi kernel OOM-kills the backend container at 3am because some process used too much RAM.
Dashboard at `jobs.marutsut.me` returns 502 (Cloudflare can't reach the backend).
You're at work, not checking. You come home, open the dashboard, see it's down, SSH in
and restart. You've missed a full day of scraping, scoring, and tailoring.

**Options:**
- **Option A — Docker `restart: always` + a cron-based health ping.**
  `docker-compose.yml` already uses `restart: unless-stopped`. Add a Pi cron job that
  curls `http://localhost:8765/health` every 10 minutes and sends a Telegram/ntfy
  message if it gets a non-200 or times out. Covers the backend container.
  For gmail-watcher, add a heartbeat row written to DB each poll; a separate check
  validates it's fresh.
- **Option B — Use Docker HEALTHCHECK in both Dockerfiles.** Docker marks containers
  unhealthy after N failed checks and can auto-restart. Combined with `restart: always`
  this is mostly self-healing without external monitoring.
- **Option C — Both A and B.** Self-healing via Docker HEALTHCHECK + alert via cron
  ping. Most robust, ~30 lines total across both Dockerfiles and a cron entry.

---

## FLAW-3: Pi deployment not done yet
**Status: OPEN — Stage 5, blocked on Stage 4 (Docker E2E test on Mac)**

The full runbook is in `DEPLOY.md`. Pre-requisites before deploying to Pi:
- [ ] Scraper built and tested (scraper/flaws.md all resolved)
- [ ] Resume tailoring quality verified (resume-tailoring/flaws.md FLAW-1 resolved)
- [ ] Docker E2E test on Mac passes (both containers, full pipeline end-to-end)
- [ ] Gmail OAuth token generated (`tools/oauth_bootstrap.py` run on Mac)
- [ ] Telegram cleanup done (notifications/flaws.md FLAW-1 resolved)
- [ ] Cloudflare tunnel configured for `jobs.marutsut.me`
