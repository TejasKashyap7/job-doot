# Gmail Watcher — Flaws

---

## FLAW-1: Notification channel must be verified working after Telegram cleanup
**Status: OPEN — blocked on notifications/flaws.md FLAW-1 (Telegram cleanup)**

**The problem:**
The Gmail watcher calls `services/telegram.py` which sends a DM to TELEGRAM_CHAT_ID.
The watcher code is correct and built. But the alert is currently invisible because
of the channel noise problem documented in `notifications/flaws.md`.

This flaw closes automatically once the Telethon cleanup script is run and the
Telegram account is clean. No code change needed in the watcher.

**Dependency:** notifications/flaws.md → FLAW-1 must be resolved first.

---

## FLAW-4: Telegram send failure = recruiter email permanently unalerted
**Status: RESOLVED — `retry_unalerted()` added; called at top of every `poll_once()` (watcher.py:233)**

**The problem:**
In `handle_message()`, when a REAL_RESPONSE is found:
1. `db.add(row); db.commit()` — email is logged to DB
2. `telegram_send(...)` — alert is sent
3. `row.alerted = True; db.commit()` — alerted flag updated

If step 2 fails (network blip, Telegram API down), step 3 is never reached and
`alerted` stays False. The dedup guard at the top of `handle_message` checks
`email_log` by `gmail_msg_id` — on the next poll, this message is already in the DB
and is skipped entirely. The Telegram alert is permanently missed. No retry, ever.

**Example:**
Recruiter from Zepto emails you. Gmail watcher picks it up, logs it, tries to send
Telegram alert. Telegram API returns 429 at that exact moment. `telegram_send()` logs
a warning and swallows the error. `alerted` stays False. Next poll: message is in
email_log, skipped. You never get the alert. You miss the recruiter's 48-hour window.
The whole point of the watcher failed silently.

**Options:**
- **Option A — On startup and on each poll, check for `alerted=False` REAL_RESPONSE rows
  and retry sending the Telegram alert.** Add a `retry_unalerted()` function called at
  the start of each `poll_once()`. If `alerted` is still False after a successful send,
  set it to True. One-time retry per poll — handles transient failures automatically.
- **Option B — Don't commit the email_log row until after the Telegram send succeeds.**
  If the send fails, the row is not committed, so next poll re-classifies and re-attempts.
  Risk: if the send succeeds but commit fails, you get a duplicate alert on next poll.
- **Option C — Option A is correct.** Retry unalerted rows is the cleanest fix.

---

## FLAW-5: Duplicate EmailLog ORM in watcher.py — schema drift risk
**Status: RESOLVED — "KEEP IN SYNC WITH backend/database/models.py" comment added in both files (watcher.py:61)**

**The problem:**
`watcher.py` defines its own `EmailLog` SQLAlchemy model (lines 63–75) instead of
importing from `backend/database/models.py`. Both map to the same `email_log` table.
If you add a column to `EmailLog` in `models.py` (e.g., for the market insights page),
you must remember to update `watcher.py` too. If you don't, the watcher will try to
write rows to a table with a column it doesn't know about — or worse, silently omit
the column's data.

**Example:**
You add a `platform` column to EmailLog in `models.py` to track which email client
sent the message. You update the backend. Watcher still has the old ORM definition
with no `platform` column. Watcher inserts rows with `platform=NULL`. Backend code
that reads `email_log.platform` gets None for all watcher-written rows and breaks.
You debug for an hour before realising there are two ORM definitions.

**Options:**
- **Option A — Move shared models to a standalone `shared/models.py`** that both
  backend and gmail-watcher import. Requires restructuring imports but eliminates
  the drift problem permanently.
- **Option B — Accept it but add a comment in BOTH files** linking them:
  `# KEEP IN SYNC WITH gmail-watcher/watcher.py EmailLog` in models.py and vice versa.
  Low-tech but makes the coupling explicit.
- **Option C — Accept it entirely.** The email_log schema is unlikely to change.
  The duplicate is annoying but not actively dangerous unless you modify the schema.

---

## FLAW-6: Watcher requests calendar.events OAuth scope it never uses
**Status: RESOLVED — SCOPES now contains only `gmail.modify`; calendar scope removed (watcher.py:40)**

**The problem:**
`watcher.py` SCOPES includes `"https://www.googleapis.com/auth/calendar.events"`.
The watcher never creates calendar events — only the backend does. This means when
you run `oauth_bootstrap.py` to generate `token.json`, Google shows a consent screen
asking permission for both Gmail AND Google Calendar. Extra permissions requested =
wider blast radius if the token is ever leaked or misused.

**Example:**
You hand the Pi to a friend to help debug. They glance at the Google consent screen
in the OAuth flow: "This app wants to: Read, compose, send, and modify your Gmail.
Create and edit events on your Google Calendar." They wonder why a job-hunter dashboard
needs calendar access in the email watcher specifically.

**Fix:** Remove `"https://www.googleapis.com/auth/calendar.events"` from SCOPES in
`watcher.py`. The backend already has its own OAuth flow for calendar (via
`calendar_service.py`). Watcher only needs `gmail.modify`.

**Options:**
- **Option A — Remove the calendar scope from watcher.py SCOPES.** One-line fix.
  Re-run OAuth if token was already generated with the old scope list.
- **Option B — Accept it.** No real security risk for a personal project. Token is
  only on your Pi, not shared.

---

## FLAW-2: No alert if the watcher container itself crashes
**Status: OPEN — low priority, production concern**

**The problem:**
If the gmail-watcher Docker container crashes (OOM, uncaught exception, OAuth failure),
nothing tells you. The backend dashboard still works fine. You assume the watcher is
running. Meanwhile real recruiter emails are sitting unread and unalerted.

**Example:**
Token.json gets corrupted on the Pi (disk write error). Watcher crashes on startup
with FileNotFoundError. You don't notice for 3 days because the dashboard still loads
fine. A REAL_RESPONSE email from a company sits unread. The recruiter moves on.

**Options:**
- **Option A — Add a heartbeat log to the DB.** Watcher writes a row to a
  `heartbeat` table every poll cycle. A cron job on the Pi checks if the last
  heartbeat is older than 30 min and sends an ntfy/Telegram alert if so.
- **Option B — Use Docker's HEALTHCHECK directive.** Add a HEALTHCHECK to
  `gmail-watcher/Dockerfile` that touches a file every 15 min; if the check fails
  Docker marks the container unhealthy and can auto-restart it.
- **Option C — Docker `restart: always` in docker-compose.yml.** Already partially
  handles crash-and-restart. Add `--restart=unless-stopped` and the container
  auto-revives after most crashes. Not a monitoring solution but reduces downtime.

---

## FLAW-3: Gmail API quota
**Status: RESOLVED — 2hr polling keeps usage negligible**

Gmail API free tier: 1 billion quota units/day.
At 2hr polling × 50 messages: 12 polls × (5 list + 50×10 fetch/modify) = ~6,060 units/day.
Free limit is 1,000,000,000. We're using 0.0006% of it. Not a concern.
