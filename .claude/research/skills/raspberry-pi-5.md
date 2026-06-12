---
title: Raspberry Pi 5 (Edge Deployment)
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — 10 ONNX models served live from a Pi 5 (4-core Cortex-A76, 8 GB) at pifive.marutsut.me; on-device latency benchmarks (MobileNetV3-Small 8 ms) [verified-live 2026-06-12].
- [[ekantik]] — 684 MB ChromaDB + LaBSE RAG served natively from the same Pi at ekantik.marutsut.me; custom HTTP bridge for syncing large artifacts.
- [[job-doot]] — Pi 5 is the M6 deployment target (SQLite/tectonic/2-container choices all Pi-driven); capacity planning (~1.4 GB/yr, SD-wear mitigation) [docs].
- [[federated-learning]] — Pi 5 specced as Phase-2 FL aggregation server (unbuilt).

## Resume verdict
Yes — LOCKED_SKILL_SET ("Raspberry Pi 5, real-time inference, edge deployment" already there) and resume. Running a personal ML server with multiple live public services is a headline differentiator.

## Interview readiness
Can discuss ARM constraints (int8 paradox, RAM budgets per model), home-server ops, and tunnel-based exposure. Caveat: job-doot and FL Phase 2 are *not yet* on the Pi — only smart-agri and ekantik are live.
