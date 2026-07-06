# Job-Doot — Project Roadmap

> Update this file as milestones are completed.
> Current overall progress: **75% done**

---

## Overall Progress

```
[██████████████████████░░░░░░░░]  75%
```

---

## Milestones

Each milestone unlocks the next. Complete them in order.

---

### M1 — Core AI Pipeline `25%` ✅ DONE

**What it is:** The brain of the system. Scoring, tailoring, LaTeX PDF output,
scheduler, database, dashboard, and auth are all built and locally runnable.

| Task | Status |
|------|--------|
| SQLite DB schema (Job, Resume, EmailLog, CalendarEvent) | ✅ |
| Groq client (Llama 3.3 70B) | ✅ |
| Scorer agent | ✅ |
| Critic + Improver + Tailor loop | ✅ |
| Agent prompts (locked skill set) | ✅ |
| CSV ingest + SHA256 dedup | ✅ |
| APScheduler (6am IST daily cron) | ✅ |
| FastAPI backend (all routes) | ✅ |
| Dashboard + archive templates | ✅ |
| Session-cookie auth | ✅ |
| LaTeX → PDF via tectonic | ✅ |
| Telegram bot service | ✅ |
| Docker + docker-compose setup | ✅ |

---

### M2 — Real Job Scraper `+15%` → brings total to **40%** ✅ DONE

**What it is:** Replace dummy CSV with live jobs from Naukri (JSON API, no login)
and LinkedIn (dummy account cookie). Wire into scheduler. Without this, the
entire pipeline runs on fake data and cannot be validated.

| Task | Status |
|------|--------|
| Naukri JSON API scraper (9 keywords × 5 locations) | ✅ |
| LinkedIn cookie scraper (drip mode, 15–45 min intervals) | ✅ |
| `li_at` cookie saved in `data/li_cookies.json` | ✅ |
| Dedup across combos via SHA256 source_hash | ✅ |
| Freshness filter (`f_TPR=r86400` on LinkedIn) | ✅ |
| Wire scraper into `scheduler.py` (replace `load_csv`) | ✅ |
| Zero-result alert (Telegram if scraper pulls nothing) | ✅ |
| LinkedIn activity simulation (connections + likes) | ✅ |

---

### M3 — End-to-End Quality Verified `+10%` → brings total to **50%**

**What it is:** Run the full pipeline on 10–20 real scraped JDs. Read the output
PDFs by hand. Confirm the improver actually tailors content and doesn't just
return a generic resume marked "APPROVED".

| Task | Status |
|------|--------|
| Trigger scrape → score → tailor on real JDs | ❌ |
| Read output PDFs, check tailoring looks real | ❌ |
| Fix any prompt issues found during review | ❌ |

**Depends on:** M2 (scraper must be pulling real jobs)

---

### M4 — Notifications Verified `+5%` → brings total to **55%**

**What it is:** Prove the Gmail watcher → Telegram bot alert chain actually
works end-to-end. Send a test email, confirm the alert fires in Telegram.

| Task | Status |
|------|--------|
| Gmail watcher container health-check | ❌ |
| Send test email → confirm Telegram alert received | ❌ |
| Confirm correct TELEGRAM_CHAT_ID (must have messaged bot first) | ❌ |

---

### M5 — Dashboard Polish `+5%` → brings total to **60%** ✅ DONE

**What it is:** Fix the two known bugs that make the dashboard harder to use
daily. Also add visibility when Groq fails so you know why jobs aren't scored.

| Task | Status |
|------|--------|
| `/filtered` page for rejected jobs with gap reasons (Flaw 4) | ✅ |
| Fix calendar form redirect — return to originating page (Flaw 5) | ✅ |
| Show Groq error banner on dashboard when scoring fails (Flaw 9) | ✅ |

---

### M6 — Pi Deployed Live `+20%` → brings total to **65%** ✅ DONE (2026-07-04)

**What it is:** The project running on the Raspberry Pi 5 at `jobs.marutsut.me`,
accessible from anywhere via Cloudflare tunnel. The biggest milestone — the tool is
actually deployed and reachable.

| Task | Status |
|------|--------|
| Code onto Pi (fresh **git clone**, replaces rsync) | ✅ |
| Secrets on Pi (`.env`, `credentials.json`, `token.json`, chmod 600) | ✅ |
| `docker compose up -d` on Pi | ✅ |
| Cloudflare tunnel (`jobs.marutsut.me`) live | ✅ |
| Dashboard loads from phone (external, via Cloudflare) | ✅ |
| First real daily scrape on Pi | ⏳ Naukri fires 06:00 IST; LinkedIn paused pending cookie |

