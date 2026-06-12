# Dashboard — Flaws

---

## FLAW-1: Score breakdown (matches, gaps, unfixable items) not visible in the UI
**Status: OPEN — low priority, does not block going live**

**The problem:**
The scorer writes `top_matches`, `top_gaps`, and `domain_flag` to each Job row, and
the tailoring loop writes `unfixable_items` to the Resume row. None of this is surfaced
in the dashboard. To see why a job scored 6.5 or what the improver couldn't fix, you
have to query the SQLite DB directly. This is fine during development but annoying
when actually using the pipeline daily.

**Example:**
A job shows score 7, status `review_needed`. You want to know: what did the critic
flag as unfixable before deciding whether to apply? You have to SSH into the Pi,
open the DB, and run a SQL query. That's too much friction for a daily-use tool.

**Options:**
- **Option A — Add an expandable detail panel per job card.** Click the score badge
  to expand: shows top_matches, top_gaps, domain_flag, and unfixable_items inline.
  No new page, no redirect — just a CSS toggle. Small JS addition.
- **Option B — Add a dedicated `/jobs/{job_id}` detail page.** Full breakdown of
  the job: score, matches, gaps, tailoring changelog, unfixable items, LaTeX diff
  between master and tailored resume. More complete but adds a route and template.
- **Option C — Accept it for now.** The dashboard is for applying, not debugging.
  Add a simple tooltip on the score badge showing top_matches only. Gaps and
  unfixable items are edge cases — look them up in the DB when actually needed.

---

## FLAW-3: /webhook/jobs endpoint has no authentication — anyone can inject jobs
**Status: RESOLVED — WEBHOOK_SECRET env var added; endpoint rejects requests without Bearer token when secret is set**

**The problem:**
`POST /webhook/jobs` accepts any JSON payload with no auth check at all. Once the
dashboard is live at `jobs.marutsut.me`, this endpoint is publicly reachable on the
internet. Anyone who discovers the URL (via scanning, shared links, etc.) can POST
arbitrary job rows directly into the database. Those fake jobs will be scored, tailored,
and appear on your dashboard wasting Groq API budget.

**Example:**
Someone scans `jobs.marutsut.me` with a tool like dirb or ffuf, finds `/webhook/jobs`,
and POSTs 500 fake job listings. Your scorer runs on all 500 (burning your daily
Groq token budget), the tailor loop tries to run on ~200 of them, your DB fills with
junk, and your daily 06:00 run is delayed because the queue is saturated with garbage.

**Options:**
- **Option A — Add a `WEBHOOK_SECRET` env var and require it as a Bearer token.**
  Any caller must set `Authorization: Bearer <secret>` header. One-line check in the
  endpoint. The friend's scraper (or our own scraper) includes this header when posting.
- **Option B — Remove the webhook endpoint entirely.** Once we build our own scraper
  (which writes to CSV and the scheduler reads it), there's no need for an HTTP
  webhook at all. The `/admin/trigger-scrape` endpoint (already auth-protected) covers
  manual triggers.
- **Option C — Restrict to internal network only.** Cloudflare tunnel can be configured
  to block this specific path from public access, only allowing Pi-local requests.
  More operational complexity.

---

## FLAW-4: _attach_pdf_flag uses wrong PDF row for re-tailored jobs
**Status: RESOLVED — _attach_pdf_flag now uses MAX(Resume.id) subquery to get latest resume per job**

**The problem:**
In `main.py`, `_attach_pdf_flag()` queries `db.query(Resume.job_id, Resume.pdf_path)
.filter(Resume.job_id.in_([...]))`. A job can have multiple Resume rows if it was
re-tailored (e.g., you hit `/admin/tailor/{job_id}` twice). The dict comprehension
`{job_id: bool(pp) for (job_id, pp) in ...}` iterates over ALL resume rows and
overwrites the same key each time — keeping whatever SQLite happens to return last,
which is not guaranteed to be the newest row. The dashboard might show "no PDF"
for a job that has one, or show a PDF link that points to a deleted file.

**Example:**
Job 42 is tailored twice. First run produced `pdfs/42.pdf` (kept). Second run also
wrote `pdfs/42.pdf` (overwrote). Two Resume rows exist — first with compile error
(pdf_path=None), second with pdf_path set. SQLite returns them in insertion order.
The dict gets populated as: `{42: False}` (first row, None), then `{42: True}` (second
row). End result depends on which row SQLite returns last — not deterministic.
Dashboard might show "no PDF" when one exists.

**Fix:**
```python
# Replace the query with one that gets only the latest resume per job
from sqlalchemy import func
subq = (db.query(Resume.job_id, func.max(Resume.id).label("max_id"))
        .filter(Resume.job_id.in_([j.id for j in jobs]))
        .group_by(Resume.job_id).subquery())
rows = db.query(Resume.job_id, Resume.pdf_path).join(
    subq, Resume.id == subq.c.max_id).all()
```

**Options:**
- **Option A — Fix the query** to use MAX(id) per job_id (latest resume row). Simple fix.
- **Option B — Add `is_latest` boolean column to Resume table**, set to False on old
  rows when a new one is created. Query only `is_latest=True` rows. More explicit but
  more schema changes.

