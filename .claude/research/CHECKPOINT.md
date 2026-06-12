# M3 Dossier Sweep — CHECKPOINT (written 2026-06-12, session "M3-Resume-Builder")

> **STATUS UPDATE 2026-06-12 ~02:15 IST: SWEEP + SYNTHESIS COMPLETE.** All 6 dossiers
> in `dossiers/`, 53 skill notes in `skills/`, `MASTER-MATRIX.md` + `HOME.md` written.
> This file is now historical. Next step = §2.3 (M3 proper): rewrite LOCKED_SKILL_SET
> + master_resume.tex from MASTER-MATRIX.md — get Tejas's go first.
> Ops note for relaunches: background agents CANNOT write files (auto-denied) — run
> dossier-style agents in FOREGROUND; allow rules for `.claude/research/**` are in
> `.claude/settings.local.json`.

> **Purpose:** Session token limit was hit (resets 1:50am IST). This file is fully
> self-contained — a fresh Claude session can resume the work from here with zero
> quality loss. Read this whole file before doing anything.

---

## 1. Status snapshot

- Project: job-doot, 45% done (M1 ✅ M2 ✅ M5 ✅). Currently in **M3 Quality Verification**.
- We are in a PRE-M3 context-gathering phase: build exhaustive dossiers of ALL of
  Tejas's projects so LOCKED_SKILL_SET + master_resume.tex can be rewritten with
  code-verified facts.
- 6 background agents were launched (one per project, each spawning 2 Explore
  subagents: spec analyst + code analyst). **ALL 6 died instantly on the session
  usage limit. ZERO dossiers were written.** `dossiers/` is empty.
- Nothing else was modified. `backend/agents/prompts.py` and `backend/master_resume.tex`
  are still untouched (their update is the step AFTER the dossiers).

## 2. The full plan (in order)

1. **Relaunch the 6 project agents** using the prompt template + per-project table
   below. Recommendation: launch in **2 batches of 3** (background, parallel within
   a batch) to avoid burning the whole quota at once. Batch 1: BluParrot, Lens,
   Smart Agri (highest resume value). Batch 2: Ekantik, Federated Learning, Job-Doot.
2. **Synthesis phase (main session, after all dossiers exist):**
   - Create `skills/<skill-slug>.md` — ONE note per skill (see vault format §4):
     which projects prove it, file:line evidence, resume-worthiness, interview-readiness.
   - Create `MASTER-MATRIX.md` — table: skill → projects → strongest evidence → on-resume? → in-LOCKED_SKILL_SET?
   - Create `HOME.md` — hub note linking everything (Obsidian entry point).
3. **Then resume M3 proper:**
   a. Rewrite `LOCKED_SKILL_SET` in `backend/agents/prompts.py` from the matrix.
   b. Rewrite `backend/master_resume.tex`: fix skills section (remove DSA/C++ STL
      duplication, FastAPI inconsistency), update Blu Parrot bullets with real tech
      (LangGraph, Groq, Sentinel-2, Supabase), ADD the Lens project.
   c. Trigger real Naukri scrape → POST /admin/score-pending → tailor 3–5
      representative jobs (one 8–9, one 6–7, one borderline).
   d. **Tejas reads the PDFs and judges quality himself** (flaw-ownership rule:
      Claude never marks Flaw 2 resolved or autonomously "fixes" quality).
4. Honesty exclusions (apply at resume-writing time, NOT at dossier time — dossiers
   capture everything): no SQL/SQLAlchemy/APScheduler/BeautifulSoup/requests as skills
   (Claude-written), no LoRA/fine-tuning (still learning), no AWS/GCP/Azure.
   Supabase = real but moderate. Spec-driven development = a real claimed skill.

## 3. Obsidian / knowledge-graph decision (user request from YT video)

- User saw a video combining "graphify" (almost certainly **Graphiti**, Zep's
  Neo4j-backed temporal knowledge graph with an MCP server) + **Obsidian**.
- **Decision: adopt Obsidian-native vault format now; defer Graphiti.**
  `.claude/research/` IS the vault — Tejas can open it in Obsidian and get the
  graph view for free. Graphiti = real infra (Neo4j + MCP), overkill for 6
  projects; revisit only if the vault proves insufficient.

## 4. Vault format (agents MUST follow)

Every dossier/note gets YAML frontmatter + wikilinks:

```markdown
---
title: <Project Name>
type: project-dossier        # or: skill, hub, matrix
path: </abs/path/to/project>
deployed: <url or none>
tags: [<lowercase-tech-tags>]
---
```

- First mention of any skill/tech in prose → wikilink it: `[[langgraph]]`, `[[groq]]`,
  `[[sarvam-ai]]`, `[[chromadb]]`, `[[fastapi]]`, `[[docker]]`, `[[raspberry-pi-5]]` …
  lowercase-kebab-case slugs, consistent across all dossiers (this is what builds the graph).
