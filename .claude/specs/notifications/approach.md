# Notifications — Approach

## Status
BUILT (Telegram) — notification channel under review, see flaws.md

## What we built
Telegram bot sends a direct message to a configured `CHAT_ID` whenever the Gmail
watcher classifies an email as `REAL_RESPONSE`. The bot also fires for calendar
reminders (via APScheduler jobs created when the user clicks "Add to Calendar" on
the dashboard).

## Current flow
```
Gmail watcher classifies email as REAL_RESPONSE
        ↓
services/telegram.py → POST to Telegram Bot API
        ↓
User gets DM on Telegram
```

## Message format (current)
```
REAL RESPONSE RECEIVED

From: <sender>
Subject: <subject>

<first 600 chars of body>

Check your email for full details.
```

## Config
```
TELEGRAM_BOT_TOKEN=<token>     # in .env
TELEGRAM_CHAT_ID=<chat_id>     # in .env
```

## Known problem
User has joined a large number of Telegram channels (1M+ messages, movie groups,
spam). Telegram notification volume makes it impossible to distinguish the bot's
DMs from everything else. Notifications are effectively buried.

## Decision needed
See flaws.md — one flaw, one decision: which notification channel to switch to.
Once decided, the only code change is in `services/telegram.py` (swap the HTTP
call) and the `.env` vars. Everything else stays the same.

## Daily heartbeat (Flaws 3 & 6, M7) — "silence = alarm"
A once-a-day Telegram health ping so the pipeline can run unattended (built 2026-07-06).
Because it fires from **inside the backend**, if the backend is down the message never
arrives — so the ABSENCE of the daily ping is itself the alarm. Unifies Flaw 3 (verify
Telegram delivery works) and Flaw 6 (Pi health monitoring): same bot, one message.

Reports (what the backend can see):
- jobs collected in the last 24h (is the scraper producing?)
- awaiting scoring / scored / CVs ready (is the consumer draining the queue?)
- LinkedIn scraper status (🟢 active / 🔴 paused — cookie missing/expired)
- any active system alerts (scoring failure, cookie expired…), else "none"

Scheduled daily at `HEARTBEAT_HOUR` (default 21:00 IST) via APScheduler; sends through the
existing `services/telegram.py`. Module-level `heartbeat_job` in `scheduler.py` (picklable).

Accepted limitation (Flaw 6): whole-Pi / tunnel death → no ping goes out; Tejas notices
the silence. The `gmail-watcher` is a separate container — its liveness is a future add
(watcher writes a last-seen timestamp the heartbeat reads). Add an external uptime monitor
only if crashes become frequent.

## Notification centre — bell on the dashboard (spec'd 2026-11-05, Tejas approved)

**Why:** on 2026-11-04 the applier paused itself ("3 failures in a row": three company
sites with no submit button) and stayed paused for a day+. The widget/Today card only showed
"paused: 3 failures in a row" — no *which* jobs, *why*, *when*, or *how to resume*. Alerts in
`data/alerts.json` are current-state only and vanish when cleared, so there's no history.

**What:** a bell icon in the top bar of every page (phone + desktop) with an unread count.
Tapping it opens `/notifications`: newest first, each row = level dot, title, detail, the
"what to do" line, time ago, optional action link. Buttons: "Mark all read", "Clear all".
Opening the page does NOT auto-mark read (you might just glance); "Mark all read" does.

**Who sees what (Tejas chose "everyone, own events"):**
- `user_id = NULL` → system events → shown to admins only (scraper, cookie, scoring, Ollama…)
- `user_id = N` → that user's own events (today: applier events → owner `SUMMARY_USER_ID`,
  because the applier only applies for the owner). Later per-user events plug in the same way.

**Storage:** new table `notifications` (id, user_id NULL|FK, key, level
error|warning|info|success, title, detail, action_url, created_at, read_at). Created by
`create_all`, no migration. Keep last 200 per audience; older ones pruned on insert.

**Sources (all backend-side; the applier on the Pi host is NOT modified):**
1. `services/alerts.set_alert` (new alert only) → system notification, same level/message/
   instructions. `clear_alert` → system "Resolved: …" (success) with the down-time.
2. Applier watcher — scheduler job every 5 min reads the mounted `data/applier/`:
   - new `attempts` rows with status `failed` → owner warning "Couldn't apply: <title> @
     <company>" + human reason (e.g. `offsite_no_submit_button` → "company site had no submit
     button") + the job URL as action link.
   - new `needs_human:` rows → owner warning "Needs you: …".
   - `PAUSED` file appears → owner error "Applier paused: <reason>" listing the last 3
     failures; fix line: "On the Pi: cd ~/job-doot-applier && python -m applier.run resume".
   - `PAUSED` disappears → owner success "Applier resumed".
   Watermark (last seen attempt id + paused flag) in `data/notify_state.json`. First run
   only records the watermark (no flood of old rows) — except an already-present PAUSED,
   which is notified once.
3. Telegram stays as-is (alerts already push there); the bell is the in-app history.

**Not in scope:** auto-resuming the applier or changing its 3-strike rule (flaw decisions are
Tejas's), web push, widget changes.
