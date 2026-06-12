---
title: Master Skill-Evidence Matrix
type: matrix
---

# Master Skill-Evidence Matrix

One row per skill note. Verdicts follow the dossiers plus Tejas's own exclusion rulings (sqlite/apscheduler excluded as Claude-written plumbing; bigquery weak as docs-only; vapi/n8n/google-sheets capped for spec-only evidence). LOCKED_SKILL_SET? = should appear in `backend/agents/prompts.py`; Resume? = should appear in the resume skills section (project bullets may still mention "no" items).

## LLM & GenAI

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[groq]] | [[job-doot]], [[ekantik]], [[bluparrot]] | 4 production agents + live RAG LLM, rate-limit-aware retry design | strong | yes | yes |
| [[gemini]] | [[lens]], [[bluparrot]] | structured extraction over 450+ page tender PDFs; 2-phase video classification | strong | yes | yes |
| [[langchain]] | [[ekantik]], [[bluparrot]] | live deployed RAG capstone of a full self-study curriculum | strong | yes | yes |
| [[langgraph]] | [[bluparrot]] | Smart Query StateGraph with parallel retrieval + LLM routing (code-verified) | strong | yes | yes |
| [[multi-agent]] | [[job-doot]], [[bluparrot]] | bounded critic↔improver loop with UNFIXABLE anti-hallucination protocol | strong | yes | yes |
| [[mcp]] | [[bluparrot]] | built a custom Wikipedia MCP server wired into LangGraph | moderate | yes | yes |
| [[sarvam-ai]] | [[lens]] | 6-step batch ASR integration, 2 undocumented quirks reverse-engineered | strong | yes | yes |
| [[vapi]] | [[bluparrot]] | "Shambhu" Hinglish caller — spec + dashboard config only | moderate | no | no |

## Vector & Retrieval

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[chromadb]] | [[ekantik]], [[bluparrot]] | 684 MB / ~40k-vector store live on a Pi with idempotent ingestion | strong | yes | yes |
| [[pinecone]] | [[bluparrot]] | serverless index, 3072-dim Gemini embeddings, batch upsert | moderate | yes | yes (in vector-DB list) |
| [[faiss]] | [[bluparrot]], [[ekantik]] | per-thread conversation-memory store in LangGraph | moderate | yes (in vector-DB list) | yes (in vector-DB list) |
| [[qdrant]] | [[bluparrot]] | sparqnow video-QA client usage (code-verified) | moderate | no | yes (in vector-DB list) |
| [[labse]] | [[ekantik]], [[bluparrot]] | cross-lingual retrieval: English queries over Hindi corpora, live | strong | yes | yes |
| [[mmr-retrieval]] | [[ekantik]] | configured with λ=1 → degenerates to pure relevance | weak | no | no |

## Indic-Multilingual

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[indic-ai]] | [[lens]], [[ekantik]], [[bluparrot]] | 4 independent projects: Hindi RAG, Hinglish ASR, cross-lingual retrieval | strong | yes | yes |
| [[speaker-diarization]] | [[lens]] | native-speaker-verified diarization + role recovery with failure fallback | strong | yes | yes (in pipeline bullet) |
| [[deep-translator]] | [[ekantik]], [[bluparrot]] | en↔hi query/transcript normalization (utility) | weak | no | no |

## ML-DL

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[tensorflow]] | [[smart-agri]], [[federated-learning]] | custom `@tf.function` FedProx step; 8-family benchmark pipeline | strong | yes | yes |
| [[keras]] | [[smart-agri]], [[federated-learning]] | applications backbones, frozen-head designs, custom callbacks | strong | yes | yes |
| [[efficientnet]] | [[smart-agri]], [[federated-learning]] | B0 99.95% acc / lowest loss; B1 FL backbone | strong | yes | yes |
| [[transfer-learning]] | [[smart-agri]], [[federated-learning]] | two-phase fine-tune, multi-seed; frozen-backbone edge design | strong | yes | yes |
| [[onnx]] | [[smart-agri]], [[federated-learning]] | 10 models served live on ARM; independent ONNX verification | strong | yes | yes |
| [[flower]] | [[federated-learning]] | custom FedAvgWithEval strategy + crash-safe checkpoint/resume | strong | yes | yes |
| [[federated-learning]] | [[federated-learning]] | FedProx μ=1.0 → 99% on skewed non-IID vs 98.8% centralized | strong | yes | yes |
| [[fedavg]] | [[federated-learning]] | balanced 100% run; bias-cancellation failure mode documented | strong | no (inside FL) | no (inside FL bullet) |
| [[fedprox]] | [[federated-learning]] | hand-implemented proximal term; μ non-monotonicity finding | strong | no (inside FL) | no (inside FL bullet) |
| [[scikit-learn]] | [[smart-agri]], [[federated-learning]] | seeded stratified splits (leakage fix), metrics | moderate | yes | yes |
| [[matplotlib]] | [[smart-agri]], [[federated-learning]] | IEEE-paper figures, convergence/confusion plots | moderate | yes | yes |

