---
title: Tejas Project Vault
type: hub
---

# Tejas Project Vault

Welcome. This vault is the evidence-checked record of everything Tejas has actually built — six exhaustive project dossiers (each grounded in file-level code verification, live-endpoint checks, and explicit honesty flags), a skill-graph layer of 53 individual skill notes with strong/moderate/weak/exclude verdicts, and a master matrix tying them together. Its purpose is simple: every resume bullet, skill claim, and interview answer should trace back to something verifiable here — and anything that can't is flagged "do not claim".

## Project dossiers

- [[lens]] — one-day Indic medical-video pipeline: Sarvam ASR + diarization → Gemini role/classification with a verbatim hallucination filter; React/TS demo site; built as a LensKart cold-pitch POC.
- [[bluparrot]] — internship work, 13+ projects: 6-engine satellite/weather farm-advisory platform, Tanzania RAG family, DGQA 450-page tender extraction, Pinecone insurance chatbot, LangGraph SQL agent, cross-lingual MCP RAG, HS-code chatbot, Vapi voice-agent spec.
- [[ekantik]] — live source-grounded Hindi RAG over 1,004 discourse transcripts (684 MB ChromaDB + LaBSE on the Pi) at ekantik.marutsut.me; LangChain self-study capstone.
- [[smart-agri]] — live plant-disease API at pifive.marutsut.me: 10 ONNX models on a Pi 5, 8-CNN-family IEEE benchmark, MobileNetV3-Small edge winner, leakage fix + multi-seed retrain.
- [[federated-learning]] — Flower FL with hand-implemented FedProx: 99% on skewed non-IID data vs 98.8% centralized; 433-line flaw ledger; strictest spec-first project.
- [[job-doot]] — this repo: multi-agent AI job-hunting pipeline (scraper → Groq scorer → critic/improver LaTeX loop → tectonic PDFs → Gmail/Telegram triage); 45% complete, M3 in progress.

## Skill layer

- [[MASTER-MATRIX]] — every skill × project × evidence × verdict, plus the **Top 10 strongest provable claims** and the **Do NOT claim** list. Start here when editing the resume.
- `skills/` — one compact note per skill (evidence, resume verdict, interview readiness). 53 notes: 27 strong, 17 moderate, 7 weak, 2 excluded (sqlite, apscheduler — Claude-written plumbing by Tejas's own ruling).

## How to use this vault

Open `/Users/tejas/Documents/personal-projects/job-doot/.claude/research` as an Obsidian vault (Open folder as vault). The dossiers live in `dossiers/`, skills in `skills/`. Wikilinks resolve by filename, so the graph view shows the project↔skill bipartite structure: hover any skill to see which projects prove it, or any project to see what it demonstrates. Frontmatter `verdict` fields can drive graph-view color groups (e.g., `["verdict": strong]`).

## M3 context (why this vault exists)

This vault is the input for job-doot Milestone M3: rewriting the **LOCKED_SKILL_SET** in `backend/agents/prompts.py` and the master resume at `backend/master_resume.tex` from code-verified facts instead of memory. Workflow: use the MASTER-MATRIX "LOCKED_SKILL_SET?" column to draft the new locked set, the "Top 10 strongest provable claims" plus per-dossier "Resume Raw Material" sections to rewrite resume bullets, and the "Do NOT claim" list as the hard filter. Per the working agreement, Tejas personally approves every change — this vault presents evidence and options; it decides nothing on its own.
