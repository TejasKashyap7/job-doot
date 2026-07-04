# Job-Doot — Project Roadmap

> Update this file as milestones are completed.
> Current overall progress: **45% done**

---

## Overall Progress

```
[██████████████░░░░░░░░░░░░░░░░░░]  45%
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

### M6 — Pi Deployed Live `+20%` → brings total to **80%**

**What it is:** The project running on the Raspberry Pi 5 at `jobs.marutsut.me`,
stable, scraping daily, accessible from anywhere via Cloudflare tunnel.
This is the biggest milestone — it means the tool is actually in use.

| Task | Status |
|------|--------|
| rsync codebase to Pi | ❌ |
| scp secrets (`.env`, `credentials.json`, `token.json`) | ❌ |
| `docker compose up -d` on Pi | ❌ |
| Verify Cloudflare tunnel (`jobs.marutsut.me`) is live | ❌ |
| First real daily scrape on Pi | ❌ |
| Confirm dashboard loads from phone | ❌ |

**Depends on:** M2 (scraper), M4 (notifications verified), M5 (dashboard usable)

---

### M7 — Ops Hardening `+10%` → brings total to **90%**

**What it is:** Make sure you know when things break, and that a dead drive
doesn't destroy months of data.

| Task | Status |
|------|--------|
| Daily Telegram heartbeat: reports backend + scrape + watcher status; silence = alarm (Flaws 3 & 6, unified) | ❌ |
| Off-site backup: monthly DB snapshot to a private GitHub repo (Flaw 7) | ❌ |
| Verify backup actually restores (test it once) | ❌ |

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

## Phase 2 (deferred — do not start)

LinkedIn Easy Apply automation. Schema hooks already exist (`Job.easy_apply`,
`application_attempts` table). Start only after Phase 1 is stable on Pi.

---

## Progress Tracker

| Milestone | Weight | Status | Running Total |
|-----------|--------|--------|---------------|
| M1 — Core AI Pipeline | 25% | ✅ Done | 25% |
| M2 — Scraper | 15% | ✅ Done | 40% |
| M3 — Quality Verified | 10% | ❌ Not started | 40% |
| M4 — Notifications | 5% | ❌ Not started | 40% |
| M5 — Dashboard Polish | 5% | ✅ Done | 45% |
| M6 — Pi Deployed | 20% | ❌ Not started | 45% |
| M7 — Ops Hardening | 10% | ❌ Not started | 45% |
| M8 — Market Insights | 10% | ❌ Not started | 45% |

---

_Last updated: 2026-06-11_