**Depends on:** M2 (scraper), M5 (dashboard usable)

**Delivered beyond the original plan (during deployment):**
- **Auto-deploy pipeline** — `git push` to `main` → Pi cron poller (every 3 min) pulls,
  `docker compose build`, swaps, health-checks, Telegrams the result, and auto-rolls-back
  on failure. Deploying is now hands-free. Read-only deploy key; tunnel is API-managed.
  Full detail: `DEPLOY.md` §10 and `infrastructure/approach.md`.
- **Self-service LinkedIn cookie page** — `/admin/linkedin-cookie`: paste the `li_at`
  value, it writes `data/li_cookies.json` and the scraper resumes. No SSH. The red
  "scraper paused" banner links straight to it.
- **Flaw 2 tailoring checks** shipped and live (change-ratio + JD skill-coverage badges
  + "Needs review" queue) — see Flaw 2.
- **Scheduler startup crash fixed** (persistent APScheduler jobstore could not pickle a
  lambda) — the app now boots cleanly on the Pi.

---

### M7 — Ops Hardening `+10%` → brings total to **75%** ✅ DONE (2026-07-06)

**What it is:** Make sure you know when things break, and that a dead drive
doesn't destroy months of data.

| Task | Status |
|------|--------|
| Daily Telegram heartbeat: backend + collection/scoring + LinkedIn + watcher status; silence = alarm (Flaws 3/6/14/15) | ✅ |
| Off-site backup: monthly safe DB snapshot → private repo `job-doot-backup` (Flaws 7 & 16) | ✅ |
| Verify backup actually restores (restore test: 33 rows, integrity ok) | ✅ |

**Depends on:** M6 (Pi must be deployed first)

---

### M8 — Market Insights Page `+10%` → brings total to **100%**

**What it is:** Charts showing which skills, roles, and salary ranges dominate
the jobs you've been pulling. Only useful once you have weeks of real data.

| Task | Status |
|------|--------|
| Decide data retention window (Flaw 8) | ✅ (180-day rolling window) |
| Add minimum-data guard (hide charts if < N jobs) (Flaw 10) | ✅ (accepted as non-issue) |
| Build `/insights` route + template with charts | ❌ |
| **Skills-edge dashboard**: compare JD-demanded skills/certs (from scraped jobs) against LOCKED_SKILL_SET — show (a) which of Tejas's skills are rare-but-demanded (his EDGE), (b) which demanded skills/certs he lacks (gaps worth learning), ranked by frequency × salary signal | ❌ |

**Depends on:** M6 (need real data from Pi runs)

---

## Phase 2 — Data Reliability & Self-Healing

The reliability layer for the scraping pipeline — designed in
`.claude/specs/scraper-agent/`, not yet built. Order matters: **sources first**
(boring, high-ROI), the **self-healing agent second** (fancier, later). Weighted
separately from the Phase-1 100%.

### M9 — Multi-source "Spies" (data resilience)
**What it is:** ≥3 independent job sources so one break is a degraded day, not a
blackout. Each source = its own module, own health state, own repair lane.

| Task | Status |
|------|--------|
| LinkedIn spy — cookie drip, paced + active-hours | ✅ live |
| A no-captcha API spy (e.g. **Adzuna** — free, India coverage, built for programmatic use) | ❌ |
| Naukri via browser automation (Playwright/Selenium + stealth) OR drop it for the API | ❌ |
| Per-source isolation — one source's break/repair never blocks the others | ❌ |

**Depends on:** M6. **Higher priority than M10** — the spec says so outright.

### M10 — Self-Healing Scraper Duo (Developer + Auditor)
**What it is:** the adversarial repair agent — **Developer** rewrites a broken parser,
an independent **Auditor** judges it cold (asymmetric context), auto-commits on pass,
escalates bot-walls/cookie-expiry, and evolves via a curated lessons store. Full design
+ 28-flaw pre-mortem in `.claude/specs/scraper-agent/`.

