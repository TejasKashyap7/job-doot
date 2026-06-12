# Telegram Cleanup — Approach

## Status
DONE — ran 2026-06-09, left 215 channels, session file deleted

## What it does
A one-time interactive script (`tools/telegram_cleanup.py`) that logs into your
Telegram account as a *user* (not a bot) and bulk-leaves the spam channels cluttering
your inbox. After running it, the bot's DM alerts become visible again.

This uses **Telethon** — a Python library that speaks the Telegram MTProto protocol
as a real client, identical to the Telegram app. It can do anything the app can do,
including listing and leaving channels.

## What it is NOT
- Not a bot (no bot token used here)
- Not part of the job-doot pipeline (runs once, manually, from your Mac)
- Not deployed to Pi
- Does not touch `services/telegram.py` — the job alert bot is separate

## Prerequisites

### 1. Get Telegram API credentials (one-time, 5 minutes)
Go to `https://my.telegram.org`, log in with your phone number, go to
"API development tools", create an app. You get:
- `API_ID` — a number (e.g. 12345678)
- `API_HASH` — a 32-char hex string

These are different from the bot token. They represent *your account*, not a bot.
Store them in `.env` as `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.
These must never be committed — already covered by `.gitignore`.

### 2. Install Telethon
```bash
/opt/anaconda3/envs/job-doot/bin/pip install telethon==1.36.0
```
Add to `requirements.txt` under a `# telegram utilities` section.

## Flow

```
Run: python tools/telegram_cleanup.py
        ↓
Prompt: "Enter your phone number (+91...)"
Telegram sends OTP to your phone
Prompt: "Enter OTP"
        ↓
Telethon creates a session file: tools/session_cleanup.session
(This file = your login. Never commit it. Already in .gitignore.)
        ↓
Fetch all dialogs (channels + groups you're in)
        ↓
For each dialog, collect:
  - Name
  - Type (channel / megagroup / group)
  - Member count
  - Your last message/activity date in it
  - Whether you've ever sent a message there
        ↓
Print a table — sorted by member count descending:
  [ID]  [Name]                    [Members]  [Your last activity]  [Type]
  1     Movie Downloads HD         450,000    Never                 Channel
  2     Python Jobs India          12,000     Never                 Channel
  3     Batch 2022 CSE             180        2024-03-01            Group
  ...
        ↓
Prompt options:
  (A) Leave all channels where members > X and you've never sent a message
  (B) Leave specific IDs (comma-separated)
  (C) Review and confirm each one individually
  (D) Exit without leaving anything
        ↓
On confirm: leave selected channels with 2s delay between each
(Telegram flood-wait kicks in if you leave too fast — 2s is safe)
        ↓
Print summary: "Left 47 channels. 12 groups kept."
```

## What to keep vs leave
**Safe to leave (classic spam pattern):**
- Member count > 10,000 AND you have never sent a message there
- Name contains keywords: "movies", "web series", "download", "free", "crack",
  "jobs" (generic job boards), "earn money", "crypto"

**Keep no matter what:**
- Groups where you've sent a message in the last 6 months (active conversations)
- Groups with < 50 members (likely real friend/college groups)
- The script never auto-leaves anything — always shows a confirmation list first

## Session file
Telethon saves your login as `tools/session_cleanup.session`.
- Already covered by `.gitignore` (add `*.session` if not already there)
- Delete it after the cleanup run — you don't need it again
- If you run the script a second time, it re-authenticates via OTP

## After running
The bot's DM channel (`services/telegram.py`) is unchanged.
REAL_RESPONSE alerts will now be clearly visible in your DM list with the bot
since the channel noise is gone.
Close notifications/flaws.md FLAW-1 after this script is run successfully.
