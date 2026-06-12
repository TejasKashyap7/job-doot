# Gmail Watcher — Approach

## Status
BUILT

## What it does
A separate long-running process that polls your Gmail inbox every 15 minutes, runs
each unread email through Groq to classify it, takes action based on the category,
and fires a Telegram alert for genuine recruiter responses.

Runs as its own Docker container so a Gmail OAuth crash or Groq failure does not
take down the main dashboard.

## Flow
```
Every 15 minutes:
        ↓
gmail_client() — refresh OAuth token if expired, build Gmail API client
        ↓
List up to 20 UNREAD messages in inbox
        ↓
For each message:
    Already in email_log? → skip (dedup guard)
    Fetch full message (headers + body)
    Extract: sender, subject, body text (up to 2000 chars)
        ↓
Groq classify(sender, subject, body):
    → REAL_RESPONSE   → log row + Telegram alert + mark alerted=True
    → SPAM_TRAP       → log row + mark email as READ in Gmail
    → AUTO_REJECTION  → log row + mark email as READ in Gmail
    → NEUTRAL         → skip entirely, do not log
        ↓
Sleep 15 minutes, repeat
```

## Email categories (locked in watcher.py classifier prompt)
- **REAL_RESPONSE** — genuine recruiter reply: interview invite, assessment scheduled,
  HR call request, offer discussion, follow-up on application
- **SPAM_TRAP** — fake "you are hired", asks for money, registration fees, suspicious
  sender domain, naukri/shine/timesjobs spam blasts
- **AUTO_REJECTION** — "we went with another candidate", "position filled",
  "not moving forward", automated rejection templates
- **NEUTRAL** — job alerts, newsletters, platform notifications, anything requiring
  no action → not even logged

## Telegram alert format (on REAL_RESPONSE)
```
REAL RESPONSE RECEIVED

From: <sender>
Subject: <subject>

<first 600 chars of email body>

Check your email for full details.
```

## Database
Writes to `email_log` table in the shared SQLite file.
Reads nothing from the `jobs` table — fully decoupled from the main pipeline.
Shares the DB via Docker volume mount with the backend container.

## OAuth
- Credentials: `data/credentials.json` (Google Cloud project, OAuth2 client)
- Token: `data/token.json` (generated once via `tools/oauth_bootstrap.py`)
- Token auto-refreshes when expired using the stored refresh_token
- Scopes: `gmail.modify` (read + mark read) + `calendar.events` (for future use)
- If token is missing: watcher crashes with a clear error message pointing to
  oauth_bootstrap.py — does not silently fail

## Config (env vars)
```
GMAIL_POLL_SEC=7200         # 2 hours default (12 polls/day vs 96 at 15min — 8x fewer Groq calls)
GMAIL_MAX_RESULTS=50        # messages fetched per poll (increased from 20 to cover 2hr window)
GOOGLE_TOKEN_PATH           # path to token.json
DATABASE_URL                # shared SQLite path
GROQ_API_KEY
GROQ_MODEL=llama-3.3-70b-versatile
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

## Token budget
Each email classification: ~700 Groq tokens (200 output + 500 input).
At 15min polling: up to 96 polls × 20 msgs = 1920 classifications/day worst case.
At 2hr polling:   up to 12 polls × 50 msgs = 600 classifications/day worst case.
Real-world inbox rarely hits 50 unread job-related emails in 2 hours, so actual
usage is much lower. 2hr interval is the right tradeoff — recruiter emails don't
need sub-hour response time.

## Groq retry logic
5 attempts with exponential backoff on RateLimitError/APIError.
On exhaustion: defaults to NEUTRAL (safe — better to miss a classification than crash).
