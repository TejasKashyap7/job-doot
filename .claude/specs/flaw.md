# Project Flaws

> Tracks all identified flaws in this project.
> Use /resolve-flaws to work through these.

---

## Flaw 1: Scraper Not Built

**Status:** resolved

### Explanation
The job scraper is the entry point of the entire pipeline. Without it, no real
jobs come in. The spec is fully designed (Naukri JSON API + LinkedIn cookie-based
scraping) but the code does not exist yet. Until it's built, the pipeline cannot
be tested end-to-end on real data and cannot go live on the Pi.

### Example
You hit /admin/trigger-scrape and it reads the same 5 fake dummy jobs every time.
You cannot validate how the scorer and tailor loop perform on actual job listings.
The resume quality check (Flaw 2) cannot be done meaningfully without real JDs.

### Solution
Built `backend/services/scraper.py` with the full Naukri batch scraper (45 keyword ×
location combos, exponential backoff, 2–5s random delays), LinkedIn drip loop (daemon
thread, 15–45 min random intervals, full JD parsing via BeautifulSoup + li_at cookie),
and daily activity simulation (0–2 PYMK connections 9am–1pm, 0–2 post likes 6pm–9pm).
`scheduler.py` updated to call `scrape_naukri()` instead of `load_csv()` and to start
the LinkedIn drip thread on app startup.

---

## Flaw 2: Resume Tailoring Quality Unverified

**Status:** resolved

### Explanation
The critic → improver tailor loop runs without errors, but no human has ever read
the output PDFs. The agents could be producing resumes that look technically valid
but are generic or hallucinated. A fabricated resume actively hurts your chances.
This must be verified before the pipeline goes live.

### Example
The scraper pulls a "GenAI Engineer" role asking for RAG and vector DB experience.
The improver is supposed to bring those forward. If the prompt is slightly off, the
improver returns the master resume unchanged and still says "APPROVED". You apply
to 50 jobs with the same generic resume. Zero callbacks.

### Solution
Add two mechanical, no-AI checks that run automatically after each resume is
tailored, so suspect resumes are flagged instead of trusting the critic's
"APPROVED" blindly. The critic is memoryless (each round is a fresh, independent
audit), so it is trustworthy — but a single reviewer can still be plain wrong
once, and these checks are the cheap insurance for that.

1. Change check — compare the tailored resume against the master resume and
   measure how much of the text is identical. If they are nearly identical, the
   improver effectively did nothing, so flag it. This catches the case where the
   critic approves on round one and the untouched master is shipped as "tailored".

2. Skill-coverage check — for each job, take the skills from the locked skill set
   that the job description mentions, then confirm those skill words actually
   appear in the tailored resume. A small per-skill alias list handles wording
   variations (e.g. RAG vs Retrieval-Augmented Generation) so real matches are
   not missed. If the job asks for a skill Tejas has but it never appears on the
   page, flag it.

Both checks are pure Python (text-similarity + word matching against the curated
locked skill set), so they add no Groq calls and no measurable delay, and they
keep catching regressions on every future daily run — not just once. Results are
stored on the Resume row and surfaced on the dashboard as a colored tag per job
(tailored / review / unchanged) plus a "Needs review (N)" queue, mirroring the
existing Filtered page. Tejas then hand-reviews only the flagged resumes to
confirm the prose quality — the checks catch the mechanical failures, the human
confirms the writing. This is the one-time end-to-end quality verification
(roadmap M3), after which the checks remain as a permanent guardrail. Code build
is a follow-up task; the approach is locked.

---

## Flaw 3: Gmail Watcher Alerts Unverified After Telegram Cleanup

**Status:** resolved

### Explanation
The Gmail watcher and Telegram bot integration are built. But this has never been
tested end-to-end. The alert could fail silently for a configuration reason — wrong
CHAT_ID, bot never received a message from you — and you would never know until you
miss a real recruiter message.

