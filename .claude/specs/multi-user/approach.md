# Multi-User — Approach

## Status
IN PROGRESS (started 2026-09-16)

## What it does
Extends job-doot from single-tenant (hardcoded to Tejas) to three users — Tejas, Vasu,
Goru — sharing one scraped job pool but with fully independent scoring, tailoring,
resumes, dashboard logins, and (optional) Telegram alerts. A job that's a 10/10 for one
user can be a 2/10 for another, scored against *that user's* profile and role-type
preferences — not a shared default.

## Data model changes
- New `users` table: `id, username, password_hash, is_admin, telegram_enabled,
  telegram_bot_token, telegram_chat_id, candidate_profile (text), locked_skill_set
  (JSON), project_library (JSON), role_type_prefs (JSON), location_prefs (JSON),
  salary_pref, master_resume_tex (text), created_at`.
- New `groq_keys` table: `id, user_id, key, label, is_active, last_failure_at` — plural
  keys per user, rotated on quota exhaustion (tailoring only, see below).
- `Job` keeps only shared scrape data: `title, company, location, salary, remote_flag,
  apply_url, raw_description, source_hash, date_scraped, easy_apply`. Score/status/
  matches/gaps/date_applied move off it.
- New `job_user_state` table (junction): `job_id, user_id, score, domain_flag,
  top_matches, top_gaps, status, date_applied`. Unique on `(job_id, user_id)`. This is
  what the dashboard, archive, filtered, and insights views query per logged-in user.
- `Resume` gains `user_id` FK — one resume per (job, user) pair, not per job.
- New `invite_tokens` table: `token, created_by_user_id, used_by_user_id, created_at,
  used_at`. `/signup?token=...` validates against this.
- Migration is **additive only** — never drops or rewrites existing `Job` rows in place
  destructively; existing score/status/matches/gaps data for Tejas's jobs is copied into
  `job_user_state` keyed to a backfilled Tejas `users` row (`is_admin=true`), not deleted,
  before the old columns are removed from `Job`.

## Scoring (shared local Ollama — confirmed 2026-09-16)
Unchanged engine (`local_llm_client.py`, `gemma3:4b`, free/unlimited, runs on the Pi
host). Runs once per `(job, user)` pair instead of once per job — each newly scraped job
gets scored against every active user's `role_type_prefs`/`locked_skill_set`, writing one
`job_user_state` row per user. No Groq quota involved in scoring at all.

## Tailoring (per-user Groq keys, confirmed 2026-09-16)
`groq_client.py` takes a user's list of keys from `groq_keys`. On `RateLimitError` /
quota-exceeded, rotates to the next active key before failing the pass. Each user's
tailoring loop uses their own `master_resume_tex` + `project_library` +
`locked_skill_set` — same honesty rules as today (never invent, `do_not_claim` lists
respected), just parameterized per user instead of hardcoded in `prompts.py`.

## Auth
Real per-user login replaces the single `DASHBOARD_PASSWORD` cookie — session cookie
carries `user_id`. Passwords hashed with bcrypt. Dashboard queries `job_user_state`
filtered to the logged-in user, joined with `Job`'s shared fields.

## Admin (confirmed 2026-09-16)
`users.is_admin` — only Tejas's account. `/admin` view lists all users (username,
signup date, last activity) + per-user operational stats (jobs scored/tailored, current
alert/error state, which of their Groq keys are currently exhausted). **Never shows
other users' raw secrets** (Groq keys, Telegram token, password hash) in the UI, even to
the admin — monitoring is operational, not credential access.

## Notifications (revised 2026-09-16)
Telegram is optional per user (`telegram_enabled`) — some users won't want it connected.
**Gmail-based recruiter-reply detection stays single-account (Tejas's) for now** — out of
scope for this pass; it needs each user's own Gmail OAuth and not everyone will want to
share that access. Flagged as future work.

## Signup (invite-token only, confirmed 2026-09-16)
Tejas generates a one-time invite token (admin-only action). `/signup?token=...`
validates the token before showing the form; invalid/missing/already-used token → 404
(don't reveal the route exists). Signup form fields: username, password (set directly on
the form, never transmitted via the intake export below), Telegram bot token + chat ID
(optional), Groq keys (one per line), a paste-in field for the profile export block
produced by the intake prompt, and a `.tex` file upload for the master resume.

## Intake prompt for new users
See `.claude/specs/multi-user/intake-prompt.md` — this is the exact document Tejas hands
to Vasu and Goru. They run it in their own Claude Code (ideally with access to their own
project repos, so claims get verified against real code rather than trusted at face
value — same rigor as job-doot's own MASTER-MATRIX correction of Tejas's skills). It
produces one exactly-formatted export block plus a `.tex` resume file, both ready
*before* they ever click the invite link.

## Explicitly out of scope for this pass
- Gmail-based recruiter-reply detection for Vasu/Goru (needs per-user Gmail OAuth).
- Public/open signup (invite-token only, see above).
- Cross-user visibility of raw secrets, even to the admin.
