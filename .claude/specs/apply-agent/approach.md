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