### Example
A recruiter emails you. The watcher classifies it as REAL_RESPONSE and calls
tg_send(). The bot token is valid but you never started a conversation with the bot,
so Telegram rejects it silently. You never get the alert. You miss the recruiter's
48-hour window.

### Solution
Add a once-a-day heartbeat message to Telegram — a short summary such as
"✅ watcher alive, checked N emails today, M recruiter alerts sent." The watcher
currently fails silently (a wrong chat ID, or a bot Tejas never messaged first,
means alerts are refused with no error logged anywhere), so the fix is to make
success visible and let the ABSENCE of the daily heartbeat be the alarm. If a day
passes with no heartbeat, something is down and Tejas goes and looks — instead of
only finding out when he misses a real recruiter. The heartbeat also re-proves the
bot token and chat ID are correctly wired every single day, not just once.

Built deliberately as ONE unified health-signal system shared with Flaw 6 (Pi
container monitoring): a single daily status ping reports the health of the whole
pipeline (gmail-watcher + backend + last scrape) rather than two separate
heartbeat mechanisms doing the same job. Detailed scope of what that unified ping
monitors is settled in Flaw 6.

---

## Flaw 4: Filtered-Out Jobs Clutter the Dashboard

**Status:** resolved

### Explanation
Jobs that score below 6 get status `filtered_out` — they failed the relevance check
and are not worth applying to. But `filtered_out` is in `ACTIVE_STATUSES` in main.py,
so these rejected jobs appear on the main dashboard mixed with the good ones.
After a few days of scraping, the dashboard fills with grey low-score cards.

### Example
After one week, 50 jobs per day score below 6. 20 per day are actionable. By day 7
your dashboard shows 350 filtered_out cards plus 140 actionable ones. You scroll
through hundreds of grey cards to find the ones worth acting on. The tool meant to
simplify job hunting becomes noise.

### Solution
Added a dedicated `/filtered` page that shows all rejected jobs with their score and
the skill gaps that caused rejection. The main dashboard stays clean — only actionable
jobs appear there. A "Filtered (N)" link in the nav bar and a stat card on the dashboard
show the count at a glance. If you ever want to review what was rejected and why, one
click takes you there.

---

## Flaw 5: Calendar Form Always Redirects to Archive Page

**Status:** resolved

### Explanation
Submitting the calendar event form always redirects to /archive, hardcoded in main.py.
The form appears on both the active dashboard (/) and the archive page (/archive).
If you submit from the active jobs page, you land on the archive instead of staying
where you were.

### Example
You're on the main dashboard and log an interview date for a job. You submit the form.
You land on the archive page — a different view showing only applied jobs. You press
back to return to active jobs but your filter state is gone.

### Solution
The backend already accepted a `next_url` form field — it just defaulted to `/archive`.
Added the calendar modal to the dashboard template with `next_url` set to `/`, so
submitting from the dashboard returns you to the dashboard. The archive page keeps its
own modal with `next_url=/archive`. Each page now stays in place after a calendar
submit.

---

## Flaw 6: No Health Monitoring for Pi Containers

**Status:** resolved

### Explanation
If either Docker container on the Pi crashes — OOM kill, OAuth failure, software
crash — nothing notifies you. The Pi stays on and the Cloudflare tunnel stays up,
but the dashboard returns an error. You only find out when you try to open it or
notice no new jobs have appeared.

### Example
At 3am the Pi OOM-kills the backend container. The dashboard returns 502 all day.
You're asleep, then at work. By the time you notice it's been 18 hours of downtime.
You missed a full day of scraping. Any recruiter emails during that window triggered
the Gmail watcher — which was also down.

### Solution
One smart internal heartbeat — the unified daily Telegram ping from Flaw 3. Before
sending, it actively checks each piece of the pipeline and reports each one, e.g.
"backend OK / today's scrape OK / watcher OK" (or a failure mark against whatever
broke). This handles the subtlety that the watcher and backend are separate
containers: the ping does not just prove the watcher is alive, it independently
confirms the backend is answering and the daily scrape ran, so a dead backend cannot
hide behind a healthy watcher. Tejas reads the status on Telegram the next day and
acts if anything shows a failure.

