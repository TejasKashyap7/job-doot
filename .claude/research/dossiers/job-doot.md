---
title: Job-Doot
type: project-dossier
path: /Users/tejas/Documents/personal-projects/job-doot
deployed: jobs.marutsut.me (planned)
tags: [groq, fastapi, sqlite, latex, multi-agent, scraping, telegram, docker]
---

# Job-Doot — Full Dossier

## TL;DR

Job-Doot is Tejas's personal AI job-hunting pipeline: it scrapes AI/ML job listings daily from Naukri (JSON API, 45 keyword×location combos) and LinkedIn (cookie-auth drip scraper, one search every 15–45 min with human-like activity simulation), scores each JD 0–10 against his profile with a [[groq]] llama-3.3-70b-versatile scorer agent, tailors a LaTeX resume per qualifying job via a critic↔improver [[multi-agent]] loop bounded by a hallucination-proof LOCKED_SKILL_SET, compiles PDFs with [[tectonic]], serves a password-protected [[fastapi]] dashboard, and alerts via [[telegram-bot]] when a separate [[gmail-api]] watcher container classifies a recruiter reply as real. Two [[docker]] containers share one [[sqlite]] WAL database. Runs locally on Mac today; Pi 5 deployment behind a [[cloudflare-tunnel]] at jobs.marutsut.me is milestone M6. **Project is 45% complete** (M1 core pipeline, M2 scraper, M5 dashboard polish done; M3 quality verification in progress). Development is rigorously spec-driven: a weighted 8-milestone roadmap plus a 34-flaw tracker (21 resolved) under `.claude/specs/`.

## Problem & Purpose

Applying to AI/ML jobs with one generic resume wastes the candidate's strongest differentiators. Job-Doot automates the full funnel: discover fresh listings (last-24h freshness filters), reject out-of-scope roles automatically (score-0 for pure SWE/frontend/data-analyst), tailor a unique resume to each in-scope JD without fabricating anything, and surface only genuine recruiter responses (filtering spam traps and auto-rejections) to Telegram.

Constraints that shaped the design:
- **Anti-hallucination is the core requirement**: every agent references a single immutable `LOCKED_SKILL_SET`; the improver must mark a gap `UNFIXABLE` rather than invent skills/projects/metrics.
- **Free-tier economics**: Groq free tier (~30 req/min, ~14k tokens/min) dictates 3s scorer delays and 2s loop delays.
- **Pi 5 target**: SQLite (not Postgres), tectonic static binary (not TeX Live), 2 lightweight containers, SD-card wear awareness.
- **Stealth scraping**: no Selenium/headless browser; plain HTTP with cookie auth, randomized drip intervals, simulated LinkedIn activity (connections + likes) to keep the dummy account alive.

Originally a friend's Selenium scraper was to supply CSVs (Apify was removed earlier); the friend never delivered (Scraper-FLAW-5), so the in-house Naukri+LinkedIn scraper was built — CSV ingest remains as a fallback path (`dummy_jobs.csv`, 10 sample rows including a deliberate out-of-scope Razorpay frontend role to test the scorer).

## Architecture

Two containers, one shared SQLite WAL database, one daily cron plus a continuous drip thread.

```
                 ┌─────────────────────────────────────────────────────┐
                 │                jobhunter-backend (8080→8000)        │
                 │                                                     │
  Naukri JSON ──►│  [[apscheduler]] 06:00 IST daily:                   │
  API (45 combos)│   scrape_naukri → score_pending → tailor_pending    │
                 │                                                     │
  LinkedIn ─────►│  daemon thread: linkedin_drip_loop                  │
  (li_at cookie) │   every 15–45 min: search → fetch → ingest →        │
                 │   score → tailor (inline, per job)                  │
                 │                                                     │
                 │  activity sim (cron @00:01 schedules random times): │
                 │   0–2 connection invites 9am–1pm IST                │
                 │   0–2 post likes 6pm–9pm IST                        │
                 │                                                     │
                 │  AGENT LOOP (per job ≥6):                           │
                 │   master_resume.tex → critic ↔ improver (≤3 rounds) │
                 │   → tectonic → /app/pdfs/{job_id}.pdf               │
                 │                                                     │
                 │  FastAPI dashboard (/, /archive, /filtered, /login) │
                 │  + admin endpoints + /webhook/jobs (Bearer)         │
                 └────────────┬────────────────────────────────────────┘
                              │  data/jobs.db  (SQLite, WAL mode)
                 ┌────────────┴────────────────────────────────────────┐
                 │           jobhunter-gmail (gmail-watcher)           │
                 │  poll Gmail every 2h (GMAIL_POLL_SEC=7200 default)  │
                 │  → Groq EMAIL_CLASSIFIER →                          │
                 │    REAL_RESPONSE → Telegram alert (+retry_unalerted)│
                 │    SPAM_TRAP / AUTO_REJECTION → mark read           │
                 │    NEUTRAL → skip logging                           │
                 └─────────────────────────────────────────────────────┘
                              │
                       Telegram bot DM (alerts, calendar reminders,
                       scrape-failure / cookie-expiry warnings)
```

