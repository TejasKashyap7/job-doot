---
title: FastAPI
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — live multi-model inference API on the Pi (`POST /predict/{model_name}`, 10 ONNX models) — verified live 2026-06-12 with real predictions.
- [[lens]] — async job server: BackgroundTasks, polling status API, per-stage timing, temp-dir cleanup [verified-in-code].
- [[ekantik]] — live RAG API + Jinja2 Hindi frontend at ekantik.marutsut.me.
- [[job-doot]] — full dashboard app (auth, admin routes, webhook with Bearer auth) [verified-in-code].
- [[bluparrot]] — API surface of nearly every sub-project (Agri-integrated, DGQA, Bajaj, nimish); lifespan-loading cut RAG latency 23s → 5–8s.

## Resume verdict
Yes — already in LOCKED_SKILL_SET; keep it. One of the most provable skills: two live public FastAPI deployments plus company systems.

## Interview readiness
Deep: background tasks vs job queues, lifespan model loading, dependency-based auth, CORS, polling APIs. Caveat: FastAPI scaffolding in job-doot was Claude-assisted plumbing — own the architecture, not every line.
