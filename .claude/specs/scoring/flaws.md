# Scoring — Flaws

---

## FLAW-1: A Groq API error leaves the job permanently stuck in 'scraped'
**Status: OPEN — low priority, manual workaround exists**

**The problem:**
`score_pending()` wraps each `score_job()` call in a try/except and increments
an error counter, but leaves the job's status as `scraped`. On the next scheduler
tick (next day at 06:00), `score_pending()` queries for `status='scraped'` again
and picks it up. So transient errors auto-retry on the next run. BUT — if Groq
is down for an extended period and many jobs accumulate errors, there's no visibility
into how many jobs are stuck or why.

**Example:**
Groq has a 2-hour outage at 06:05 IST. 15 jobs were ingested. Scorer runs, hits
a network error on each one, logs "Scoring failed for job X" 15 times, exits.
Logs scroll by. Tomorrow the scheduler retries and all 15 score fine. But if you
were watching the dashboard at 06:10 expecting to see scored jobs, you'd see nothing
and have no idea why without digging into logs.

**Options:**
- **Option A — Accept it.** The next-day retry is the safety net. If you suspect
  something is stuck, hit `POST /admin/score-pending` manually from the dashboard.
  Low enough frequency of Groq outages that this is not worth engineering around now.
- **Option B — Add a `score_failed` status** and a counter field. After 3 failed
  attempts, flip to `score_failed` so it's visible in the dashboard and doesn't
  clog the retry queue indefinitely.
- **Option C — Add a daily summary log line** at the end of `score_pending()` that
  prints total errors so the count is obvious in logs without needing a DB query.

---

## FLAW-3: Groq can return a score outside [0, 10] — status transition breaks silently
**Status: RESOLVED — clamped with max(0.0, min(10.0, score)) in scorer.py**

**The problem:**
`score_job()` does `score = float(result.get("score", 0))` with no range check.
If Groq hallucinates a score of 11, -1, or 0.5 for a role that should be filtered,
`_next_status(score)` runs against the wrong value and puts the job in the wrong bucket.
A score of 11 passes as `scored` (≥6) and triggers an expensive tailor loop.
A score of -1 is treated the same as 0 and marked `rejected` — wrong threshold applied.

**Example:**
Groq returns `{"score": 11, "domain_flag": "in-scope", ...}` for a borderline job.
`_next_status(11)` returns `"scored"`. Job goes through the full tailor loop, wastes
Groq tokens on critic + improver rounds, produces a PDF for a job you'd have never
applied to. Multiply by 5 bad scores in a batch = significant wasted API budget.

**Fix (2 lines in scorer.py):**
```python
score = max(0.0, min(10.0, float(result.get("score", 0))))
```
Clamp after parsing. This also handles float parsing errors if Groq returns a string.

**Options:**
- **Option A — Clamp the score immediately after parsing.** `max(0.0, min(10.0, score))`.
  Zero risk, zero side effects. Do this.
- **Option B — Reject the entire result if score is out of range and retry.** More correct
  but adds complexity and retry cost. Overkill given Option A is sufficient.

---

## FLAW-2: No cap on daily scoring batch — large CSV drops block the scheduler thread
**Status: OPEN — low priority, only matters if scraper ever returns 200+ jobs at once**

**The problem:**
`score_pending()` fetches ALL jobs with `status='scraped'` and scores them one by
one with a 3s delay between calls. For 20 jobs that's ~1 min. For 100 jobs that's
~5 min. For 200 jobs that's ~10 min. The scheduler runs this in a background thread
so the FastAPI app remains responsive, but a very large batch ties up that thread
for a long time and delays any calendar reminder jobs that fire during the same window.

**Example:**
Friend's scraper has a bug and dumps 500 jobs in one CSV. Scorer starts at 06:00.
It's still running at 06:25. A calendar reminder for "Interview at 10:00" was
scheduled to fire at 09:45 but the scheduler thread is saturated. Reminder fires late.

**Options:**
- **Option A — Accept it.** The scraper is keyword-filtered so 200+ jobs in a day
  is unrealistic for our keyword set. Not worth adding complexity now.
- **Option B — Add a configurable `SCORE_DAILY_CAP` env var** (default 50). Process
  highest-priority jobs first (freshest scraped_at) and leave the rest for next run.
- **Option C — Move scoring to a separate background thread** with its own pool,
  completely decoupled from the APScheduler thread.