Data flow per job: `scraped → (score 0: rejected | score <6: filtered_out | ≥6: scored) → tailoring → ready | review_needed → applied`. Eight statuses total (incl. all branches). Crash-recovery: app lifespan resets stuck `tailoring` rows back to `scored` on startup (Tailoring-FLAW-2 resolution).

Key architecture decisions (documented in specs, verified in code):
- **Why [[groq]]**: free tier covers the daily batch (~3–4 min of scoring); fast structured-JSON inference (SETUP.md:9-19).
- **Why [[sqlite]] WAL**: one writer + concurrent readers across two containers without a DB server; PRAGMAs set on every connection in `backend/database/db.py:14-20` (`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`).
- **Why a separate gmail-watcher container**: OAuth/Groq crashes in the watcher cannot take down the dashboard (gmail-watcher/approach.md:11-12).
- **Why [[tectonic]]** over pdflatex/reportlab: stateless single static Rust binary, real LaTeX template the user can hand-edit, fetched directly in the Dockerfile (v0.15.0, musl builds for x86_64 and aarch64).
- **Why no Selenium**: LinkedIn blocks headless browsers; plain `requests` + dummy-account `li_at` cookie (sessions valid 1–2 weeks, expiry triggers Telegram + dashboard alert) sidesteps fingerprinting entirely (scraper/flaws.md FLAW-1/2).

## Complete Tech Stack

| Tech | Where used | Evidence |
|------|-----------|----------|
| [[python]] 3.11 | everything; conda env `job-doot`, `python:3.11-slim` base | CLAUDE.md; both Dockerfiles |
| [[fastapi]] 0.115.5 | web app, dashboard, admin & webhook routes | backend/main.py:8; requirements.txt |
| [[uvicorn]] 0.32.1 | ASGI server | backend/Dockerfile:31 CMD |
| [[jinja2]] 3.1.4 | dashboard templates | backend/main.py:11; backend/templates/ |
| [[sqlalchemy]] 2.0.36 | ORM, 5 tables + APScheduler jobstore | backend/database/db.py:2, models.py |
| [[sqlite]] (WAL) | single shared DB `data/jobs.db` | backend/database/db.py:14-20 |
| [[groq]] SDK 0.13.0 | llama-3.3-70b-versatile for all 4 agents | backend/services/groq_client.py:19,23 |
| [[apscheduler]] 3.10.4 | 06:00 IST daily pipeline, activity sim, calendar reminders; SQLAlchemyJobStore | backend/scheduler.py:4-6,42-48 |
| [[requests]] 2.32.3 | Naukri/LinkedIn scraping, Telegram HTTP | backend/services/scraper.py:20 |
| [[beautifulsoup4]] 4.12.3 + lxml 5.2.2 | LinkedIn HTML parsing | backend/services/scraper.py:21 |
| [[itsdangerous]] 2.2.0 | signed session cookie `jh_session` | backend/services/auth.py:15 |
| python-multipart 0.0.18 | login form POST parsing | requirements.txt:15 |
| [[gmail-api]] / [[google-calendar-api]] (google-api-python-client 2.151.0, google-auth 2.36.0, google-auth-oauthlib 1.2.1) | watcher polling, interview calendar events, OAuth bootstrap | gmail-watcher/watcher.py:19; backend/services/calendar_service.py:31; tools/oauth_bootstrap.py:24 |
| [[telegram-bot]] (raw HTTP API) | alerts: real responses, scrape failures, cookie expiry, calendar reminders | backend/services/telegram.py; gmail-watcher/watcher.py |
| [[telethon]] 1.36.0 | one-off Telegram channel/DM cleanup tools | tools/telegram_cleanup.py:28 |
| [[tectonic]] 0.15.0 | LaTeX→PDF compile, 120s timeout | backend/services/latex_compiler.py:44-50; backend/Dockerfile |
| [[latex]] | master_resume.tex source of truth | backend/master_resume.tex |
| [[docker]] + docker-compose | 2 services, healthcheck, shared `./data` volume | docker-compose.yml |
| [[cloudflare-tunnel]] | planned TLS ingress jobs.marutsut.me → :8080 | DEPLOY.md Stage 4 |
| pytz 2024.2 | Asia/Kolkata timezone math | requirements.txt:32 |

## Agent Loop Detail

Four Groq agents, all on `llama-3.3-70b-versatile` (env-overridable `GROQ_MODEL`, groq_client.py:23), all sourcing the same `LOCKED_SKILL_SET` from `backend/agents/prompts.py:7-13` ("single source of truth" per the module docstring).

