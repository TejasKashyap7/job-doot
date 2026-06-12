---
title: SQLite
type: skill
verdict: exclude
---
## Evidence
- [[job-doot]] — two Docker containers share one WAL-mode SQLite DB (per-connection PRAGMAs: WAL, synchronous=NORMAL, foreign_keys=ON); deliberate Pi-friendly choice over Postgres [verified-in-code: `backend/database/db.py:14-20`].
- [[ekantik]] — ChromaDB's backing store is a 571 MB sqlite file (incidental); [[bluparrot]] nimish sessions/compliance DB.

## Resume verdict
**Excluded by Tejas's own ruling**: the SQL/SQLAlchemy plumbing was Claude-written; he does not claim SQLite/SQL as a personal skill. The claimable part is the *architecture decision* (WAL for two-container concurrency on a Pi), which belongs in the job-doot system-design bullet, not the skills list.

## Interview readiness
Can defend the WAL decision at design level (one writer + readers, tables partitioned by container, accepted-risk flaw record). Should not field deep SQL/SQLAlchemy-internals questions as an expert.
