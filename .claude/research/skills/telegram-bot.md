---
title: Telegram Bot (Alerts)
type: skill
verdict: moderate
---
## Evidence
- [[job-doot]] — raw Telegram bot HTTP API for recruiter-reply alerts, scrape-failure/cookie-expiry canaries, and 3-tier interview reminders; at-least-once delivery via `alerted=False` retry sweep each Gmail poll [verified-in-code: `backend/services/telegram.py`, `gmail-watcher/watcher.py`].

## Resume verdict
Mention inside the job-doot notification bullet ("LLM email triage with at-least-once Telegram alerting"); not a standalone skill line. The at-least-once guarantee is the resume-worthy idea.

## Interview readiness
Can explain the alerted-flag retry design ("what if Telegram is down?" — nothing is lost). Caveat: the end-to-end email→Telegram chain is unverified (M4 open) — frame as built, not battle-tested.