- Cross-link related projects: `[[lens]]`, `[[bluparrot]]`, `[[ekantik]]`,
  `[[smart-agri]]`, `[[federated-learning]]`, `[[job-doot]]`.
- Dossier filenames = those slugs, in `dossiers/`. Skill notes in `skills/`.

## 5. Shared agent prompt template (relaunch verbatim, filling {PLACEHOLDERS})

Launch each as: Agent tool, subagent_type "general-purpose", run_in_background true.

```
MISSION: You are the dedicated project-context agent for **{NAME}**. Produce an
EXHAUSTIVE dossier — no detail too small. Token budget is not a concern;
completeness is the only success metric.

PROJECT LOCATION: {PATH}
DEPLOYED: {DEPLOYED}
KNOWN CONTEXT (verify against code, don't assume): {KNOWN_CONTEXT}

PROCESS (follow exactly):
1. Spawn TWO subagents IN PARALLEL via the Agent tool:
   a. SPEC ANALYST — subagent_type "Explore", very thorough: find and read EVERY
      documentation artifact — .claude/specs/**, CLAUDE.md, README*, docs/, any
      *.md, design notes, TODOs, roadmaps, flaw trackers. Report: goals,
      requirements, architecture decisions + rationale, milestones, known
      flaws/limitations, spec-driven-development evidence. Quote key passages
      with file paths.
   b. CODE ANALYST — subagent_type "Explore", very thorough: walk the ENTIRE
      codebase (incl. notebooks). Report: directory layout; every
      language/framework/library actually imported or declared with file:line
      evidence; every external API/service + exact model names (LLM, ASR/TTS,
      embeddings + dimensions, vector DBs + index config, databases, satellites,
      weather APIs); all HTTP endpoints; data models/schemas; frontend stack;
      Docker/deploy configs; EVERY hard number in code/comments/configs/notebook
      outputs (accuracy, latency, dataset sizes, counts, params); non-obvious
      engineering (caching, retries, idempotency, validation, concurrency).
      Note EXISTENCE of .env/credentials but NEVER read out secret values.
2. After both report, personally read the 3–5 most load-bearing files to resolve
   conflicts between the reports.
3. Synthesize EVERYTHING into one dossier and WRITE it to: {OUTPUT_FILE}

VAULT FORMAT: YAML frontmatter (title, type: project-dossier, path, deployed,
tags) + wikilink every skill/tech on first mention as [[lowercase-kebab-slug]]
(e.g. [[langgraph]], [[groq]], [[chromadb]]) and related projects as
[[lens]]/[[bluparrot]]/[[ekantik]]/[[smart-agri]]/[[federated-learning]]/[[job-doot]].
Slugs must be consistent — they build an Obsidian graph.

DOSSIER SECTIONS:
# {NAME} — Full Dossier
## TL;DR (one paragraph)
## Problem & Purpose
## Architecture (components + data flow; ASCII diagram welcome)
## Complete Tech Stack (table: tech | where used | evidence file:line)
{EXTRA_SECTIONS}
## Endpoints / Interfaces
## Metrics & Hard Numbers (every quantified fact, with source)
## Deployment & Infra
## Spec-Driven Development Evidence
## Resume Raw Material (10–20 candidate bullets, concrete numbers + tech names,
   each marked [verified-in-code] or [docs-only])
## Interview Depth (hard problems solved, design tradeoffs, likely interview
   questions + honest answers)
## Honesty Flags (anything scaffolded/generated-looking, half-finished, or
   claimed in docs but absent in code)

RULES:
- READ-ONLY on the project directory. Your ONLY write is the dossier file.
- Never copy secret values (keys, tokens, cookies) — reference existence only.
- Code evidence beats doc claims; report and flag conflicts.
- Final message back: ~10-line executive summary + dossier path. Detail goes in the file.
```

## 6. Per-project parameters

Output dir for all: `/Users/tejas/Documents/personal-projects/job-doot/.claude/research/dossiers/`

| # | NAME | PATH | DEPLOYED | OUTPUT_FILE |
|---|------|------|----------|-------------|
| 1 | Lens | /Users/tejas/Documents/lens | https://lens.marutsut.me (currently 403 — note, don't fix) | dossiers/lens.md |
| 2 | BluParrot (internship) | /Users/tejas/Documents/BluParrot | — (internal) | dossiers/bluparrot.md |
| 3 | Ekantik Vartalap RAG | /Users/tejas/Documents/LangChain/Ekantik Project (space in name) | https://ekantik.marutsut.me | dossiers/ekantik.md |
| 4 | Smart Agri / Plant Disease | /Users/tejas/Documents/Smart Agri (space in name) | https://pifive.marutsut.me/docs | dossiers/smart-agri.md |
| 5 | Federated Learning | /Users/tejas/Documents/Fedrated Learning (misspelled on disk + space — use exactly) | none | dossiers/federated-learning.md |
| 6 | Job-Doot | /Users/tejas/Documents/personal-projects/job-doot | jobs.marutsut.me (planned, M6) | dossiers/job-doot.md |