**LOCKED_SKILL_SET contents** (verified, prompts.py:7-13): Languages C++/Python; Frameworks FastAPI, Docker, Git, Cloudflare Tunnel, Linux shell, VS Code, Colab, Kaggle, Android Studio, Roboflow, Render, GitHub; ML/DL TensorFlow, Keras, PyTorch, Scikit-learn, Matplotlib; Domains ML/DL/CV/GenAI/RAG/Vector DBs/Source-Grounded QA/Hallucination Mitigation/Idempotent Data Pipelines/YOLOv5 object detection/CNN design; Hardware Raspberry Pi 5, real-time inference, edge deployment; Other published research, client-facing iteration, data annotation/curation. (Note: M3 work plans to rewrite this from the dossier sweep — another workstream.)

**1. Scorer** (`agents/scorer.py`, SCORER_SYSTEM at prompts.py:16-49):
- Candidate profile baked into the system prompt: B.Tech CSE Bennett University 2022–2026 CGPA 7.92, AI Engineer Intern at [[bluparrot]] (Feb 2026–), ICSRF 2025 published researcher, live ML server marutsut.me (6+ models, <150ms latency), RAG over 1300+ YouTube videos ([[lens]]). Explicit instruction: "NEVER describe experience as student projects."
- In-scope: AI/ML/DL/CV/GenAI/LLM Engineer, light MLOps, AI Research. Out-of-scope (score 0 regardless): pure SWE, frontend, backend web dev, data analyst, Android dev, DevOps-without-ML.
- Rubric 0–10; JSON-only output `{score, top_matches[3], top_gaps[3], domain_flag}`. Temperature 0.1, max_tokens 512.
- Score clamped `max(0.0, min(10.0, score))` (scorer.py:49, Scoring-FLAW-3 fix). Thresholds: 0→`rejected`, <6→`filtered_out`, ≥6→`scored`. 3s sleep between jobs (SCORER_DELAY_SEC, scorer.py:23). Batch errors fire a Telegram alert + persistent dashboard banner (FLAW-9 fix).

**2. Critic** (`agents/critic.py`, CRITIC_SYSTEM prompts.py:52-70): "brutally honest senior technical recruiter," finds shortcomings only, never rewrites. Checks missing JD keywords, weak verbs, unquantified impact, irrelevant content, missing proof points, ATS issues. Max 8 shortcomings, prioritized. JSON output `{shortcomings:[{id,severity,issue}], verdict: APPROVED|NEEDS WORK, reason}`. Temperature 0.2, max_tokens 1500. Invalid verdicts normalize to NEEDS WORK.

**3. Improver** (`agents/improver.py`, IMPROVER_SYSTEM prompts.py:73-93). Absolute rules: only LOCKED_SKILL_SET skills; never invent projects/experience/tools/metrics; never change dates/companies/institutions; may reorder, strengthen verbs, surface implicit skills; output must be compilable LaTeX in the same template. **Output is delimiter-based, not JSON** (deliberate — 6000-token LaTeX bodies break JSON escaping): `LATEX_START/END`, `CHANGELOG_START/END`, `UNFIXABLE: [...]|none`, parsed via DOTALL regex (improver.py:24-26). Parse failure falls back to the previous LaTeX; stray ```latex fences are stripped. Temperature 0.3, max_tokens 6000.

**4. Email classifier** (EMAIL_CLASSIFIER_SYSTEM prompts.py:96-112, used by the watcher): REAL_RESPONSE / SPAM_TRAP / AUTO_REJECTION / NEUTRAL with confidence + reason; spam red flags include "pay to get hired" and naukri/shine/timesjobs patterns. Temperature 0.1, max_tokens 200.

**Tailor loop** (`agents/tailor_loop.py`): MAX_ROUNDS=3, INTER_CALL_DELAY=2s. Round 1 critic reviews the untouched master resume; APPROVED → compile and `ready`. NEEDS WORK → improver rewrites → critic re-reviews; on round 3 the improver is skipped and the latest LaTeX compiles anyway with status `review_needed` (human-in-the-loop fallback rather than infinite loop). Early exit if improver returns LaTeX identical to the previous round (Tailoring-FLAW-4 — saves wasted Groq calls). Compile failure (LatexCompileError) → `review_needed` with the error appended to `unfixable_items`. Each run persists a `Resume` row: latex_content, pdf_path, iteration_count, critic_verdict, changelog, unfixable_items. Batch `tailor_pending` processes `scored` jobs ordered score DESC.

**Failure modes handled**: Groq RateLimitError/APIError → exponential backoff 4→8→16→32→60s, 5 attempts (groq_client.py); missing master_resume.tex → startup warning + job reset to `scored`; crash mid-tailor → startup status reset; scoring error → Telegram + banner; improver parse failure → previous LaTeX retained.

## Scraper Detail

All in `backend/services/scraper.py` (~490 lines).

**Naukri (batch, 06:00 IST)**
- Internal JSON API `https://www.naukri.com/jobapi/v3/search` (line 47) — no login, no CAPTCHA.
- 9 keywords ("AI Engineer", "ML Engineer", "Machine Learning Engineer", "Deep Learning Engineer", "Computer Vision Engineer", "GenAI Engineer", "LLM Engineer", "NLP Engineer", "AI Research Engineer") × 5 locations (Gurgaon, Delhi, Noida, Pune, Remote) = **45 combos** (lines 34-39, 150-155).
- Per query: `noOfResults=20`, `experienceMin=0`, `experienceMax=3`, freshness last-24h. 3 rotating Chrome User-Agents. 20s request timeout.
- Backoff: 3 retries, 5s initial, ×2 per attempt, 60s cap, triggered on HTTP 429/503 (lines 93-112). Random 2–5s sleep between combos. Batch completes in ~3–4 min, ~90 jobs/day.
- Zero-result alert: if a non-first run fetches 0 jobs → Telegram + dashboard alert (block/IP-ban canary).