Accepted limitation (Tejas, cost/complexity call): if the WHOLE Pi or the Cloudflare
tunnel dies, no ping goes out at all, and catching that relies on Tejas noticing the
silence himself. That is fine for now — the functionality-to-complexity ratio of
adding an external watchdog is not worth it yet. Revisit trigger: if crashes become
frequent, escalate this flaw to add an outside uptime monitor on jobs.marutsut.me
and/or container auto-restart. Until then, the single internal heartbeat is enough.

---

## Flaw 7: Pi Data Loss — Single Device, No Off-Site Backup

**Status:** resolved

### Explanation
The Pi runs everything off one NVMe SSD, and all data — the jobs database and
application history — lives only on that one drive. (An earlier version of this
flaw worried about SD-card write-wear; Tejas has since pivoted to an NVMe SSD for
exactly that reason, so wear is no longer the concern.) The real risk is that any
single device can be lost — it can die, be stolen, or be replaced — and with no
copy anywhere else, the data is gone.

### Example
The NVMe drive fails one morning, or Tejas swaps it for a bigger one, or the Pi is
lost to theft or a physical accident. Because the only copy lived on that drive,
all job history and application records vanish. There was no backup elsewhere.

### Solution
Correction to the premise (Tejas, 2026-07-03): the Pi runs everything on an NVMe
SSD, NOT an SD card. SSDs tolerate vastly more write cycles than SD cards, so
write-wear from the daily SQLite writes is effectively a non-issue. The real risk
that remains is single-device loss of ANY kind — drive death, theft, fire,
earthquake, or simply swapping the NVMe drive — all of which wipe local data if no
copy exists elsewhere. No on-Pi fix can survive the whole device being gone, so the
answer must be off-site.

Solution: an automated monthly cloud backup. Once a month a job snapshots the
jobs database — the job/market data: companies, JDs, roles, scores, and application
history — and commits it to a PRIVATE GitHub repo, separate from the code repo.
Because the copy lives off-site in the cloud, the data survives any physical
disaster to the Pi and lets Tejas restart exactly where he left off even after
replacing the NVMe drive or moving to new hardware — no reliance on a single
physical device. Ethical bonus: it preserves a real-world job-market dataset that
future developers could reuse.

Guards: the backup contains the jobs DATABASE ONLY. The tailored CV PDFs are
deliberately NOT backed up — they are personal and fully regenerable from the DB
via the tailor loop, so storing them wastes space (PDFs are ~1.1GB/year vs ~326MB
for the DB) and needlessly copies personal resumes to the cloud. Secrets (.env,
credentials.json, token.json) are never backed up either — they stay off the cloud
and are regenerated or re-copied on restore. As the DB grows past GitHub's comfort
zone (a single file over ~100MB is rejected, and the DB reaches ~326MB by year
one), gzip the snapshot or move backups to Kaggle / object storage.

---

## Flaw 8: No Decision on Insights Data Retention Window

**Status:** resolved

### Explanation
The market insights page will show charts of skill trends and salary ranges from the
jobs table. We have never decided how far back these charts should look. Data older
than 12–18 months misleads you — the AI job market changes fast. Aggregating years
of data also gets slower in SQLite over time.

### Example
After 3 years of running, the insights chart shows "basic ChatGPT integration" as
highly in-demand because it appeared in hundreds of 2024 job listings. But it has
been table stakes for two years. You make resume decisions based on outdated signal
without realising it.

### Solution
Use a 180-day rolling window for all insights queries — only jobs scraped in the
last 180 days feed the charts. This keeps the signal current without swinging wildly
week-to-week. When the /insights route and template are built, every aggregation
query gets a WHERE date_scraped >= NOW() - 180 days filter applied. Phase 2 can
layer time-series models (AR, SARIMA) on top of this same windowed dataset once
enough history has accumulated.

