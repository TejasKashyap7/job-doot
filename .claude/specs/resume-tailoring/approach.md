# Resume Tailoring — Approach

## Status
BUILT

## What it does
For each job scoring **≥9** (cost gate — see below), runs a Critic → Improver loop
against the master LaTeX resume. Produces a job-specific tailored PDF. The master
resume is never modified — each job gets its own copy stored in the `resumes` table.

## Tailoring cost gate (2026-07-06) — auto-tailor only score ≥ 9
Tailoring is the expensive step (Critic + Improver × up to 3 rounds ≈ 20k+ tokens per
job). Auto-tailoring **every** scored job (≥6) was exhausting the Groq free-tier quota:
the first couple of CVs succeeded, then rate limits made the rest fail and the job was
silently reset to `scored` with **no CV** — the "day-3, still no CVs for most jobs"
symptom. Decision (Tejas): **auto-tailor only jobs scoring ≥ 9** (the cream). This
slashes token spend, stops tailoring from starving scoring/filtering, and lets the few
top jobs get their CV reliably. Controlled by `TAILOR_MIN_SCORE` (default 9) in
`agents/tailor_loop.py`; enforced in `tailor_pending()`, which the consumer
(`score_and_tailor_job`) calls. (Post-decoupling the scrapers never tailor — only the
consumer does.) Jobs scoring 6–8 stay `scored` and visible; a CV can be made for one on
demand via `POST /admin/tailor/{job_id}`. Pairs with the role-fit targeting rewrite
(`scoring/approach.md`) so "≥9" means a top **core-AI/R&D** job, not a top applied one.

### Two more guards (2026-07-06, Tejas)
- **Cap at 2 tailors per pass** (`TAILOR_MAX_PER_PASS`, default 2): ~2 tailorings is
  enough to exhaust the free tier, so the consumer tailors at most the top 2 ≥9 jobs per
  pass; the rest wait for the next pass.
- **Fall back to the master résumé if tailoring can't run.** If Groq is down/rate-limited
  (or any agent error) during the loop, `tailor_for_job` catches it, uses the **master
  résumé as-is** (no Groq — just compiles it), and flags the résumé `TAILORING
  UNAVAILABLE`. Rule: *if we can't tailor, use the old CV* — a job never ends up with no
  CV at all.

## Flow
```
Job with status='scored'
        ↓
tailor_for_job(db, job)  [agents/tailor_loop.py]
        ↓
Read master_resume.tex (source of truth, never modified)
        ↓
ROUND 1:
    Critic reviews LaTeX against JD
    → APPROVED → skip to compile
    → NEEDS WORK → Improver edits LaTeX
ROUND 2:
    Critic reviews improved LaTeX
    → APPROVED → compile
    → NEEDS WORK → Improver edits again
ROUND 3 (final):
    Critic reviews
    → APPROVED → compile, status='ready'
    → NEEDS WORK → compile anyway, status='review_needed'
        ↓
Tectonic compiles LaTeX → PDF
PDF saved to backend/pdfs/{job_id}.pdf
        ↓
Resume row saved to DB:
    latex_content, pdf_path, iteration_count,
    critic_verdict, changelog, unfixable_items
```

## Key constraint: locked skill set
The improver agent reads `LOCKED_SKILL_SET` from `agents/prompts.py`.
It may ONLY rearrange, reword, and emphasise existing skills/projects.
It must NEVER:
- Invent a skill the candidate doesn't have
- Add a project that doesn't exist
- Change dates, metrics, or company names
- Add a new technology not in the locked set

If a JD requires something not in the locked set and it cannot be addressed by
rewording existing content → mark as `UNFIXABLE` in `resume.unfixable_items`.

## Status after tailoring
- `ready` — PDF compiled, critic gave APPROVED
- `review_needed` — PDF compiled, but critic still flagged issues after 3 rounds
  (user should review manually before applying)

## Trigger points
- Automatic: `scheduler.py` → `tailor_pending()` runs after `score_pending()`
- Manual: `POST /admin/tailor-pending` or `POST /admin/tailor/{job_id}`

## PDF access
`GET /admin/pdf/{job_id}` — serves the PDF file directly (protected by auth).
Dashboard shows a "Download PDF" button for each job that has one.

## Storage
PDFs: `backend/pdfs/{job_id}.pdf`
LaTeX source: `resumes.latex_content` column (kept for debugging/re-compile)

---

## Pre-go-live validation (do this before deploying to Pi)

The tailoring loop is the most important part of the pipeline — a bad resume is
worse than no resume. Before going live, manually verify quality on real-looking
sample jobs locally.

### What "up to the mark" means
1. PDF compiles without errors (no LaTeX crashes, no garbled output)
2. Formatting is correct — no overflowing lines, no missing sections, page fits
3. Content is genuinely tailored — not just the master copy pasted as-is
4. Zero hallucination — no invented skills, projects, companies, dates, or metrics
5. Unfixable gaps are flagged honestly in `unfixable_items`, not papered over

### How to run the validation locally

Step 1 — Make sure you have 3-5 diverse real JDs ready:
- One strong match (AI Engineer, lots of overlap)
- One borderline (Data Scientist, some gaps)
- One that should be rejected (pure SWE/frontend) to verify the scorer filters it

Step 2 — Add them to `dummy_jobs.csv` (or POST to `/webhook/jobs`)

Step 3 — Hit the manual admin endpoints from the dashboard:
```
POST /admin/trigger-scrape   ← loads the CSV
POST /admin/score-pending    ← runs scorer on all new rows
POST /admin/tailor-pending   ← runs tailor loop on scored jobs
```

Step 4 — For each job that reaches status `ready` or `review_needed`:
```
GET /admin/pdf/{job_id}      ← open the PDF in browser
```
Open it. Read it like a recruiter. Ask:
- Does it feel tailored to *this* JD or generic?
- Are there any lines that sound fabricated?
- Does the formatting look professional?

Step 5 — Check `unfixable_items` via the API or DB directly:
```sql
SELECT job_id, unfixable_items, critic_verdict FROM resumes;
```
Verify the agent correctly flagged what it couldn't fix rather than making it up.

### Pass criteria
All 3-5 test JDs must pass steps above before declaring the pipeline production-ready.
If any PDF looks wrong, investigate the critic/improver prompts in `agents/prompts.py`
before deploying — prompts are far easier to fix on Mac than on the Pi.
