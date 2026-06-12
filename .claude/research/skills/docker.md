---
title: Docker
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — multi-arch (AMD64+ARM64) image `tejaskashyap07/smart_agri` (1.99 GB) running live on the Pi 5 with restart=always; deployed image tar + inspect JSON preserved in pi-backup [verified].
- [[job-doot]] — 2-container compose (backend + gmail-watcher) sharing one SQLite WAL volume, healthchecks, tectonic static binary fetched in Dockerfile [verified-in-code].
- [[bluparrot]] — BCL chatbot containerized (docs).

## Resume verdict
Yes — already in LOCKED_SKILL_SET; keep it. Strongest claim: "multi-arch Docker images deployed to ARM64 edge hardware (Raspberry Pi 5), multi-container compose with shared-volume SQLite".

## Interview readiness
Can discuss multi-arch builds, container-vs-host path conventions, healthchecks, and why two containers isolate OAuth/LLM crashes from the dashboard. Caveat: ekantik runs uvicorn natively on the Pi — don't fold it into Docker claims.