---

## Flaw 9: Groq Error Leaves Scoring Failure Invisible

**Status:** resolved

### Explanation
When Groq fails during scoring, the job stays at `scraped` and retries next day.
That is fine for correctness. But there is no visible signal on the dashboard that
anything went wrong. If you are watching for new scored jobs after the 06:00 run
and none appear, you do not know if the scraper failed, Groq was down, or just no
good jobs came in today.

### Example
Groq has a 2-hour outage at 06:05. 15 jobs were scraped. The scorer fails on all 15,
logs warnings, and exits. The dashboard shows 0 newly scored jobs. You have no idea
why without SSH-ing into the Pi and reading logs.

### Solution
Two signals fire when scoring errors occur. First, a Telegram message is sent
immediately — same bot as recruiter alerts — so you know on your phone within seconds.
Second, a persistent warning banner appears at the top of every dashboard page until
scoring succeeds the next day, at which point it clears automatically. If scoring
runs clean, the alert is cleared. No manual cleanup needed.

---

## Flaw 10: Insights Charts Are Misleading With Too Little Data

**Status:** resolved

### Explanation
The market insights charts will be statistically meaningless for the first few weeks
of scraping. With only 30–50 jobs, a few companies with matching keywords dominate
the chart and look like "the market" when they are just 2–3 employers. The chart
actively misleads you into wrong conclusions early on.

### Example
On day 5, PyTorch appears in 8 listings and TensorFlow in 2. The chart shows a strong
market preference for PyTorch. But those 8 listings are from 2 companies. With 500
jobs over 3 weeks, the real picture is much more balanced. The early chart was noise.

### Solution
Accepted as a non-issue given scraping volume. With Naukri pulling 90+ jobs per day
and LinkedIn adding ~24 more, the dataset will have 1,000+ jobs within the first week.
Charts will be statistically reliable well within a month — no minimum-data guard needed.
Full insights page design including pay-weighted skill analysis and company profiling
is documented in .claude/specs/market-insights/approach.md.

---

## Flaw 11: Project Count & Selection on the Resume Is Undecided

**Status:** resolved

### Explanation
The master resume now carries 3 projects (Smart Agri, Ekantik, Lens) plus Experience
and Research, which exactly fills one page. Tejas is unsure whether 2, 3, or 4 projects
is right, and whether the SAME projects should go to every JD. Standard norms: with
real experience + a publication on a 1-pager, 2–3 projects is typical; 4+ crowds out
the experience section that recruiters read first. But the right answer is per-JD:
a GenAI JD is best served by Ekantik+Lens, an edge/CV JD by Smart Agri+FL, an
agritech JD by Smart Agri+BluParrot bullets.

### Example
A "GenAI Engineer — RAG" JD arrives. The tailored resume still leads with Smart Agri
(pure CV/edge) because project selection is static. The recruiter skims page 1, sees
plant disease CNNs first, and never reaches the RAG project that matches their stack.

### Options to discuss
1. Fixed 3 projects (current state) — simplest, no pipeline change.
2. Master holds ALL projects (4–5); the improver agent SELECTS the best 2–3 per JD
   and drops the rest (prompt change in agents/prompts.py + a "project library" in the
   master tex as comments or a separate snippets file). Dossier vault already contains
   ready bullets per project.
3. Hybrid: 2 fixed anchors (Smart Agri = live+edge, Ekantik = RAG) + 1 JD-matched slot.

### Solution
Decided by Tejas 2026-06-12: **dynamic selection + dynamic bullets, grounded in a
maintained fact library.** Implementation (done):
- `backend/agents/project_library.py` — PROJECT_LIBRARY: every project (Smart Agri,
  Ekantik, Lens, Federated Learning, Job-Doot) as verified facts distilled from the
  dossier vault, each with a hard DO-NOT-CLAIM list from the dossier honesty flags.
  Maintenance rule: new project or changed fact → update library + dossier together.