**LinkedIn (continuous drip, daemon thread)**
- Dummy account; `li_at` cookie in `data/li_cookies.json` (existence noted, value never read here). Session build sets `x-restli-protocol-version: 2.0.0` headers and extracts JSESSIONID → `csrf-token` header (lines 194-226). Expiry detected via redirect-to-login or 401 → Telegram + system alert; sessions last 1–2 weeks.
- `_next_sleep()` = `random.uniform(15*60, 45*60)` → **one keyword search every 15–45 min** (line 246), keywords shuffled. Search URL uses `f_TPR=r86400` (last 24h), `location=India`, count=10; max 5 job URLs parsed per search via regex `/jobs/view/(\d+)/` with BeautifulSoup. ~24 jobs/day.
- **Inline pipeline**: each newly inserted LinkedIn job is immediately scored, and if ≥6 immediately tailored (lines 366-372) — no waiting for the 6am cron. Outer loop survives crashes (5-min sleep, restart); 1h sleep if no valid session.
- **Activity simulation** (anti-bot-detection, scheduler.py:62-67 + scraper.py:472,488): nightly cron at 00:01 IST schedules two one-shot jobs at random times — 0–2 PYMK connection invites in a random 9am–1pm slot (30–60s between invites), 0–2 feed-post likes in a random 6pm–9pm slot (20–40s between likes).

**Dedup** — `source_hash` = `sha256(f"{title}|{company}|{apply_url}|{description[:200]}")` (scraper.py:61-65, mirrored ingest.py:12-13), stored UNIQUE-indexed on `Job.source_hash`, checked before insert. The `description[:200]` component was added to fix hash collisions when apply_url is missing (Ingest-FLAW-1). Makes ingestion idempotent across the 45 overlapping Naukri combos and re-fetches.

**CSV ingest fallback** — `load_csv()` accepts flexible description column aliases (`description|job_description|jd|raw_description`, Ingest-FLAW-2 fix), word-boundary `\bremote\b` regex for remote_flag (Ingest-FLAW-3 fix), boolean coercion for easy_apply. Path from `JOBS_CSV_PATH` env (default `/app/dummy_jobs.csv`). Also `POST /webhook/jobs` accepts JSON pushes with Bearer auth.

## Database Schema

`backend/database/models.py`; engine PRAGMAs in `db.py:14-20` (WAL, synchronous=NORMAL, foreign_keys=ON). Plus an `apscheduler_jobs` table via SQLAlchemyJobStore (scheduler.py:42-44) so calendar reminders survive restarts.

**jobs** — id PK; title, company (NOT NULL); location; salary; remote_flag bool; **easy_apply bool (Phase-2 hook)**; apply_url; raw_description Text; score Float; domain_flag (in-scope/out-of-scope/borderline); top_matches JSON; top_gaps JSON; status (default 'scraped', indexed; lifecycle scraped→rejected/filtered_out/scored→tailoring→ready/review_needed→applied); date_scraped (utcnow, indexed); date_applied; **source_hash (UNIQUE, indexed)**. Cascade-delete relationships to resumes and calendar_events.

**resumes** — id PK; job_id FK (cascade, indexed); latex_content Text; pdf_path; iteration_count (default 0); critic_verdict (APPROVED/NEEDS WORK); changelog Text; unfixable_items Text; created_at.