**KNOWN_CONTEXT + EXTRA_SECTIONS per project:**

1. **Lens:** Sarvam AI Saaras v3 batch ASR + speaker diarization, IndicTrans2,
   Bulbul-v2 TTS, Gemini classification of patient lens responses (eye clinic
   video interpreter), Hindi/Hinglish production pipeline, React+TS+Vite frontend,
   FastAPI backend, Tejas bought own Sarvam credits. EXTRA: `## Pipeline Detail
   (upload → ASR → diarization → translation → classification → output)`.
2. **BluParrot:** Main = production FastAPI agri advisory, 6 engines (crop stage,
   irrigation, fertilizer, crop protection, yield, financial risk); Sentinel-2
   NDVI/NDWI time-series, Open-Meteo, Supabase (service-role), Groq, LangGraph,
   PuLP fertilizer LP, Rasterio. MUST also find + cover sub-projects (may be in
   sibling dirs like /Users/tejas/Documents/LangChain — spawn extra Explore to
   locate if needed): (a) Tanzania Horticulture RAG (ChromaDB, LaBSE, PDF
   ingestion); (b) Smart Query Assistant (LangGraph, MCP server, FAISS,
   deep-translator Hindi/Hinglish); (c) Bajaj vector search (Pinecone serverless
   AWS, Gemini embeddings 3072-dim, batch upsert); (d) Vapi voice calling agent
   (PG rental lead qualification, Hinglish); (e) DGQA over 450+ page defense
   tenders (LLM extraction/summarization → JSON) if it exists on disk.
   EXTRA: per-component sections (Problem/Architecture/Stack/Pipeline/Metrics each);
   `## Sub-Project Index`; bullets are COMPANY work → Experience section, not projects.
   15–25 resume bullets.
3. **Ekantik:** Source-grounded QA over 1300+ YouTube videos (Premanand Ji Maharaj
   discourses), refuses when answer absent; LangChain, ChromaDB persistent, MMR
   retrieval (capture k/fetch_k/lambda), chunking config, resumable idempotent
   ingestion w/ video-level dedup + timestamps, constrained generation prompt,
   FastAPI. EXTRA: `## Ingestion Pipeline Detail`, `## Retrieval & Generation
   Detail`, `## Neighboring Projects in /Users/tejas/Documents/LangChain (brief
   inventory, names + one-liners only)`.
4. **Smart Agri:** 6 DL models + 4 custom CNNs, PlantVillage (20,600 images, 15
   classes), EfficientNetB0 99.95% acc / 1.0 AUC / 92.5% precision / 89.8% recall,
   TF/Keras on M1 GPU (tensorflow-macos/-metal), FastAPI+Docker+Cloudflare Tunnel
   on Pi 5, <150ms. EXTRA: `## Models & Training Detail (all 10)`, `## Dataset
   Detail`, `## Inference Server`. Honesty flag focus: does 99.95% hold in
   notebooks, train vs test?
5. **Federated Learning:** Flower (flwr), FedAvg + FedProx (capture proximal mu),
   EfficientNet B1, non-IID partitioning (identify method), ~99% acc, ONNX export
   via tf2onnx + standalone verification. EXTRA: `## FL Detail (strategies, client
   count, rounds, partitioning, aggregation)`, `## ONNX Export & Verification`.
   Honesty flag focus: does 99% hold in recorded results?
6. **Job-Doot:** Naukri JSON-API + LinkedIn cookie scraper (drip thread 15–45min,
   activity simulation, SHA256 source_hash dedup), Groq llama-3.3-70b-versatile
   scorer/critic/improver loop with LOCKED_SKILL_SET + UNFIXABLE mechanism,
   LaTeX→PDF via tectonic, SQLite WAL, APScheduler 6am IST, FastAPI dashboard +
   session auth, Gmail watcher container + Telegram alerts, Docker compose.
   EXTRA: `## Agent Loop Detail`, `## Scraper Detail`, `## Database Schema`,
   `## Notifications`, `## Deployment Plan (DEPLOY.md summary)`, `## Neighboring
   Projects in /Users/tejas/Documents/personal-projects (brief inventory)`.
   WARNING in prompt: do NOT modify backend/agents/prompts.py or
   backend/master_resume.tex (another workstream edits those).

## 7. Resume instructions for next session (TL;DR)

1. Read this file + memory `project-m3-state` + `project-tejas-skills`.
2. Launch batch 1 (BluParrot, Lens, Smart Agri) per §5/§6. When done, batch 2.
3. Verify all 6 dossiers exist and are non-trivial (each should be hundreds of lines).
4. Run synthesis phase (§2.2): skills/ notes + MASTER-MATRIX.md + HOME.md.
5. Tell Tejas to open `/Users/tejas/Documents/personal-projects/job-doot/.claude/research`
   as an Obsidian vault to see the graph.
6. Proceed to M3 file updates (§2.3) — get Tejas's go before editing.