## Satellite-Geo

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[sentinel-2]] | [[bluparrot]] | Sentinel Hub band math (NDVI/NDWI), cloud-filtered revisit walk | strong | yes | yes |
| [[open-meteo]] | [[bluparrot]] | weather feeds for irrigation/protection/harvest engines | moderate | no | no (project bullet only) |
| [[rasterio]] | [[bluparrot]] | in-memory GeoTIFF parsing, NaN-aware aggregation | moderate | no | no (project bullet only) |

## Web & Frontend

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[fastapi]] | [[smart-agri]], [[lens]], [[ekantik]], [[job-doot]], [[bluparrot]] | 2 live public deployments + company APIs; 23s→5–8s lifespan optimization | strong | yes | yes |
| [[react]] | [[lens]], [[bluparrot]] | SPA exists but was Claude-implemented — Tejas ruling 2026-06-12: cannot defend in interview | exclude | no | no |
| [[typescript]] | [[lens]] | Claude-implemented — Tejas ruling 2026-06-12: replaced by AppScript in skill set | exclude | no | no |
| [[vite]] | [[lens]] | Claude-implemented toolchain — Tejas ruling 2026-06-12 | exclude | no | no |
| [[tailwind-css]] | [[lens]] | Claude-implemented styling — Tejas ruling 2026-06-12 | exclude | no | no |
| [[framer-motion]] | [[lens]] | Claude-implemented animations — Tejas ruling 2026-06-12 | exclude | no | no |
| appscript | (Tejas-confirmed) | added per Tejas 2026-06-12 — replaces TypeScript in Languages | moderate | yes | yes |

## Infra & Deployment

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[docker]] | [[smart-agri]], [[job-doot]], [[bluparrot]] | multi-arch image live on Pi 5; 2-container compose | strong | yes | yes |
| [[raspberry-pi-5]] | [[smart-agri]], [[ekantik]], [[job-doot]], [[federated-learning]] | 2 live public ML services from a home Pi 5 | strong | yes | yes |
| [[cloudflare-tunnel]] | [[smart-agri]], [[ekantik]], [[job-doot]] | systemd tunnel, multi-subdomain ingress, custom upload bridge | strong | yes | yes |
| [[tectonic]] | [[job-doot]] | sandboxed LaTeX→PDF compile with timeout/error capture | moderate | no | no (project bullet only) |
| [[gmail-api]] | [[job-doot]] | OAuth-scoped email triage daemon, quota budgeting | moderate | no | no (project bullet only) |
| [[telegram-bot]] | [[job-doot]] | at-least-once alert delivery via retry sweep | moderate | no | no (project bullet only) |
| [[bigquery]] | [[bluparrot]] | BCL architecture docs only — code not on disk | weak | no | no |
| [[n8n]] | [[bluparrot]] | workflow design in Vapi spec — no exports on disk | weak | no | no |
| [[google-sheets]] | [[bluparrot]] | POC-datastore design in Vapi spec only | weak | no | no |

## Data & Numerics

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[sqlite]] | [[job-doot]], [[bluparrot]] | WAL two-container architecture decision (Claude-written plumbing) | exclude | no | no |
| [[apscheduler]] | [[job-doot]] | cron + persistent jobstore orchestration (Claude-written plumbing) | exclude | no | no |
| [[pulp]] | [[bluparrot]] | in requirements only; real solver is scipy linprog/HiGHS | weak | no | no |
| [[pytesseract]] | [[bluparrot]] | soil-report OCR digitization | moderate | no | no (project bullet only) |
| [[rapidfuzz]] | [[bluparrot]] | district fuzzy match + spell-fix UX | weak | no | no |

## Practices

