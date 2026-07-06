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
