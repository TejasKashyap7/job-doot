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