| Task | Status |
|------|--------|
| Golden-record schema + canary queries (the oracle) | ❌ |
| Sensor (failure classifier) + class routing | ❌ |
| Developer agent (scoped write to `services/sources/**` only) | ❌ |
| Auditor agent (fresh context, per-field, canary cross-check) | ❌ |
| Escalation report + Telegram + lessons store + human curation gate | ❌ |
| Close the 17 open SA-flaws (`scraper-agent/flaws.md`) — many close only by building + measuring | ❌ |

**Depends on:** M9 (needs ≥1 stable source + the multi-source structure first).
**Note:** does NOT fix bot-walls (recaptcha) — those escalate to a browser spy in M9.

### M11 — LinkedIn Easy Apply automation (deferred)
Schema hooks already exist (`Job.easy_apply`, `application_attempts` table). Start only
after Phase 1 is stable on Pi.

---

## To Discuss (parked — do not build until discussed)

### D1 — Claude-powered agents alongside Groq (dual-brain)
**Idea (2026-07-06):** Tejas has a Claude Pro subscription with spare quota and is
comfortable using it for this project. Instead of relying only on Groq free tier,
make the agent layer **provider-pluggable**: agents can run on (a) Groq key (current),
(b) Claude Code subscription (headless `claude -p` / Agent SDK / subagents feature),
or (c) a Claude API key. Likely shape: Groq stays the high-volume workhorse
(first-pass scoring of every scraped JD), Claude handles the low-volume high-value
work (final evaluation + resume tailoring for shortlisted jobs, possibly with a
compile-and-inspect loop). Fall back to Groq if Claude quota/token fails.

**Known facts so far (verified 2026-07-06, re-verify before building):**
- Subscription CANNOT be used as a raw API key (Messages API needs paid credits).
- Headless path: `claude setup-token` on the Mac → long-lived OAuth token →
  `CLAUDE_CODE_OAUTH_TOKEN` on the Pi → scheduler shells out to `claude -p`.
  (`setup-token` has a known ARM64 bug — generate on Mac, not on Pi.)
- Claude Code CLI runs on Linux ARM64 (Pi 5 OK).
- Quota: headless runs draw on the subscription pool (5-hr windows + weekly caps);
  Anthropic appears to be moving headless/SDK use to a separate metered monthly
  credit per plan (~mid-June 2026 change; figures unconfirmed). Keep volume to a
  few calls/day = "ordinary individual usage" and within ToS spirit.

**Open questions (the "another day" list):** exact login/token provisioning flow on
the Pi, call contract (prompt in / JSON out), which agents move to Claude first,
quota budgeting + Groq fallback trigger, Agent SDK vs plain `claude -p`, cost if
moved to a paid API key instead.

### D2 — Adaptations from MadsLorentzen/ai-job-search (evaluated 2026-07-06)
Repo review found these candidate borrowings (their manual craft steps → our factory):
- **PDF compile-and-visually-inspect loop** — read the rendered PDF, check page
  count / orphaned titles / fonts, iterate (pairs naturally with D1 Claude agents).
- **Drafter–reviewer split** — fresh-context critic agent reviews tailored output.
- **Relevance-weighted cutting** — when resume overflows, cut lines scored by
  JD-relevance × uniqueness, not oldest-first.
- **Explicit scoring rubric bands** — score thresholds mapped to actions.
- **Upskill gap report** — aggregate JDs of poorly-scored jobs into a learn-next
  list (overlaps M8 skills-edge dashboard).
- ~~LinkedIn `jobs-guest` public endpoints~~ — **ruled out**: no job descriptions
  (tested earlier); cookie approach stays.

---

## Progress Tracker

| Milestone | Weight | Status | Running Total |
|-----------|--------|--------|---------------|
| M1 — Core AI Pipeline | 25% | ✅ Done | 25% |
| M2 — Scraper | 15% | ✅ Done | 40% |
| M3 — Quality Verified | 10% | ⏳ Flaw 2 tooling built; human review pending | 40% |
| M4 — Notifications | 5% | ⏳ Telegram delivery proven (deploy pings); test pending | 40% |
| M5 — Dashboard Polish | 5% | ✅ Done | 45% |
| M6 — Pi Deployed | 20% | ✅ Done | 65% |
| M7 — Ops Hardening | 10% | ✅ Done (heartbeat live + backup restore-verified, 33 rows) | 75% |
| M8 — Market Insights | 10% | ❌ Not started | 75% |

_Extra (not in original plan): auto-deploy pipeline + self-service LinkedIn cookie page — both live._

---

_Last updated: 2026-07-06_
