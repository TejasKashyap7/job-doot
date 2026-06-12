---
title: APScheduler
type: skill
verdict: exclude
---
## Evidence
- [[job-doot]] — 06:00 IST daily pipeline cron, nightly self-rescheduling randomized activity jobs, persistent SQLAlchemyJobStore so interview reminders (T-1d/T-day/T-30m) survive restarts [verified-in-code: `backend/scheduler.py:42-67`].

## Resume verdict
**Excluded by Tejas's own ruling**: APScheduler wiring was Claude-written plumbing; do not list it as a skill. The claimable layer is the orchestration *design* (cron pipeline + randomized human-mimicking schedules + restart-surviving reminders), which lives in the job-doot bullets without naming the library as a skill.

## Interview readiness
Can describe what the scheduler does and why jobs persist across restarts at design level. Should not claim API-level expertise in APScheduler internals.
