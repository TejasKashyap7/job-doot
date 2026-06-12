---
title: Gmail API
type: skill
verdict: moderate
---
## Evidence
- [[job-doot]] — gmail-watcher container: polls `is:unread in:inbox` every 2h, dedups on gmail_msg_id, Groq-classifies each message, marks spam/auto-rejections read; OAuth bootstrap tool (`tools/oauth_bootstrap.py`) with InstalledAppFlow, scoped tokens, 7-day expiry ops handling; quota math (~6,060 units/day vs 1B) [verified-in-code: `gmail-watcher/watcher.py`].

## Resume verdict
Yes as part of the job-doot bullet ("LLM email triage daemon over the Gmail API"); not a standalone skills-section item. Pair with the at-least-once Telegram guarantee.

## Interview readiness
Can discuss OAuth consent flows, scope minimization (calendar scope dropped from the watcher), polling vs push trade-off, and quota budgeting. Caveat: the full email→alert chain is unverified end-to-end (M4 open); note the 15-min-vs-2h doc conflict — code says 2h.