| Skill | Projects | Strongest evidence | Verdict | LOCKED_SKILL_SET? | Resume skills section? |
|---|---|---|---|---|---|
| [[spec-driven-development]] | [[bluparrot]], [[federated-learning]], [[job-doot]], [[lens]], [[smart-agri]] | 40+ specs, 433-line flaw ledger, gated roadmaps, flaw pre-mortems | strong | yes | yes |
| [[supabase]] | [[bluparrot]] | farm/commodity data layer, seed scripts (Claude-guided) | moderate | yes | yes (stack mention) |

---

## Top 10 strongest provable claims

1. **Live multi-model edge ML serving** — 10 ONNX models on a Raspberry Pi 5 behind FastAPI + Docker + Cloudflare Tunnel, verified live with real predictions ([[smart-agri]]).
2. **FedProx implemented by hand** as a custom `@tf.function` proximal training step; 99% on skewed non-IID data (98% independently ONNX-verified) ([[federated-learning]]).
3. **Live source-grounded Hindi RAG** — 1,004 transcripts, ~40k chunks, 684 MB ChromaDB on a Pi, retrieval-gated refusal before any LLM call ([[ekantik]]).
4. **Cross-lingual retrieval with LaBSE** — English queries retrieving Hindi chunks in one vector space, in two independent projects ([[ekantik]], [[bluparrot]]).
5. **8-CNN-family edge benchmark** with honest findings: MobileNetV3-Small wins (8 ms, 1.53M params), int8-on-ARM paradox, optimizer sensitivity, self-diagnosed leakage fix + multi-seed retrain ([[smart-agri]]).
6. **6-engine production farm-advisory platform** over Sentinel-2 / Open-Meteo / SoilGrids / Supabase, incl. LP fertilizer optimization and EVI-regression yield prediction ([[bluparrot]]).
7. **Layered LLM hallucination control** shipped three different ways: verbatim-substring filter ([[lens]]), evidence-checker no-inference rule ([[bluparrot]]), LOCKED_SKILL_SET + UNFIXABLE protocol ([[job-doot]]).
8. **Sarvam Saaras v3 batch ASR + diarization integration** for Indic dialects, with two undocumented API quirks reverse-engineered ([[lens]]).
9. **Bounded multi-agent resume-tailoring loop** (critic/improver separation of duties, 3-round cap, human-review fallback) with idempotent SHA256 ingestion and stealth no-browser scraping ([[job-doot]]).
10. **Spec-driven engineering practice** — 40+ specs at BluParrot, a 433-line flaw ledger gating all FL code, weighted roadmap + 34-flaw tracker in job-doot, 10 specs for a one-day build in Lens.

## Do NOT claim

- **"6 DL models + 4 custom CNNs"** — evidence shows 8 standard architecture families / 10 deployed ONNX models; no custom CNN architectures exist ([[smart-agri]] HF #1).
- **IndicTrans2 / Bulbul-v2 TTS** — absent from the Lens codebase entirely; no translation model, no TTS step anywhere ([[lens]] HF #1).
- **"Timestamps preserved in the vector store"** — ekantik keeps timestamps only in raw transcript JSONs; chunk metadata drops them ([[ekantik]] HF #2).
- **PuLP as used** — requirements-only; the working solver is scipy linprog/HiGHS ([[bluparrot]]).
- **BCL chatbot code ownership** — the directory holds architecture docs, not running code; confirm before claiming implementation ([[bluparrot]] HF #2).
- **Vapi agent as built/live** — spec + dashboard config only; no n8n workflows or code on disk ([[bluparrot]] HF #1).
- **AWS / GCP / BigQuery as skills** — no AWS anywhere; GCP/BigQuery is docs-only company architecture.
- **LoRA / fine-tuning of LLMs** — not ready; no evidence in any dossier.
- **SQL / SQLAlchemy / APScheduler / BeautifulSoup as personal skills** — Claude-written plumbing per Tejas's own ruling; claim the architecture decisions, not the libraries.
- **React / TypeScript / Vite / Tailwind CSS / Framer Motion as personal skills** — Tejas ruling 2026-06-12: frontends were Claude-implemented; he has seen the implementations but cannot claim them. The Lens *product* and its pipeline remain claimable; the frontend stack does not. AppScript replaces TypeScript in Languages.
- Also handle with care: "MMR for diversity" (λ=1 turns it off), "1300+ videos" (say 1,004 ingested), 99.95% accuracy (lab images; full-dataset 99.67%), "beat centralized" (+0.2pp within noise — say "matched"), job-doot throughput numbers (spec estimates, never run in production).
