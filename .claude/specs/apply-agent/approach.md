# Apply Agent — Design Spec (M11)

> Status: designed 2026-11-01, not built. Decisions below are Tejas's unless marked
> "proposed". Roadmap entry: `.claude/specs/roadmap.md` → M11.

## Goal
Apply to LinkedIn Easy Apply jobs **fully autonomously**, with human-like input, at
random times through the day — no daily human step. First applicant is the **test
account (Vishal Kashyap)**; Tejas's main account only after the test account survives.

## Decisions (2026-11-01)
- **Live from day one.** Real Submit on every application. No dry-run phase.
- **Test applicant = Vishal's LinkedIn account**, logged in on the Pi in its own Chromium
  profile `~/.config/jobdoot-applier`. Separate from Hugh Janus (scraper, cookie-only HTTP,
  no browser) and from Tejas's main account (never on the Pi).
- **Which jobs:** the same AI jobs fetched for Tejas — jobs where Tejas's score ≥ threshold.
- **Which resume:** Vishal's own resume, unchanged (B.Com, MDU 2017–21; skills Instagram
  Marketing, Photography, Videography — from his LinkedIn). **Tejas's skills/projects are
  never put on Vishal's resume or answers.** No tailoring for Vishal in the test.
- **Honest answers only.** "Years of Python?" → 0. Anything not covered by the applicant
  profile or the Q&A bank → skip the job + ask (see Q&A bank).
- **Pacing:** 1–2 jobs per slot, a few random slots per day inside active hours, random
  gaps between jobs; never a fixed clock time. Hard daily cap.
- **Brain:** Claude (headless Claude Code on the Pi, Tejas's subscription) reads each form
  step and returns answers as JSON. A script does the clicking. If Claude is unavailable
  → pause applying (no fallback to the small model).
- **Hands:** Playwright driving the Pi's real Chromium + ghost-cursor (curved mouse paths,
  overshoot, Fitts's-law timing) + human typing.

## Where it runs
On the **Pi host, not in Docker** (proposed): it needs the desktop session (Wayland) and
the already-logged-in Chromium profile. New top-level folder `applier/` (like
`gmail-watcher/`), run as a systemd **user** service so it lives inside Tejas's desktop
session. Reads/writes the same SQLite `data/jobs.db` the backend uses (WAL handles a
second writer; writes are tiny).

## Flow
```
applier service (always on, Pi host)
  └─ each day 00:05: pick N random slot times in active hours (default 10:00–20:00 IST)
       └─ at each slot (if not paused, under daily cap):
            pick 1–2 jobs  → for each:
              1. open job URL in the applier Chromium profile; "read" 8–30 s (scroll)
              2. no "Easy Apply" button → log skipped(not_easy_apply), next job
              3. click Easy Apply (ghost-cursor)
              4. loop over modal steps:
                   extract fields (label, type, options, required, prefilled)
                   → Claude: profile + Q&A bank + fields → answers JSON | UNKNOWN list
                   → any UNKNOWN required field → discard, log skipped(question),
                     add to Q&A bank, Telegram Tejas, next job
                   → fill fields (ghost-cursor clicks, human typing, natural scroll)
                   → resume step: select/upload the applicant's PDF
                   → click Next / Review / Submit
              5. confirm "Application sent" → log success; else log failure + reason
              6. wait 2–6 min (random) before the next job in the slot
  └─ 21:30: Telegram digest (applied / skipped / failed / new questions) — FYI only
```

## Job selection (test phase)
Candidate jobs = `jobs` with a LinkedIn `apply_url`, where Tejas's `job_user_state.score`
≥ `APPLY_MIN_SCORE` (proposed default 7), not already attempted by this applicant, newest
first. Easy Apply is detected on the page (the scraper's `easy_apply` flag is always False
today). When Vishal later becomes a real user with his own preferences, selection switches
to his own `job_user_state`.

## Applicant profile (config, per applicant)
`applier/profiles/<name>.yaml` (gitignored — personal data): browser profile dir, resume
PDF path, contact details, facts the brain may use (education, skills, location, work
authorization, notice period, expected stipend/CTC, experience = none), daily cap,
active hours, min score, which user's scores to pick jobs from.

## Q&A bank
- New table `qa_bank`: `id, applicant, question_text, question_norm, field_type, options,
  answer, status (UNANSWERED|ANSWERED), job_id, first_seen, answered_at`.
- Unknown required question → row saved as UNANSWERED, job skipped, Telegram message to
  Tejas with the question (and options if it's a dropdown).
- Tejas answers on a dashboard page `/qa` (admin). Telegram-reply answering = later.
- Matching: Claude gets all ANSWERED rows each call and maps similar wording itself
  (no separate embedding store needed at this volume).
- Skipped-for-question jobs are retried after the question is answered.

## Logging / storage (as built 2026-11-01)
`data/jobs.db` is owned by root (backend container) and the applier runs as the desktop
user, so the applier keeps its **own SQLite file `data/applier/applier.db`** with tables
`attempts` (applicant, job, status `applied|skipped|failed|paused`, detail, steps) and
`qa_bank`. It reads jobs (and Telegram creds) read-only via `docker exec` into the
backend container. `application_attempts` in jobs.db stays unused for now.
Failure screenshots: `data/applier/shots/` (last 50). Log: `data/applier/applier.log`.

## Deploy (as built)
Code lives on branch `applier`, checked out on the Pi as a separate git worktree
`~/job-doot-applier` (so the main auto-deploy poller on `~/job-doot` is untouched);
`APPLIER_DATA=~/job-doot/data/applier`. Python venv `~/.venvs/applier311` — Python 3.11
(made with `uv`, matches the project's 3.11 standard; bezier has no Py3.13 aarch64 wheel and
its source build fails on the Pi's 3.13). CLI: `python -m applier.run
once|daemon|status|qa|answer|resume`. Answer questions until `/qa` exists:
`applier.run qa` then `applier.run answer <id> "<text>"`.

## Safety stops (auto-pause, no human needed to stay safe)
Any of these → stop all applying, write a pause flag, Telegram alert, wait for Tejas:
URL contains `/checkpoint` or `/authwall`; captcha/"unusual activity"/"restricted" text;
logged out; 3 failures in a row; LinkedIn's own Easy Apply limit message. Resume = delete
the pause flag (dashboard button later).

## Human-like behaviour
- Mouse: ghost-cursor paths between every target; occasional idle drift.
- Typing: 60–220 ms per character, occasional longer pause; no paste.
- Scrolling: wheel steps with variable speed; scroll the job description before applying.
- Timing: random think-time 1–4 s before each click; random slot times; daily cap.
- Same browser, same profile, same home IP as a normal user — no headless mode.

## Claude on the Pi
Install Claude Code on the Pi host; auth via `CLAUDE_CODE_OAUTH_TOKEN` generated on the
Mac with `claude setup-token` (ARM64 setup-token bug — generate on Mac). Tejas pastes the
token into the Pi env file himself. Call: `claude -p --output-format json` with a fixed
prompt; output validated as JSON before use. Budget: one call per form step.

**Model per task — cheapest that does the job** (decided 2026-11-01):
| Task | Model |
|---|---|
| Clicking, scrolling, typing, timing | **no LLM** — plain script + ghost-cursor |
| Answering Easy Apply form fields, matching a question to the Q&A bank | **Haiku** (`--model haiku`) |
| Retry when Haiku's JSON is invalid / it can't map a field it should know | **Sonnet**, once |
| Technical work (repairing broken scrapers/applier code, M10 check-up) | Opus |
Model names live in config so they can be changed without code edits.

## Dependencies
Python: `playwright`, a Python ghost-cursor port (verify which package works with
Playwright before pinning), `pyyaml` — appended pinned to `requirements.txt`. Browser:
the Pi's system Chromium via `executable_path` (no Playwright-bundled browser).
Open point: host Python env on the Pi (proposed: a dedicated venv for `applier/` only,
since the Mac-side "no .venv" rule is about the conda env on the Mac).

## Resolved (2026-11-01)
1. Vishal's standard answers → stored in `applier/profiles/vishal.yaml` (notice period,
   expected pay, relocation, citizenship, phone — given by Tejas).
2. **No daily cap** beyond the score rule: apply to every job that passes it, **max 2 per
   slot**. Throughput is set by the number of random slots per day (proposed 6–8 →
   ≤16/day). Safety stops still apply.
3. No Chrome extension: Claude Code CLI on the Pi (terminal) is the brain; Playwright is
   the hands. Claude Code logs in once on the Pi via its normal browser login flow.

## Open points
- Does Vishal know his account is being used for this.

## Build order
1. `qa_bank` table + `application_attempts` columns (migration).
2. `applier/` skeleton: config, Playwright persistent context on the Pi profile, safety
   checks, ghost-cursor + typing helpers.
3. Easy Apply modal driver (step loop, field extraction, resume step, submit, confirm).
4. Claude brain call + JSON validation + Q&A bank integration.
5. Daily random-slot scheduler, daily cap, Telegram alerts + digest.
6. `/qa` dashboard page.
7. Deploy to Pi as a systemd user service; first live slot watched via Pi Connect.

## Test mode — LinkedIn search source (decided 2026-11-02)
First live rounds (20 top-scored jobs) found 0 Easy Apply jobs: the fetched pool is mostly
closed or offsite-apply. To test detection now, the applier can take jobs from a LinkedIn
search done in the applicant's own browser, like a person would: profile setting
`source: linkedin_search` + `search_keywords`, URL filters Easy Apply only (`f_AL=true`),
India, past week. Results are NOT scored (test only — Tejas approved skipping the score
rule for the detection test, Vishal gave full permission). Attempts are keyed by the
LinkedIn job id. Default source stays `db` (score rule).

## Phase 2 — apply to ANY job, not only Easy Apply (decided 2026-11-02, not built)
Offsite "Apply ↗" jobs: follow the link and fill the company form.
- No-account ATS (Greenhouse, Lever, Ashby, SmartRecruiters, plain forms) → fill with the
  same brain + hands; Haiku writes a short honest cover note/"why us" from the JD + facts.
- Account-required or captcha ATS (Workday, Taleo, iCIMS login, SuccessFactors) → skip,
  list in the digest as "apply by hand".
- Scraper should record apply type (easy / offsite + ATS host) so the applier picks
  efficiently instead of opening pages to find out.

## Notifications privacy (decided 2026-11-02)
Nothing goes to Tejas's monitored office email. All alerts/digests/questions → Telegram
(phone); optional copy to personal Gmail only.

## Live test results + switch to scored jobs (2026-11-02)
- Search test mode: 3 real Easy Apply submissions on Vishal's account (SpeedMart AI
  Engineer + 2 Generative AI roles), ~30 job pages over ~10 runs, no captcha / security
  check / warning. LinkedIn's 2026 Easy Apply modal and search page needed new handling
  (dialog in shadow root, text-only buttons, file-chooser upload, unlinked question text,
  card browsing) — all built and verified live.
- **Decision (Tejas):** Vishal now applies to ALL of Tejas's scored jobs with
  **score >= 5** (was 7), source `db`, daily schedule on, 2 per slot. Offsite-apply jobs
  are skipped (recorded `not_easy_apply`) until Phase 2; they should be revisited then.

## Priority 2026-11-03 — never get stuck; apply on company sites too (decided: Tejas)
"The whole point is that it must not get stuck." Order:
1. **Scraper tags apply type** (this change). Guest jobPosting HTML is a reliable marker:
   `public_jobs_apply-link-onsite` = Easy Apply, `apply-link-offsite` = company site
   (verified on 2 known Easy Apply + 2 known offsite jobs). New column
   `jobs.apply_type` ('easy' | 'offsite' | NULL = unknown/legacy); `easy_apply` set too.
   Applier picks `easy` first, then unknown (old rows, checked by opening the page);
   `offsite` is skipped until step 2 ships. The company URL is NOT in the guest page —
   step 2 reaches it by clicking "Apply ↗" in the applicant's browser.
2. **Company-site applier (Phase 2):** follow Apply ↗, detect the ATS, fill no-account
   forms (Greenhouse, Lever, Ashby, SmartRecruiters, generic) from profile facts +
   Q&A bank; Haiku writes a short honest cover note when asked; upload resume; submit.
3. Account-required ATS (Workday etc.) later — needs the applicant's email to verify.

**CAPTCHAs: not solved by the agent (hard boundary).** Most no-account ATS forms use
invisible risk scoring that a real browser + human-like input passes without a challenge.
If a visible CAPTCHA/challenge appears, the agent does NOT attempt it: it parks the job as
`needs_human`, Telegrams Tejas the link, and moves straight on to the next job — so the
run never stalls. Parked jobs are listed in the daily digest.

### Phase 2 design (2026-11-03, building)
- Module `applier/offsite.py`. Entry: on the LinkedIn job page, when there is no Easy Apply
  button but an offsite "Apply" button, and profile `offsite: true`. Click it (human-like),
  catch the new tab (or same-tab navigation), dismiss LinkedIn's "share profile?" step.
- ATS detection by URL: greenhouse, lever, ashbyhq, smartrecruiters, workable, recruitee,
  breezy, keka, darwinbox, zoho → fill; myworkdayjobs/workday, taleo, icims, successfactors,
  oraclecloud → `needs_human:account_required`; unknown → generic fill.
- If the page shows a job description with an "Apply / Apply for this job" button but no
  form, click it first. Same field extractor + brain + human fill as Easy Apply, run on the
  form root. Resume via file input/chooser. Cover-letter / "why us" text fields: Haiku
  writes 3–4 honest sentences from the facts + job title/company (no invented experience).
- Stops (park, Telegram, move on — never stall): visible CAPTCHA (reCAPTCHA checkbox/
  challenge frame, hCaptcha, Cloudflare Turnstile), password/sign-in/create-account forms,
  no form found, email/OTP verification. Status `skipped` with detail `needs_human:<why>`
  + company URL; these are final (not retried) and listed in the digest.
- Success = confirmation text (thank you / application received / submitted). Validation
  errors → one re-ask, then fail with a snapshot. LinkedIn safety checks don't run on
  company sites (their own /login pages must not pause the whole applier).
- Profile flags: `offsite: true` enables it; `include_offsite: true` lets the job query
  return company-site jobs.