**email_log** — id PK; gmail_msg_id (UNIQUE, indexed); sender; subject; body_snippet Text; category (indexed: REAL_RESPONSE/SPAM_TRAP/AUTO_REJECTION/NEUTRAL); confidence (high/medium/low); reason; received_at; alerted bool (default False — drives the retry_unalerted safety net). NOTE: ORM class duplicated in gmail-watcher/watcher.py with explicit "KEEP IN SYNC" comments (Gmail-FLAW-5 mitigation).

**calendar_events** — id PK; job_id FK (cascade, indexed); disguised_name (privacy: real interview details hidden behind an innocuous calendar title); real_details Text; event_time; google_event_id; created_at.

**application_attempts** — **Phase-2 placeholder** (LinkedIn Easy Apply automation, deliberately not built until Phase 1 is stable): id PK; job_id FK (cascade, indexed); attempted_at; success bool default False; failure_reason.

## Endpoints & Dashboard Pages

`backend/main.py`. Auth = signed cookie `jh_session` via itsdangerous URLSafeSerializer (SESSION_SECRET env), single password vs DASHBOARD_PASSWORD env; `require_login` dependency redirects to /login (auth.py:17,27,49-57).

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health | none | liveness `{"status":"ok"}` |
| POST | /webhook/jobs | Bearer WEBHOOK_SECRET | external job JSON push (Dashboard-FLAW-3 fix) |
| GET/POST | /login | — | password form → set signed cookie |
| POST | /logout | cookie | delete cookie |
| GET | / | login | active dashboard (statuses ready/review_needed/scored/tailoring); filters min_score (0/6/7/8/9), status, free-text q over title/company/location; score color classes ≥8 green / ≥6 yellow / grey |
| GET | /archive | login | applied jobs |
| GET | /filtered | login | rejected/filtered_out jobs with skill gaps (FLAW-4 fix) |
| POST | /jobs/{id}/applied | login | mark applied + date_applied |
| POST | /jobs/{id}/unapply | login | undo, restore ready/scored |
| POST | /jobs/{id}/calendar | login | Google Calendar event + 3 Telegram reminders; respects next_url redirect (FLAW-5 fix) |
| POST | /admin/trigger-scrape | login | run CSV ingest now |
| POST | /admin/score-pending, /admin/score-one/{id} | login | manual scoring |
| POST | /admin/tailor-pending, /admin/tailor/{id} | login | manual tailoring |
| GET | /admin/pdf/{id} | login | download latest resume PDF (latest = MAX(Resume.id) subquery, Dashboard-FLAW-4 fix) |
| GET | /admin/jobs | login | JSON job list (limit 50) |

Templates: base.html (system-alerts banner bar), login.html, dashboard.html (stats + table: Title/Company/Location/Salary/Score/Status/CV PDF/Calendar/Apply), archive.html, filtered.html; static/style.css (~17.7 KB). System alerts persisted in `data/alerts.json` via `services/alerts.py` (Groq failures, LinkedIn cookie expiry, scraper zero-results).

## Notifications (Gmail watcher + Telegram)

**gmail-watcher container** (`gmail-watcher/watcher.py`, own Dockerfile, shares only `./data`):
- Polls `is:unread in:inbox`, max 50 messages, **every 7200s = 2 hours by default** (`GMAIL_POLL_SEC`, watcher.py:31). *Conflict flag: older docs/briefs say "every 15 min" — code says 2h default; the spec (gmail-watcher/approach.md:73-74) records the change from 15 min to 2h. Code wins.* Quota impact: ~6,060 Gmail API units/day vs 1B free quota.
- Per message: dedup on gmail_msg_id against email_log; extract From/Subject/body (2000-char cap); Groq classify (temp 0.1, 200 tokens, 5-attempt exponential backoff 4→60s); NEUTRAL is not even logged; REAL_RESPONSE → Telegram DM (From + Subject + 600-char excerpt) and `alerted=True`; SPAM_TRAP/AUTO_REJECTION → Gmail mark-as-read. 2s sleep between messages.
- **`retry_unalerted()`** at the start of every poll re-sends any REAL_RESPONSE row with alerted=False — a Telegram outage can delay but never drop an alert (Gmail-FLAW-4 fix).

**Telegram** (raw bot HTTP API, `backend/services/telegram.py` + watcher): real-response alerts, scoring-failure alerts, LinkedIn-cookie-expiry alerts, Naukri zero-result alerts, and calendar interview reminders at **T-1 day 19:00 IST, T-day 08:00 IST, and T-30 min** (calendar_service.py, scheduled through the persistent APScheduler jobstore). Prerequisite Telegram noise cleanup (Notifications-FLAW-1) was executed 2026-06-09 via the Telethon tools — 215 channels left.

**Google OAuth**: `tools/oauth_bootstrap.py [--force] [--test]` runs the InstalledAppFlow consent for Gmail+Calendar scopes, writes `data/token.json` (mode 0600); --test hits getProfile and events.list. Unpublished GCP app means 7-day token expiry → weekly re-run noted in DEPLOY.md ops. Watcher dropped the unused calendar scope (Gmail-FLAW-6 fix).

