# Resume Tailoring — Flaws

---

## FLAW-1: Tailoring output quality is unverified
**Status: OPEN — pipeline MUST NOT go live until this is RESOLVED**

**The problem:**
We have built the critic → improver loop and it runs without errors, but we have
never actually read the output PDFs with human eyes on real job descriptions.
The agents could be producing resumes that are technically valid LaTeX but are
generic, hallucinated, poorly formatted, or just not tailored in any meaningful way.

**Example:**
Imagine the scraper pulls a GenAI Engineer role that specifically wants RAG and
vector DB experience. The improver is supposed to bring those forward prominently.
But if the prompt is slightly off, the improver might just return the master resume
unchanged and still say "APPROVED". You apply to 50 jobs with a resume that was
never actually tailored. Every recruiter sees the same generic resume. Zero callbacks.
You wasted the whole pipeline.

**How to close this flaw:**
See the "Pre-go-live validation" section in `approach.md` for the exact checklist.
The short version:

1. Pick 3-5 real JDs (one strong match, one borderline, one out-of-scope)
2. Run them through the full pipeline locally (trigger-scrape → score → tailor)
3. Open every PDF at `GET /admin/pdf/{job_id}` and read it like a recruiter
4. Check `unfixable_items` in the DB — agent must flag gaps, not hide them
5. Verify zero hallucination — no skill, project, date, or metric that does not exist

**Pass criteria:**
- PDF compiles clean, no formatting issues
- Content is visibly different from master resume and specific to the JD
- No invented content anywhere
- `unfixable_items` correctly lists what could not be addressed

Mark this RESOLVED only after you have personally read and approved at least
3 output PDFs covering different role types. Update status below when done.

---

---

## FLAW-2: Job stuck at "tailoring" forever if the server crashes mid-run
**Status: RESOLVED — startup resets all 'tailoring' jobs to 'scored' in main.py lifespan**

**The problem:**
`tailor_for_job()` sets `job.status = "tailoring"` and commits at the very start.
`tailor_pending()` only picks up jobs with `status='scored'`. So if the Pi loses
power, the backend crashes (OOM kill, uvicorn exception), or the Docker container
is force-stopped while a tailor run is in progress, that job is permanently stuck
at `"tailoring"`. It will never be retried because no code ever re-queues it.
Restart the server — the job is invisible to the pipeline forever.

**Example:**
Scraper pulls 30 jobs. Scorer runs, 12 get `status='scored'`. Tailor loop starts.
On job 7, the Pi overheats and the kernel OOM-kills the backend container. Jobs 7–12
are stuck at `"tailoring"`. Docker auto-restarts the backend. Next 06:00 run picks
up new scraped jobs, scores them, tailors them. The 6 stuck jobs are never touched.
You never see a PDF for those 6 roles.

**Options:**
- **Option A — On startup, reset all `tailoring` jobs back to `scored`.**
  In `lifespan()` (main.py), after `init_db()`, run:
  `db.query(Job).filter(Job.status == "tailoring").update({"status": "scored"})`
  Any job that was mid-tailor when the server died gets re-queued on next restart.
  Safe — worst case you re-tailor a job once.
- **Option B — Add a recovery job in the scheduler** that runs every hour: finds any
  job stuck at `"tailoring"` for more than 30 minutes and resets it to `"scored"`.
  Handles mid-run hangs without requiring a restart to trigger recovery.
- **Option C — Both A and B.** Startup reset handles crash recovery. Hourly job
  handles infinite hangs (e.g., a Tectonic compile that somehow never times out).

---

## FLAW-3: If master_resume.tex is missing, job is permanently stuck at "tailoring"
**Status: RESOLVED — _read_master_resume() wrapped in try/except that resets job to 'scored'; startup warning added**

**The problem:**
`tailor_for_job()` sets `job.status = "tailoring"` and commits BEFORE calling
`_read_master_resume()`. If `master_resume.tex` is missing (path changed, file
deleted, wrong Docker volume mount), `_read_master_resume()` raises `FileNotFoundError`.
This exception propagates up to `tailor_pending()`'s try/except which logs it and
increments the error counter — but the job stays stuck at `"tailoring"` (see FLAW-2).
Every job in the batch fails the same way. The entire tailor run silently produces 0 PDFs.

**Example:**
You deploy to Pi and forget to include `master_resume.tex` in the Docker image
(it's not in the COPY path). Every tailor attempt fails with FileNotFoundError.
Logs show errors but the dashboard just shows all jobs stuck at `"tailoring"`.
You don't realise `master_resume.tex` is missing until you SSH in and read the logs.

**Options:**
- **Option A — Check for master_resume.tex at application startup** in `lifespan()`,
  log a loud WARNING (or raise) if it's missing. You catch the deployment error
  immediately on startup rather than silently during the first batch run.
- **Option B — Wrap `_read_master_resume()` in a try/except inside `tailor_for_job()`**
  and set `job.status = "scored"` (not "tailoring") before raising. Job goes back
  to the queue instead of getting stuck.
- **Option C — Both.** Startup check prevents the case entirely. The try/except
  is a fallback safety net.

---

## FLAW-4: No check if LaTeX changed between rounds — wasted Groq calls
**Status: RESOLVED — LaTeX diff check added in tailor_loop.py; breaks early if improver returns identical content**

**The problem:**
After the improver runs and returns `current_latex`, the loop goes straight to the
next critic round without checking if the LaTeX is identical to the previous version.
If the improver returns the exact same LaTeX (model got confused, context too long,
or shortcomings are genuinely unfixable), you call the critic again on identical input
and get the same NEEDS WORK verdict. You've wasted 2 Groq calls (improver + critic)
doing nothing.

**Example:**
Round 1 critic: NEEDS WORK, 5 shortcomings. Round 1 improver: returns identical LaTeX
(all 5 shortcomings are skills not in the locked set — unfixable). Round 2 critic:
reads same LaTeX, produces same NEEDS WORK. Round 2 improver: same result again.
3 full rounds consumed, 0 actual improvement, 6 Groq calls wasted. PDF compiled from
the original unmodified master resume anyway.

**Options:**
- **Option A — After each improver call, compare `current_latex == previous_latex`.**
  If identical, log a warning and break early. Job gets `review_needed` status.
  No point doing more rounds on unchanged LaTeX.
- **Option B — Check `unfixable` field from improver.** If improver says all
  shortcomings are unfixable, break immediately without running another critic round.
- **Option C — Both A and B.** Different failure modes, worth catching both.

---

_Resolution log: (fill this in when closing)_
- Date resolved:
- Test JDs used:
- Issues found and fixed:
