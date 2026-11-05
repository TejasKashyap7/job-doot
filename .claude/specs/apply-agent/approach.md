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
logged out; LinkedIn's own Easy Apply limit message. Resume = delete
the pause flag (dashboard button later).
**Only LinkedIn signals pause** (Tejas, 2026-11-05). Failed or "needs you" jobs never pause
the applier — see "No failure-count pause" below.

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
| ~~Clicking, scrolling, typing, timing~~ | ~~no LLM — plain script + ghost-cursor~~ **SUPERSEDED 2026-11-05: Haiku decides what to click; ghost-cursor still does the moving/clicking/typing — see "Haiku drives the browser" below** |
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

## Phase 3 — account-based ATS + email verification (decided 2026-11-03, NOT built yet)
**Explicit permission (Tejas, 2026-11-03):** the agent MAY create job-portal accounts
(Workday, Taleo, iCIMS, SuccessFactors, …) with his details, and MAY read verification
OTPs / links from **his own Gmail `tejas06012005@gmail.com` ONLY** to verify those
accounts. **Not Vishal's mail** — the agent never reads Vishal's inbox.
- Scope: Gmail API, read-only, query limited to verification mails from the portal's
  domain in the last few minutes; extract code or link; nothing else is read or stored.
- Passwords: strong random per portal, stored in a chmod-600 file on the Pi
  (`data/applier/vault`), never in git / chat / logs; reused to log back in.
- Still parked (needs_human): SMS/phone OTP, CAPTCHA on sign-up.
- **Timing:** build + test only when the applier switches to Tejas's own identity. Until
  then Vishal's account keeps running the detection test (Easy Apply + Phase 2 no-account
  sites); account-based ATS stay parked. If Vishal's account gets flagged → change
  strategy before moving to Tejas's account.

## Parked-job notifications (decided 2026-11-03)
- Each needs_human job → instant Telegram message: job, company, why, direct link to the
  application page so Tejas can apply by hand. Plus the 21:30 digest list.
- Telegram reply to mark a parked job done (so it leaves the list) — to build.
- Never to the monitored office mailbox.

## Haiku drives the browser (decided 2026-11-05: Tejas — spec only, NOT built yet)

**Why:** on 2026-11-04 three company sites (Advanced Energy, Applied Materials, MacDermid
Alpha — same `jobs.<company>.com/job/...` careers platform) failed with
`offsite_no_submit_button` and paused the applier for 1.5 days. Cause was the *script*,
not the AI: its rule "≥ 2 input boxes = this is the form" took the site's job-search bar
(Keyword + Location) for the application form, never clicked the orange "Apply now »"
(a link, and the button finder only looks at buttons), and Haiku was asked to fill the
search boxes. Tejas: *"We need Haiku to apply for jobs, not some random script — like you
would with the Chrome extension: look at what is there and what is not, then apply."*

**Decision:** Haiku decides every action on the page (where to click, what to type, when
it's done). The script only (a) reads the page into a snapshot, (b) carries out Haiku's
actions with the existing ghost-cursor/human typing in `human.py`, (c) enforces the hard
safety rules. Applies to **both** LinkedIn Easy Apply and company sites (Tejas chose
"both at once"). Replaces the field-extractor + `_primary()` button-guessing in
`easy_apply.py` and `offsite.py`.

### The loop (one Haiku call per page state)
```
open job page (LinkedIn) → human "reads" it (scroll 8–30 s, as today)
repeat:
  1. SNAPSHOT (script, no AI) — text, like the Chrome extension's read_page:
       url, page title, any modal/dialog (incl. LinkedIn's shadow-root Easy Apply dialog),
       visible main text (trimmed), visible error messages, cookie banner present?,
       numbered list of every visible interactive element:
         [n] role  "label/text"  (type, current value, options, required, which
             region: header/search/nav/form/dialog/footer)
  2. HAIKU — gets: goal ("submit an application for <title> at <company>"),
       snapshot, applicant facts, Q&A bank, the last few actions + what changed,
       last form errors. Returns ONLY JSON:
         {"thinking": "<1 line: what page this is>",
          "actions": [ {"do":"click","n":4}, {"do":"type","n":7,"text":"..."},
                       {"do":"select","n":9,"option":"..."}, {"do":"check","n":12},
                       {"do":"upload_resume","n":11}, {"do":"scroll","dir":"down"},
                       {"do":"wait"} ],
          "status": "continue" | "applied" | "ask_human" | "give_up",
          "unknown": [ {"n":9,"question":"..."} ],   // required, not answerable truthfully
          "why": "<reason for applied/ask_human/give_up>"}
       A batch of actions per page (fill all fields, then one Next/Submit click) keeps it
       to ~1 call per page, not per click.
  3. VALIDATE (script) — every n exists and is visible; select/radio values copied from
       that element's options; text only from facts/Q&A (same honesty rules as today's
       PROMPT); no action outside the allow-list. Invalid → one Sonnet retry (as today).
  4. ACT — ghost-cursor click / human typing / file chooser upload, think-time between.
  5. CHECK — safety.check() (LinkedIn pages only), CAPTCHA detector, success text.
until status ≠ continue
```

### No page limit (Tejas, 2026-11-05: "don't limit Haiku with 15 pages")
No cap on pages/steps per application. The only stop is **stuck detection**: the same
snapshot (url + element list + errors) after Haiku's actions **3 times in a row** = no
progress → `failed: stuck_loop` with a screenshot. Every new page / changed form resets it.

### Hard rules the script enforces (Haiku cannot override)
- **Honesty:** same rules as the current form PROMPT. Unknown required answer →
  `ask_human` → Q&A bank + Telegram + bell, job skipped (never guess).
- **Stay on the job:** Haiku may navigate only within the job's LinkedIn page/dialog or
  the company site reached via "Apply ↗" (same registrable domain + its ATS host). A click
  that lands elsewhere → go back once; again → give_up.
- **Never touched by the AI:** CAPTCHA (park `needs_human`, as today), password / create
  account (park until Phase 3), LinkedIn checkpoint/authwall/restriction texts (pause
  everything, as today), payment pages.
- Cookie banners: Haiku may accept/close them (allowed action).
- Resume upload only via the `upload_resume` action → script picks the profile's PDF.
- "applied" is accepted only if the page also shows confirmation text (script regex) or
  LinkedIn's "Application sent"; otherwise treated as `continue`.

### No failure-count pause (Tejas, 2026-11-05 — replaces the 3-strike rule)
- The old "3 failures in a row → pause" rule is **removed**. It paused on 5 Nov because it
  skipped over "needs you" results and counted 3 old-script failures from 4 Nov.
- A job that fails (site confusing, stuck, no form) or needs Tejas (sign-in, account,
  CAPTCHA, payment) is logged + shown under the bell, and the applier **moves on to the
  next job**. Tejas handles "Needs you" items when he is free.
- The **only** pauses are LinkedIn account-safety signals (checkpoint/authwall/login,
  "unusual activity", restriction, Easy Apply daily-limit text) — see Safety stops.
- Browser crash: 2 crashes in one slot → end that slot (not a pause); the next slot
  starts a fresh browser session.
- Per slot: keep opening jobs until the slot's 1–2 applications are done, up to
  **`max_views_per_slot`** job pages (default 12, was 5; Vishal's profile: 15), with random 20–60 s gaps between jobs and 2–6 min
  after an application — so a run of sign-in sites no longer ends the slot with 0 applied.
- Note: "account / sign-in required" stops only because the current profile is Vishal's
  test account. On Tejas's own profile, Phase 3 (account creation with
  tejas06012005@gmail.com + Gmail OTP) will handle these sites; until it is built they stay
  "Needs you".

### Cost (Claude subscription, shared with Tejas's own use)
~1 Haiku call per page state ≈ 3–8 per application (today 1–3). Text snapshot, no
screenshot by default (much cheaper); a screenshot is attached only on the retry after
Haiku says it can't make sense of the page. Quota hit (429) → skip, not a failure (as
today). Snapshot trimmed to ~6 k chars; elements outside the viewport listed but marked.

### Plain-language reasons (Tejas, 2026-11-05)
Haiku's `why` (give_up / ask_human) is written for a non-technical reader in 1–3 sentences:
what it saw, what it tried, why it stopped. Stored in the attempt detail (`site:<why> | url`,
up to 900 chars) and shown in full under the bell. Stuck / left-the-site stops get the same
kind of sentence from the script.

### Build order
1. `applier/snapshot.py` — page → numbered element list + text (shadow-root aware).
2. `applier/brain.py` — `next_actions()` with the new PROMPT + validator (keep
   `answer_fields` until both flows are switched).
3. `applier/agent.py` — the loop, stuck detection, domain guard, success check.
4. Switch offsite → agent; live-test on the 3 failed jobs (811/812/813) via `run once`.
5. Switch Easy Apply → agent; live-test on a few Easy Apply jobs.
6. Failure-counting change in `run.py`; delete old field-guessing code once both pass.

### Open points
- Wall-clock limit per job: **none** (Tejas, 2026-11-05: "no time limit"). Stuck detection is the only stop.