## Metrics & Hard Numbers

- Progress: **45%** (M1 25 + M2 15 + M5 5; roadmap.md:4). Milestone weights: M1 25 / M2 15 / M3 10 / M4 5 / M5 5 / M6 20 / M7 10 / M8 10.
- Flaw tracker: **34 flaws, 21 resolved, 13 open** (3 critical among open: resume quality unverified, Gmail alerts unverified, Pi not deployed).
- Groq: free tier ~30 req/min, ~14k tokens/min; temps 0.1/0.2/0.3/0.1 and max_tokens 512/1500/6000/200 for scorer/critic/improver/classifier; retry backoff 4→8→16→32→60s ×5.
- Pipeline: scorer delay 3s; tailor loop max 3 rounds, 2s inter-call delay; score cutoffs 0 and 6; tectonic timeout 120s, log excerpt 3000 chars.
- Naukri: 45 combos, 20 results/query, exp 0–3 yrs, 3 retries (5s→×2→60s cap), 20s timeout, 2–5s combo sleep, ~3–4 min batch, ~90 jobs/day.
- LinkedIn: drip 15–45 min (uniform, avg ~30), ≤5 URLs/search, f_TPR=r86400, ~24 jobs/day, cookie life 1–2 weeks; activity sim 0–2 invites (9–13h IST, 30–60s gaps) + 0–2 likes (18–21h IST, 20–40s gaps), rescheduled 00:01 IST.
- Throughput estimate: ~114 jobs/day total, ~35% score ≥6, ~25 tailored/day → 1000+ jobs in DB within week 1 (insights become statistically sound by week 2).
- Watcher: 2h poll, 50 msgs max, 2000-char body cap, 600-char alert excerpt, 2s per-message sleep, ~6,060 Gmail units/day (0.0006% of quota).
- Schedules: scrape 06:00 IST (SCRAPE_HOUR/SCRAPE_MINUTE env); planned cleanup Sundays 02:00 IST; monthly VACUUM first Sunday; calendar reminders T-1d 19:00 / T-day 08:00 / T-30min.
- Storage projections: ~120MB DB + ~195MB LaTeX + ~1.1GB PDFs + ~11MB email log ≈ **1.4GB/year**; retention policy: applied jobs forever, non-applied 90 days, filtered/rejected 30 days, email_log 60 days; insights window **180 days rolling** (FLAW-8 decision).
- Docker: backend port 8080→8000, healthcheck /health every 30s (5s timeout, 3 retries), restart unless-stopped; build ~3–5 min Mac, ~10–15 min Pi 5; tectonic 0.15.0.
- dummy_jobs.csv: 10 rows, salaries 14–50 LPA, one deliberate out-of-scope row.

## Deployment Plan

Target: [[raspberry-pi]] 5 at `/home/<user>/job-doot`, public via [[cloudflare-tunnel]] at **jobs.marutsut.me** (sibling of the existing pifive.marutsut.me ML server). Full runbook in `/Users/tejas/Documents/personal-projects/job-doot/DEPLOY.md`:

1. Prereqs on Pi: Docker, docker-compose, cloudflared (already installed for the ML server).
2. Build & verify on Mac first: `docker compose build && up -d`, `curl localhost:8080/health`.
3. `rsync` code (excluding .venv/.git/data/pdfs/__pycache__); `scp` secrets separately (.env, credentials.json, token.json).
4. Build on Pi (10–15 min); add ingress rule `jobs.marutsut.me → localhost:8080` to `~/.cloudflared/config.yml`; `cloudflared tunnel route dns`; restart tunnel. Backend itself speaks plain HTTP — Cloudflare terminates TLS.
5. Verify from phone on cellular: /health + login; optional calendar T-30 reminder test.
6. Day-2 ops cheatsheet: `docker compose logs -f`, weekly DB backup cron (Sunday 04:00), OAuth refresh via `oauth_bootstrap.py --force`, schema changes = drop jobs.db and re-ingest (no migrations).
7. Stage 7 (legacy): friend's-scraper CSV swap-in instructions retained, though the in-house scraper has superseded it.

Blockers before M6 (per roadmap + flaw tracker): M3 PDF quality approval (human gate — Tejas must personally read 3–5 PDFs), M4 end-to-end email→Telegram test, Docker E2E on Mac. M7 afterwards: health monitoring (15-min ping) + SD-card wear mitigation (USB SSD or nightly rsync). M8: market-insights charts over the 180-day window.

## Spec-Driven Development Evidence