- IMPROVER_SYSTEM in `agents/prompts.py` — improver now SELECTS the 2-3 best-matching
  projects per JD and WRITES the bullets itself, molded to the JD. Constraints: every
  claim traceable to a "Verified facts" line; rephrase/emphasize/reorder/select
  allowed; adding tools/metrics/outcomes/scope forbidden; DO-NOT-CLAIM lists are hard
  bans.
- **Always-deliver rule (Tejas, 2026-06-12):** a submission-ready tailored resume is
  produced for EVERY job above the apply threshold — no opportunity missed. Weak JD
  match → mold the closest real projects as far as honesty allows and still deliver.
  UNFIXABLE/gap notes are DASHBOARD-ONLY metadata (Resume.unfixable_items, shown in
  UI); no gap text, disclaimer, or limitation ever appears inside the resume itself.
  Enforced in tailor_loop.py: if the tailored LaTeX fails to compile, the loop falls
  back to compiling the master resume so a PDF always exists (error surfaced in UI).
- Master resume keeps Smart Agri + Ekantik + Lens as the default layout; tailored
  PDFs may differ per JD. Quality of selection + grounding is verified by hand in M3
  (Flaw 2 review).

---

## Flaw 12: Achievements Are Emotionally Curated, Not Signal-Curated

**Status:** resolved

### Explanation
The achievements section was written when Tejas had no job and carries emotional
weight (drone, pickleball officiating, NCC). Trimmed now to 3 (home server with 3 live
AI services, drone build, 500+ attendee research event + Dean's LOR), but open
questions remain: (a) how many achievements belong on a 1-pager (norm: 2–4, each must
make an interviewer ask a question Tejas WANTS to answer); (b) fixed set vs per-JD
selection (e.g., drone signals hands-on hardware for edge/robotics JDs but wastes a
line for pure-LLM JDs); (c) should the improver agent be allowed to swap achievements
per JD the way it reorders bullets — and how to automate that without fabrication
risk; (d) what NEW achievements to aim for next (e.g., open-source contributions to
LangChain/Flower, a Kaggle medal, a second publication from the Smart Agri IEEE
draft sitting ready on disk, hackathon wins, GitHub stars on a public repo).

### Example
An interviewer at an LLM startup reads "officiated 370+ pickleball matches" (already
cut) — zero signal for the role, one line of page-1 real estate burned. Conversely
"3 live public AI services off a home Pi" makes them open marutsut.me during the
call — strong, verifiable signal.

### Options to discuss
1. Fixed 2–3 high-signal achievements for all JDs (current state).
2. Achievement library + per-JD selection by the improver (same mechanism as Flaw 11
   option 2).
3. Drop the section entirely and fold the home-server line into Projects/Summary.
Plus: pick 1–2 future-achievement targets to actively pursue this year (IEEE paper
submission is the lowest-hanging — the draft already exists).

### Solution
Decided by Tejas 2026-06-12: **fixed set of all 3 high-signal achievements** for every
JD — (1) Pi 5 home server with 3 live public AI services (strongest, verifiable
mid-interview), (2) Acro drone build (hands-on hardware signal), (3) 500+ attendee
research event + Dean's LOR (leadership). Emotional-only items (pickleball, NCC)
removed. Per-JD achievement swapping deferred — revisit only if Flaw 11 lands on
dynamic selection. **Future achievement targets actively pursued:** (a) submit the
Smart Agri edge-benchmark IEEE paper (draft exists at
~/Downloads/agri-tanzania-documentation/smart_agri_notebooks/main.tex — fill author
placeholders, compile on Overleaf, pick venue); (b) merged open-source contributions
in the Flower / LangChain / Sarvam ecosystem (verifiable, tied to locked skills).