---

## FLAW-5: Calendar event form always redirects to /archive — wrong page if submitted from /
**Status: OPEN — UX bug**

**The problem:**
`POST /jobs/{job_id}/calendar` hardcodes `return RedirectResponse(url="/archive", ...)`.
The calendar event modal exists on BOTH the active dashboard (`/`) and the archive page
(`/archive`). If a user on the active dashboard adds a calendar event for an upcoming
interview, they land on `/archive` instead of staying on `/`. Jarring and confusing.

**Example:**
You're looking at today's scored jobs on `/`. You find a role you just applied to and
want to add the interview date. You submit the calendar form. Instead of staying on
the active jobs view, you're dumped into the archive page which shows your applied jobs.
You have to manually navigate back to `/` to continue reviewing other jobs.

**Options:**
- **Option A — Pass a `next` query param from the form** (`/jobs/{id}/calendar?next=/`
  or `?next=/archive`) and redirect to that. One hidden input in each template.
- **Option B — Use the HTTP Referer header** to redirect back to wherever the request
  came from. Less explicit but zero template changes needed.

---

## FLAW-6: filtered_out jobs (score < 6) appear on the active dashboard
**Status: OPEN — design issue, decide and fix**

**The problem:**
`ACTIVE_STATUSES = {"ready", "review_needed", "scored", "tailoring", "filtered_out"}`.
`filtered_out` jobs scored between 0 and 5 — they're effectively rejected. They have
no tailored resume, no PDF, and you'd never apply to them. But they appear on the main
dashboard mixed in with the good jobs. For every 10 jobs that pass scoring, there might
be 20 that got filtered. The dashboard becomes a sea of grey low-score cards.

**Example:**
Daily scrape brings in 70 jobs. Scorer runs: 20 scored ≥6 (good), 45 filtered_out
(score 1–5), 5 rejected (score 0). Dashboard shows all 65 non-rejected jobs. You scroll
past 45 grey "filtered_out" cards to find the 20 actually actionable ones. Every day
this accumulates — after a week, 315 filtered_out jobs filling the dashboard.

**Options:**
- **Option A — Remove `filtered_out` from `ACTIVE_STATUSES`.** These jobs are done.
  They're not actionable. Let them sit silently in the DB (needed for source_hash dedup
  and for insights page data). Dashboard shows only jobs you can act on.
- **Option B — Keep them in ACTIVE_STATUSES but default the `min_score` filter to 6.**
  Filtered_out jobs are still reachable if you lower the filter, but by default they're
  hidden. Adds a "show low scores" toggle.
- **Option C — Create a separate `/low-scores` view** for the filtered_out jobs, similar
  to how archive is separate from active jobs. Active dashboard stays clean.

---

## FLAW-7: No visible alert when LinkedIn session cookie expires — scraper silently pauses
**Status: RESOLVED — system alert banner added to base.html; alerts.py read/write module created**

**The problem:**
When the LinkedIn scraper detects a redirect to the login page (cookie expired), the old design
only logged a message and stopped scraping. There was no indication on the dashboard that
anything was wrong. You'd only notice jobs had stopped appearing after a day or two.

**Decision:**
Created `backend/services/alerts.py` with `set_alert(key, level, message, instructions)` and
`clear_alert(key)`. The scraper calls `set_alert("linkedin_cookie_expired", "error", ...)` on
expiry detection. Alert state is persisted in `data/alerts.json`.

The dashboard now shows a sticky red banner at the very top of every page when any alert is
active. The banner pulses (CSS animation) to be impossible to miss. It shows the message
("LinkedIn scraper paused — session cookie expired") and fix instructions ("Extract li_at
cookie from dummy account browser session, paste into data/li_cookies.json to resume.").

The banner appears on ALL dashboard pages (base.html), stays until the cookie is refreshed and
the scraper successfully makes a request and calls `clear_alert("linkedin_cookie_expired")`.

**Files changed:**
- `backend/services/alerts.py` — created (get_alerts, set_alert, clear_alert)
- `backend/main.py` — import alerts_svc; register `get_alerts` as Jinja2 template global
- `backend/templates/base.html` — sticky red banner above all page content
- `backend/static/style.css` — `.sysalert-bar`, `.sysalert--error`, pulse animation

---

## FLAW-2: No visibility into scraper / scheduler run history from the dashboard
**Status: OPEN — low priority**

**The problem:**
The scheduler runs at 06:00 IST daily. There's no way to see from the dashboard
whether today's run happened, how many jobs were ingested, or if the scraper
returned 0 results. You'd only notice something is wrong if you check the dashboard
and the date on the newest jobs is yesterday.

**Options:**
- **Option A — Add a status bar to the dashboard header** showing: last scrape time,
  jobs ingested today, scorer/tailor counts. Read from a lightweight `run_log` table
  that the scheduler writes to after each daily run.
- **Option B — Expose a `GET /admin/last-run` JSON endpoint** with the same data.
  No UI change — you can check from the browser address bar when needed.
- **Option C — Accept it.** The zero-result alert (planned in scraper FLAW-6) already
  catches the worst case. Detailed run history is a nice-to-have.