The `.claude/specs/` tree is the governing artifact set — unusually mature for a personal project:
- **roadmap.md**: 8 weighted milestones summing to 100%, explicit dependency gating (M2/M4/M5 block M6; M6 blocks M7/M8), live progress figure (45%).
- **flaw.md + 10 subsystem flaws.md files** (scraper, gmail-watcher, infrastructure, scoring, resume-tailoring, dashboard, ingest, notifications, market-insights, storage-management, telegram-cleanup): every flaw has Explanation → Example → Options A/B/C → Decision → Resolution. 34 tracked, 21 resolved. Per memory note, **flaw resolution ownership stays with Tejas** — flaws are presented with options and wait for his decision; nothing is auto-resolved.
- **approach.md per subsystem**: design rationale with data flows and constraints (e.g., scraper/approach.md specifies the drip math, backoff, and JSESSIONID handling before code existed).
- **Human quality gates**: FLAW-2/Tailoring-FLAW-1 hard-block deployment until Tejas manually reads output PDFs; a pre-go-live checklist lives at resume-tailoring/approach.md:71-119.
- **Research checkpoints**: `.claude/research/CHECKPOINT.md` documents the M3 dossier sweep (6 background agents across all projects) whose purpose is to rewrite LOCKED_SKILL_SET and master_resume.tex from code-verified facts; this dossier library (Obsidian vault with frontmatter + wikilinks) is itself part of that workflow.
- **Decisions recorded as resolutions**: 180-day insights window (FLAW-8), dummy-LinkedIn-account strategy (Scraper-FLAW-1), accepted-risk closures (combo duplicates, WAL contention).
- `pipeline-diagram.excalidraw` at repo root: "Job Hunter — Data Pipeline" visual (Naukri/LinkedIn → ingest → score → tailor → PDF).

## Neighboring Projects in /Users/tejas/Documents/personal-projects

- **job-doot** — this project.
- **vapi** — voice-AI agent project ([[vapi]]); already covered by its own dossier in this library, not re-analyzed here.

(No other directories exist in the parent folder. Other Tejas projects — [[bluparrot]], [[lens]], [[ekantik]], [[smart-agri]], [[federated-learning]] — live elsewhere and have their own dossiers.)

## Resume Raw Material

1. Built a multi-agent resume-tailoring pipeline (scorer → critic → improver on Groq llama-3.3-70b) with a locked-skill-set constraint that makes fabrication structurally impossible — gaps are marked UNFIXABLE instead of invented. [verified-in-code]
2. Designed a bounded critique loop (max 3 rounds, early-exit on no-diff, human-review fallback status) instead of an open-ended agent conversation. [verified-in-code]
3. Reverse-engineered Naukri's internal JSON search API (v3) and scraped 45 keyword×location combos daily with rotating user agents and exponential backoff (429/503-aware, 5s→60s). [verified-in-code]
4. Built a stealth LinkedIn scraper with no browser automation: cookie-auth HTTP sessions, CSRF/JSESSIONID handling, randomized 15–45-min drip intervals, and scheduled human-mimicking activity (connections, likes) at randomized day-part times. [verified-in-code]
5. Implemented idempotent ingestion via SHA256 content hashing (title|company|url|description[:200]) with a UNIQUE index — re-running scrapers can never duplicate rows. [verified-in-code]
6. Engineered an automated LaTeX→PDF pipeline: LLM emits compilable LaTeX (delimiter-protocol output, not JSON, to survive 6k-token bodies), compiled by tectonic in a sandboxed temp dir with timeout and log-excerpt error capture. [verified-in-code]
7. Ran two Docker containers against one SQLite database safely using WAL mode + per-connection PRAGMAs, avoiding a DB server entirely on a Raspberry Pi target. [verified-in-code]
8. Built an LLM email triage daemon (REAL_RESPONSE/SPAM_TRAP/AUTO_REJECTION/NEUTRAL) over the Gmail API with an at-least-once Telegram alert guarantee (alerted-flag retry sweep each poll). [verified-in-code]
9. Designed crash-safe job lifecycle handling: startup resets stuck `tailoring` states, persistent APScheduler jobstore survives restarts, drip thread self-heals with backoff. [verified-in-code]
10. Wired a full APScheduler orchestration: 06:00 IST cron pipeline (scrape→score→tailor), nightly self-rescheduling randomized activity jobs, and per-event interview reminders (T-1d/T-day/T-30m) to Telegram. [verified-in-code]
11. Session-cookie auth from primitives (itsdangerous-signed cookie + FastAPI dependency) rather than a heavyweight auth framework, appropriate to a single-user threat model. [verified-in-code]
12. Capacity-planned for a Pi: storage projections (~1.4GB/yr), retention tiers (forever/90/60/30 days), 180-day rolling analytics window, SD-wear mitigation plan. [docs-only — M7/M8 not built]
13. Ran the project spec-first: weighted milestone roadmap with dependency gating and a 34-item flaw tracker where every fix records options considered and the decision rationale. [verified-in-docs + matching code fixes]
14. Free-tier LLM budget engineering: tuned per-agent temperature/token budgets, inter-call delays (2–3s), and exponential-backoff retries to fit Groq's 30 req/min / 14k TPM limits. [verified-in-code]
15. Privacy-aware calendar integration: interview events stored with a disguised public name and real details kept in the DB. [verified-in-code]
16. Planned zero-port-forwarding deployment: Cloudflare Tunnel ingress to a Pi 5, TLS at the edge, plain HTTP internally. [docs-only — M6 pending]

## Interview Depth

**"How do you stop the LLM from lying on the resume?"** Three mechanisms, layered: (1) a single LOCKED_SKILL_SET constant injected into scorer and improver prompts — the improver's first absolute rule is it may only use those skills; (2) the UNFIXABLE channel — the improver's output protocol has a dedicated field for shortcomings it refuses to fix, so honesty has a syntactic home instead of competing with completion pressure; (3) an adversarial critic that never rewrites (separation of duties: the finder of problems can't paper over them) plus a hard cap of 3 rounds ending in `review_needed`, i.e., a human reads anything the loop couldn't honestly satisfy. Honest caveat: quality is still formally unverified — M3's human PDF review is the open gate before going live, by design.

**"Why delimiters instead of JSON for the improver?"** A full LaTeX resume is ~6k tokens of backslashes and braces; JSON-escaping that reliably with an LLM is a known failure mode. Scorer/critic/classifier outputs are small and structured → JSON; the improver emits raw LaTeX between LATEX_START/END sentinels parsed with DOTALL regex, with fallback-to-previous on parse failure.

**"How is ingestion idempotent?"** SHA256 over title|company|apply_url|description[:200] into a UNIQUE-indexed column, checked pre-insert. The description prefix was added after discovering hash collisions on rows with missing apply_url (tracked as Ingest-FLAW-1). The 45 Naukri combos overlap heavily; correctness comes from the hash, and the ~10–15s/day of wasted duplicate API calls was an explicitly accepted trade-off.

**"Two containers, one SQLite file — isn't that a problem?"** WAL mode gives one writer + many readers; the two processes mostly write to different tables (backend: jobs/resumes; watcher: email_log), so practical contention is near zero. Documented as Infra-FLAW-1, resolved as accepted-risk with rationale. Postgres would be overkill on a Pi for ~115 rows/day.

**"How does the LinkedIn scraper avoid detection?"** No headless browser at all (fingerprinting surface gone), dummy account decoupled from the real one, drip pacing (uniform 15–45 min so intervals never repeat), last-24h freshness filter to keep requests minimal, randomized daily activity (0–2 invites, 0–2 likes in human time windows) so the account doesn't look like a pure reader, and a zero-result Telegram canary plus cookie-expiry alerts as failure detectors. ISP IP rotation every ~24h further reduces ban stickiness.

**"What breaks if Telegram is down when a recruiter replies?"** Nothing is lost: the alert flag (`alerted=False`) persists in email_log and `retry_unalerted()` re-sends at the start of every subsequent poll — at-least-once delivery.

**"What's deliberately not built?"** Phase 2 (LinkedIn Easy Apply automation) — schema hooks exist (`Job.easy_apply`, `application_attempts`) but the roadmap explicitly defers it until Phase 1 is stable on the Pi. Likewise health monitoring (M7) and analytics (M8) are sequenced behind deployment.

## Honesty Flags

Per Tejas's own exclusion list and the project's working agreement:
- **Claude-assisted (plumbing)**: SQL/SQLAlchemy model boilerplate, APScheduler wiring, BeautifulSoup parsing code, and general FastAPI/Docker scaffolding were written with heavy Claude Code assistance. He should not claim deep hand-written expertise in SQLAlchemy internals or APScheduler APIs.
- **His (architecture & design)**: the system decomposition (two containers, shared WAL SQLite), the agent-loop design (separation of critic/improver duties, round cap, UNFIXABLE protocol, locked skill set as the anti-hallucination primitive), the scraping strategy (no-browser cookie approach, drip pacing, activity simulation), the spec-driven process (roadmap weighting, flaw-tracker decision records — he personally owns every flaw resolution decision), and all product/quality gates (manual PDF approval before launch).
- **Unverified claims to avoid in interviews**: end-to-end resume quality (M3 open), the email→Telegram chain (M4 open), and anything about production operation — the system has never run on the Pi or served real traffic at jobs.marutsut.me yet. Throughput figures (~114 jobs/day, ~35% pass rate) are spec estimates, not measured production numbers.
- The dummy LinkedIn account + scraping approach sits against LinkedIn/Naukri ToS; fine to discuss as a technical design, framed as a personal-use research project.
