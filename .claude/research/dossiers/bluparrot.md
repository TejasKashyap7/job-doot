---
title: BluParrot (Internship Work)
type: project-dossier
path: /Users/tejas/Documents/BluParrot
deployed: none (internal company systems)
tags: [langgraph, groq, sentinel-2, supabase, fastapi, pinecone, chromadb, faiss, mcp, vapi, gemini, bigquery, qdrant]
status: COMPLETE — merged from spec-analyst + code-analyst reports + direct verification, 2026-06-12
---

# BluParrot (Internship Work) — Full Dossier

## TL;DR
Tejas's internship at Blu Parrot Ventures spans **13+ projects**: a production-grade agricultural decision-intelligence platform (6 advisory engines over [[sentinel-2]] satellite, [[open-meteo]] weather, SoilGrids and [[supabase]] farm data — both a rule-based reference implementation and three spec-driven RAG variants), a defense-tender DGQA pipeline ([[gemini]] 2.5 Flash structured extraction over 450+ page PDFs), an insurance vector-search chatbot ([[pinecone]] 3072-dim), an enterprise SQL agent for Bajaj Capital RMs ([[langgraph]] + [[bigquery]] + Redis), a cross-lingual multi-source RAG assistant ([[labse]] + [[mcp]] + [[faiss]]), an HS-code classification chatbot, a video-QA system ([[qdrant]]), and a Hinglish voice-calling agent spec ([[vapi]]). Dominant patterns: spec-driven development (40+ spec docs in the Tanzania repos), abstract provider classes for LLM/vector-DB swappability, evidence-checked no-inference extraction, and dual-path (deterministic fast path + LLM fallback) architectures.

## Sub-Project Index

| # | Component | Path | One-liner |
|---|-----------|------|-----------|
| 1 | Agri (rule-based reference) | `BluParrot/Agri` | 6-engine crop advisory, pure Python rules + LP optimization; benchmark/reference system |
| 2 | Agri-integrated (unified API) | `BluParrot/Agri-integrated` | Single [[fastapi]] service wrapping all 6 engines + satellite + soil + weather fetchers |
| 3 | agri-rag-apple | `BluParrot/agri-rag-apple` | Apple-crop RAG variant — [[chromadb]], spec-driven, React frontend |
| 4 | agri-tanzania-horticulture | `BluParrot/agri-tanzania-horticulture` | Tanzania horticulture RAG advisory — most complete instance (maize dataset, 40+ spec docs) |
| 5 | agri-tanzania-rag | `BluParrot/agri-tanzania-rag` | Later Tanzania iteration — adds alembic migrations, multi-doc ingest |
| 6 | Bajaj | `BluParrot/Bajaj` | Insurance-policy vector search — [[pinecone]] serverless + [[gemini]] embeddings (3072-dim) |
| 7 | DGQA | `BluParrot/DGQA` | Defense tender generation + 450+ page bid extraction/eligibility/scoring — Gemini 2.5 Flash |
| 8 | Smart Query Assistant | `BluParrot/Smart Query Assistant` | [[langgraph]] multi-source RAG (YouTube transcripts + Wikipedia via [[mcp]]), cross-lingual [[labse]] |
| 9 | bcl_chatbot | `BluParrot/bcl_chatbot` | Bajaj Capital RM SQL agent — LangGraph + [[bigquery]] + Redis checkpoints (see Honesty Flags re: docs-vs-code) |
| 10 | nimish-chat-bot | `BluParrot/nimish-chat-bot` | GCC HS-code lookup chatbot — [[groq]], multilingual-e5-small (384-dim), ChromaDB, SQLite compliance DB |
| 11 | parakh | `BluParrot/parakh` | EMPTY directory (verified) |
| 12 | sparqnow | `BluParrot/sparqnow` | Video Q&A with citation safety — Streamlit + LangGraph + [[qdrant]] + Gemini |
| 13 | deep-fake | `BluParrot/deep-fake` | EfficientNet-B4 + attention deepfake detector — model scaffold only, no training loop |
| 14 | Vapi voice agent ("Shambhu") | `/Users/tejas/Documents/personal-projects/vapi` | Gurgaon PG rental lead-qualification outbound caller — spec-only on disk (full section below) |

---

## Main Project: Agri Advisory (Agri / Agri-integrated)

### Problem & Purpose
Farm-level decision intelligence for smallholder farmers: given a farm (location, crop, sowing date) plus live satellite/weather/soil data, produce actionable advisories across six dimensions — crop stage, irrigation, fertilizer, crop protection, yield prediction, and loan-default financial risk. `Agri` is the rule-based reference implementation; `Agri-integrated` exposes all six engines as one production [[fastapi]] API (`POST /farm-advisory` returns all 6 engine outputs for a farm_id).

### Architecture
```
client → FastAPI (/farm-advisory, /engine5, /engine6, /combined, /health)
            │
            ├── data_fetchers: satellite.py (Sentinel Hub OAuth2 → NDVI/NDWI GeoTIFF via rasterio)
            │                  weather (Open-Meteo: 7d past + 5d forecast, no key)
            │                  soil (SoilGrids + PyTesseract OCR of soil reports + rapidfuzz district match)
            │                  user/farm profile (Supabase service-role)
            │
            └── engines 1–6 (pure Python modules, JSON-config-driven, zero hardcoded crop logic)
```
- **Stack:** Python 3.10 (conda env `pyTensor`), FastAPI ≥0.110, Pydantic ≥2.0, supabase ≥2.3, groq ≥1.0, numpy/scipy, pulp ≥2.7, pillow + pytesseract ≥0.3.10, rapidfuzz ≥3.0, rasterio + requests-oauthlib (satellite).

### Complete Tech Stack (evidence)

| Tech | Where used | Evidence |
|------|------------|----------|
| [[fastapi]] + Pydantic v2 | API surface, schemas | `Agri/api/main.py`, `api/schemas.py`, `requirements_api.txt` |
| [[supabase]] (PostgreSQL, service-role) | farm profiles, soil district master, commodity prices, crop HI config | `scripts/seed.py`, `seed_engine2_tables.py`, `.env.example` |
| [[sentinel-2]] via Sentinel Hub | NDVI/NDWI timeseries | `data_fetchers/satellite.py` (process API, B04/B08/B11 bands) |
| [[rasterio]] | GeoTIFF in-memory read, nanmean over cloud-edge NaNs | `data_fetchers/satellite.py` |
| [[open-meteo]] | weather past/forecast | `data_fetchers/weather.py` |
| SoilGrids + [[pytesseract]] OCR + [[rapidfuzz]] | soil nutrients; soil-report digitization; district fuzzy match | `data_fetchers/soil/` |
| scipy `linprog` (HiGHS) | Engine 3 least-cost fertilizer LP | `fertilizer_engine/optimizer.py` (PuLP in requirements but CBC fails on macOS arm64 — solver is scipy) |
| [[groq]] | Engine 4 pest-remedy prompts | `crop_protection_engine/` (model string not pinned in code) |

### Pipeline & Engine Detail

**Engine 1 — Crop Stage (S1–S5):** DAS from sowing date + NDVI trend (slope thresholds ±0.01) vs. expected per-stage behaviour → stage + confidence (base 0.90, penalties: possible 0.10 / suspicious 0.25 / strongly-suspicious 0.40 / unknown-NDVI 0.20). Phenology config for **14 crops** (`crop_stage_config.json`), e.g. maize S1 Establishment 0–14 DAS … S5 Maturity 96–200 DAS.

**Engine 2 — Irrigation:** composite score `(100−soil_moisture)×0.4 + temp_score×0.2 + stage_score×0.2 − capped_rainfall`; threshold 25.0 triggers irrigation. Stage-based base water (e.g. Vegetative 40mm / 7-day frequency) × soil multiplier (sandy 1.3, clay 0.8) − 0.7×forecast rain. Liters = mm × area (4046 m²/acre); pump runtime = liters/(LPM×60×0.85 efficiency), 10h max continuous. Overrides: >30mm rain cancels; soil moisture <20% in critical stage ignores rain penalty. Urgency cutoffs SM 30%/60%. Risk engine detects Water Stress / Heat Stress / Waterlogging / Dry Spell.

**Engine 3 — Fertilizer (least-cost LP):** stage-based N/P/K demand lookup → soil adjustments (OC<0.8% → +10% N, <0.5% → +15%; pH<6.5 → +15% P; >7.8 → +10% P) → NDVI<0.40 stress → +15% all doses → LP: minimize Σ price·x subject to nutrient coverage, 0≤x≤200kg per fertilizer. 9 fertilizers (UREA 46-0-0, DAP 18-48-0, MOP 0-0-60, SSP, CAN, SOP, NPK 10:26:26/12:32:16/19:19:19). Hard caps N 220 / P 120 / K 160 kg/acre. INM split-schedule bounds 0.70–1.40× of scheduled dose; basal + 2–3 splits; fertigation option for drip. Crops: maize/wheat/sugarcane/rice (basal+INM), cotton/soybean (basal only).

**Engine 4 — Crop Protection:** dual sub-engine. (a) IPM schedule engine — per-crop per-DAS preventive sprays (±2-day DAS tolerance); (b) condition-rule engine — weather rules (humidity/temp/rain bands) → disease risk alerts. Guardrails layer: PHI buffer 2 days vs. days-to-harvest, rain >10mm delays foliar spray, wind >20 km/h skips (drift), temp >35°C flags phytotoxicity (sulfur/oil). Max 3 treatments per alert. Preventive and reactive (Plantix detection input) modes.

**Engine 5 — Yield + Harvest Window:** NDVI peak → decline to 0.8×peak = maturity (min 120 DAS, fallback sowing+150); harvest window 21 days, per-day weather risk classification, 7-day pre-maturity lookback under extreme weather. Biomass `AGB = exp(a·NDVI + a·EVI + a·NDWI) + offset` (per-crop literature coefficients); yield = AGB × harvest-index (maize 0.50, wheat 0.48, rice 0.55; NDWI-stress-adjusted) × stress_factor. Confidence: base 0.90 − penalties (weather missing 0.10, model 0.08, HI default 0.05).

**Engine 6 — Financial Risk:** loan coverage ratio = projected harvest value / outstanding loan → base risk tiers (≥2.5× → 5%; 2.0 → 10%; 1.5 → 20%; 1.0 → 35%; 0.5 → 50%; else 70%, floor 85%) + additive penalties (yield volatility >0.4 → +15%; NDVI volatility >0.2 → +12%; drought none/mild/moderate/severe → 0/8/20/40%; repayment good/average/poor → 0/12/25%). Cap 0.95. Categories: ≤0.15 Low, ≤0.45 Moderate, else High. Per-field confidence accounting (base 0.70, +0.10 required / +0.05 optional field). Commodity modal-price lookup by state/district/market/variety/grade via Supabase.

### Metrics & Hard Numbers
- Satellite: 5-day revisit steps ±2-day window, ≤20% cloud cover, NDVI=(B08−B04)/(B08+B04), NDWI=(B08−B11)/(B08+B11), FLOAT32 2-band GeoTIFF, 30s request timeout. **No caching → ~150 API calls per 14-month farm; ~200 advisories exhaust a 29-day Sentinel Hub trial.** First-call latency for long-running farms 90–180s (satellite-bound, not LLM-bound).
- 5 seeded test farms (F124 maize Karnal drip … F128 no active season) exercising full/partial/skip paths.
- All thresholds above are code constants with file evidence (`config.py` per engine).

---

## Tanzania RAG Family (agri-tanzania-horticulture / agri-tanzania-rag / agri-rag-apple)

### Problem & Purpose
Same 6-engine advisory, re-architected as a **knowledge-base-driven RAG system**: "We are not coding logic, we are storing knowledge and prompting logic. Data is dynamic, versions are controlled, LLM uses latest truth." Agronomy documents are ingested, validated, versioned and embedded; engines retrieve the active document set and prompt an LLM. Built so the client can hand-off and maintain it without touching code.

### Architecture — Part 1 ingestion (LOCKED), Part 2 RAG (future)
`Upload → Pre-Process → Heuristic Filter → LLM Classify (auto-approve ≥90% confidence, else 30-min pending TTL) → Extract Structured JSON with *_source fields → Evidence Checker → Validate → Version Check → Metadata → Embed → ChromaDB`
- **Evidence checker (no-inference rule):** every extracted value must be a verbatim substring of the source document; numeric fields require nearest-keyword match (`FIELD_KEYWORDS` + `_ALL_KEYWORDS` distractor list). Failures route to human review — never silent acceptance. (`app/pipeline/evidence_checker.py`)
- **Versioning:** `doc_key = {crop}_{type}`; exactly one `is_active=true` per key; rollback = keep old active until new confirmed.
- **Deliberate Phase-1 constraints (documented in decisions.md):** 1 document = 1 chunk; metadata-only filtering (no semantic ranking); no auto-fix on validation failure; fail-fast preprocessing.
- **Swappability:** abstract `LLMProvider` (`app/llm/base.py`) — currently Gemini 2.5 Flash (switched from Groq), one-class swap; abstract `VectorStore` (`app/storage/vector_store.py`) — ChromaDB now, Pinecone/Weaviate migration path documented, 9-field metadata contract, every query filters `is_active=true`.
- Stack pins: fastapi 0.135.3, chromadb 1.5.5, sentence-transformers 5.4.1, groq 1.1.2, google-generativeai 0.8.5, pydantic 2.12.5, pandas 3.0.2. Backend port 8001 (ui-fixed branch), frontend 5500, conda env `agri`.

### Pipeline & Engine Detail (RAG E1–E6, maize most complete)
- ChromaDB documents: maize_stage_definition v2, irrigation_parameters v5, fertigation_schedule v1 (DAS 0–50 only), ipm_schedule v2, yield_parameters v3, market_data v2.
- **E5 yield (7-step, v3):** pre-S3 check → filter EVI where das ≥ stage3_start (need ≥3 obs, else NDVI fallback) → regional coefficient lookup (`india_haryana` → `india` → `global_default`) → `biomass_t_ha = a·exp(b·avg_EVI)` ×404.686 (t/ha→kg/acre) × harvest_index 0.45; NDVI fallback `NDVI_peak × 7500` kg/acre (no 404.686). Regional (a,b): UP (2.84,3.1), Haryana/Punjab (2.72,3.0), MH (2.20,3.2), KA (2.10,3.3), TG/AP (2.05,3.4), India default (2.27,3.2), global (2.10,3.4). Harvest window: first S3+ NDVI ≤75% of peak → +1 to +10 days; >5mm rain inside window shifts forward; moisture tip from quality_benchmarks.
- **Client data contract** (`docs/FULLSTACK_DATA_CONTRACT.md`): pull `GET /farms/ids` → `GET /satellite/timeseries?farm_id=` → internal weather/soil fetch → run engines → `POST /webhooks/farm-advisory`. Server computes DAS itself. **NDWI must be Gao (1996) (NIR−SWIR)/(NIR+SWIR), NOT McFeeters** — wrong formula silently corrupts water stress. Carry-forward state per farm: E4 `last_alerts` dict, E5 `temp_stress_days`. Outstanding client asks: RQ-1 sowing_date (critical), RQ-2 loan/market price, RQ-3 farm_name.
- **Farmer language spec** (`docs/FARMER_ADVISORY_LANGUAGE_SPEC.md`): all farmer-facing text in selected regional language (hi/mr/sw...); banned terms list (DAS, NDVI, ETc, MAD, Kc, fertigation, PHI, biomass, confidence score...); never say "insufficient data".
- Test farms: F123 Green Valley UP (89 DAS), F-MAIZE-HR Karnal (62), F-MUNNAR-TEST Kerala (60, falls back to `india` coefficients), F-SANGLI-TEST MH (75).

### Known issues (admitted in CLAUDE.md)
F123/F124 missing farm_polygon → EVI diluted by ~1km² bbox fallback (√area square, 30m floor); financial_policy doc not ingested → E6 always "undetermined"; fertigation schedule stops at DAS 50 → E3 silent beyond; E5 needs NDVI peak+decline → pre-peak farms get fallback date only; E4 leaf-wetness proxy is a single global RH≥90%+T≥5°C rule that never fires for San Jose Scale (RH 50–80% band) — per-rule durations on roadmap.

---

## Smart Query Assistant

### Problem & Purpose
Multi-source agentic RAG answering questions about the CampusX LangChain/LangGraph YouTube course: retrieves from YouTube transcripts (vector DB) and Wikipedia (via [[mcp]]) in parallel, LLM-routes to the best source, keeps per-user conversation memory.

### Architecture & Stack
[[langgraph]] StateGraph: `thread_check → memory → [youtube_retriever ∥ wiki_retriever] → merge → decision (strict JSON routing: youtube|wiki|hybrid|fallback) → answer node → save → END`. LLM [[groq]] `llama-3.3-70b-versatile`; YouTube store [[chromadb]] with [[labse]] embeddings; memory store [[faiss]] per-thread with all-MiniLM-L6-v2; Wikipedia via `mcp` + `langchain-mcp-adapters` (Tejas also built a Wikipedia MCP server here); UI Streamlit + SQLite session persistence; API FastAPI.

### Pipeline Detail & Numbers
- Ingestion: yt-dlp playlist metadata → youtube-transcript-api (Hindi) → GoogleTranslator ([[deep-translator]]) Hindi→English in 2000-char segments → 1200-char chunks / 250 overlap → LaBSE → ChromaDB. **Corpus: 26 videos (13+13), 1,156 chunks.**
- **Cross-lingual trick:** English query retrieves Hindi chunks directly because LaBSE (109 languages) maps both into one vector space — translation happens *after* retrieval, only so the routing LLM can read the chunks.
- **Perf engineering:** model loading moved to FastAPI lifespan context — request latency **23s → 5–8s** (LaBSE 16s + MiniLM 7s loads were previously per-request).

---

## Bajaj Vector Search (Insurance Chatbot)

- **Purpose:** policy Q&A over Life/General insurance brochures for RMs.
- **Stack:** [[fastapi]] server (`Bajaj/server.py`); [[pinecone]] serverless index `bajaj-vector-search-index`; embeddings `models/gemini-embedding-001` (**3072-dim**, batch upsert via `embed_gemini.py`/`store_embeddings.py`); LLM `gemini-2.0-flash`.
- **Flow:** query → similarity retrieval k=10 → formatted context → Gemini with formal policy-grounded system prompt → answer + source filenames.
- **Endpoints:** `GET /` (index stats: vector count, dimension), `POST /chat` `{query}` → `{response, session_id, sources[]}`, `GET /health`.

---

## DGQA (Defense Tender Generation & Bid Evaluation)

### Problem & Purpose
Government/defense tendering: generate formal tender documents from structured JSON, then extract + evaluate vendor bids (450+ page PDFs) into structured comparisons, eligibility verdicts, and scores.

### Architecture & Stack
FastAPI (`api.py`): `/generate-tender`, `/process-bids/{tender_id}`, `/run-full-evaluation/{tender_id}`.
- **Tender generation** (`tender_generator.py`): `gemini-2.5-flash`, temperature 0, "Government Tender Drafting Assistant" role → 7-section `TenderDocument` Pydantic (manpower table, contract value in words+numerals, completion period, eligibility clauses, document list, turnover, security deposit forms).
- **Bid extraction** (`processing_bid.py`): PyPDFLoader (langchain-community) → full-text concat (no chunking — leans on Gemini's context window) → raw text persisted to `processed_bids/{tender}/{bid}/` → `.with_structured_output(BidStructuredOutput)`, temperature 0, **3-attempt retry**. Output schema: bid_metadata (incl. company experience years, office state, llm_summary), financial_details (avg annual turnover + years + cert flag), past_projects[] (client type Govt/PSU/Private, value, similarity flag), manpower_compliance[], certifications (MSME type/year, GST, blacklisting declaration).
- **Eligibility** (`bid_evaluation.py`, deterministic — not LLM): 7 rules (experience ≥ min, turnover ≥ min, office state, MSME cert type+year, GST, non-blacklisting, similar projects ≥ min count in N years).
- **Scoring** (`final_evaluation.py`): `ScoreBreakdown` (experience / past projects / financial / manpower / documentation) → `FinalScore` with disqualification reason.

This is the resume's "Document-Grounded QA over 450+ page defense tenders" claim — verified in code, though the LLM is **Gemini, not Groq**.

---

## BCL Chatbot (Bajaj Capital RM SQL Agent)

- **Purpose:** RMs ask natural-language questions about their book (clients, AUA, margin, incentives) against BigQuery `wealthmaker_prod_fz`.
- **Dual-path design:** (1) deterministic fast path (~80% target): rule classifiers → parameterized SQL templates (hypothetical incentive calc, margin advice, client category/status counts, AUA, date-ranged total margin); (2) LangGraph fallback: `list_tables (JSON allow-list) → call_get_schema → get_schema (local schema.json — no INFORMATION_SCHEMA calls) → generate_query → run_query → final_response`.
- **Multi-tenancy enforced at SQL-generation time:** every reference to `MV_LOGIN_MARGIN_PRODUCTS_API` is rewritten to a `payroll_id`-scoped sub-select; payroll_id required in every request.
- **Memory:** Redis RedisSaver checkpointer, TTL 1440s refreshed on read; last **64 messages** to the LLM, full history retained. **Resilience:** 5-attempt exponential backoff on Gemini 429/quota → HTTP 429. **Logging:** PostgreSQL audit; secrets via GCP Secret Manager; Docker; LLM `gemini-2.5-flash`. CORS currently `["*"]` (flagged in docs to tighten).
- **Incentive calculator** (`incentives.py`): CTC/revenue eligibility threshold + four boosters (Upfront Champion, Retirement Expounder, Wealth Creator, White Knight).

---

## Nimish Chat-Bot (GCC HS-Code Classification)

- **Purpose:** walk a trader through the GCC Common Customs Tariff (2022, 12-digit codes) to classify a product basket; exportable results (CSV/PDF/Email). Spec locked v1.0 (`.claude/specs/hs-code-chatbot.md`).
- **7-state conversation machine:** input normalizer (rapidfuzz + pyspellchecker spell-fix; >30% change → "did you mean"; Hindi/Hinglish detection with matched-language responses) → intent classifier → product discovery loop (category table, 1–2 drill-down questions, basket accumulator CC1..CCn) → confirmation screen → batch RAG (parallel embedding, top-3 chunks/item, chapter metadata filter) → streaming generation (**codes only from retrieved context — never hallucinate**) → results table.
- **Stack:** FastAPI; Groq `llama-3.3-70b-versatile` + fast `llama-3.1-8b-instant`; embeddings `intfloat/multilingual-e5-small` (**384-dim**, batch 32); ChromaDB persistent (`hs_codes` collection, 1,156 chunks from PDF); SQLite sessions (TTL 7200s); MAX_RSS_MB 1024. (Spec mentions Qdrant + Next.js + Claude `claude-sonnet-4-20250514` for generation; `.env.example` shows Groq+Chroma — stack evolved; see Honesty Flags.)
- **Compliance subsystem (verified):** Qatar customs JSON → SQLite 4-table normalized schema (oga / document / hs_oga_document / ingestion_log) — **4,004 HS codes, 12 OGAs, 53 unique documents**, "Bill of Lading" deduped once and referenced 1,847×, idempotent re-runs (0 new / 4,004 updated, stable row counts), 9 records skipped (non-200).
- **Costing analysis (COSTING.md):** at 1,000 users / 2,500 conversations / 30M tokens per month: Gemini 2.0 Flash ~₹420/mo AI cost, all-in ~₹4,000/mo, **~₹3.50 per active user, ~₹1.40 per conversation**; sensitivity table for 5k/10k users.

---

## Vapi Voice Calling Agent ("Shambhu" — Gurgaon PG AI Calling Agent)

**Location: `/Users/tejas/Documents/personal-projects/vapi`** (NOT inside the BluParrot dir — sits under personal-projects; only 3 files on disk: `PROJECT_SPEC.md`, `FEATURES.md`, `.claude/settings.local.json`). Verified by direct read 2026-06-12.

### Problem & Purpose
A Gurgaon PG/property owner receives leads from portals as Excel sheets (name + phone + minimal metadata); humans manually call each lead with repetitive qualification questions, explain availability, schedule visits, follow up — operationally heavy, doesn't scale. Goal: an AI voice agent named **Shambhu** ([[vapi]]) that (1) calls leads automatically, (2) asks structured qualification questions, (3) extracts structured data, (4) matches needs against available properties, (5) schedules visits, (6) follows up automatically. "Humans still close deals — AI only qualifies and schedules."

### Architecture
- **Calling platform:** [[vapi]] — assistant "Shambhu", outbound calls via `POST /call` with assistant ID + customer phone.
- **LLM:** [[groq]] `llama-3.1-8b-instant` (per spec stack table).
- **Voice:** Vapi built-in voice "Elliot". **Transcription:** Google [[gemini]] 2.0 Flash.
- **Workflow engine:** [[n8n]] self-hosted via [[docker]]; **tunnel:** ngrok (`ngrok http 5678`, free-tier URL rotates on every restart — server URL must be re-set in Vapi dashboard after each restart).
- **Storage:** [[google-sheets]] as POC database (leads tab + Visits tab; phone number as unique key); PostgreSQL planned later.
- **Data path:** n8n polls sheet for `status=new` leads → fires Vapi outbound call → Vapi posts `end-of-call-report` webhook (transcript, summary, tool-call results, duration, recording URL) to ngrok→n8n → n8n parses `save_lead_data` tool result (LLM-parse-of-summary fallback if tool wasn't called) → writes back to sheet → WhatsApp alert to owner for interested leads.
- **Vapi tools registered:** `save_lead_data` (end-of-call structured JSON), `schedule_visit` (name, phone, property_id, visit_date, visit_time → Visits tab, confirmation string returned to agent), `check_availability` (deferred — POC hardcodes 4 properties in the system prompt).

### Pipeline & Engine Detail
- **8-step Hinglish conversation flow** (system prompt entirely in Hinglish, warm/non-robotic, Gurgaon/Delhi slang): Opener ("Namaste! Main Shambhu bol raha hoon, Gurgaon PG Solutions se...") → Location → boys/girls PG type → Budget + meals → Move-in timing → Property suggestion (top 1–2 matches on sector + pg_type + budget) → Visit scheduling → Close.
- **Location intelligence:** hardcoded fuzzy landmark→sector dictionary in the system prompt, 13 entries, e.g. "ey office"/"ernst young"→Sector 44, "cyber hub"→DLF Phase 2, "huda metro"/"iffco chowk"→Sector 29, "pani ki tanki"→Sector 45, "medanta"→Sector 38. Unknown input → clarifying question ("Kaunsi company mein kaam karte ho?"). Google Maps API + embeddings deferred to later phase.
- **Structured output JSON per call:** 15 fields — lead_name, phone, looking_now, preferred_sector, original_location_input, pg_type, budget, meals_preference, move_in_timing, visit_scheduled, visit_date, visit_time, matched_property_id, call_outcome, notes.
- **Call outcomes enum:** `visit_scheduled | callback_requested | not_interested | no_answer | wrong_number` (+ `dnd` from F07).
- **Lead lifecycle states:** `new → called → qualified → visit_scheduled → visited → closed`, plus `cold` and `dnd`.
- **Ops policies (FEATURES.md, 30 features F01–F30, priority-tagged POC/Soon/Later):** retry on no_answer after 3 hrs, max 3 attempts then `cold` (optional reactivation after 30 days); call time gating 10:00–19:00 IST; duplicate detection by phone; DND detection from "call mat karo"; lead polling every 30 min; daily 8pm summary + 9am visit sheet to owner via WhatsApp.

### Metrics & Hard Numbers
- 4 placeholder properties (₹10,000–₹14,000/month; e.g., P2 Sector 44 boys ₹14,000 meals included). 13-entry location dictionary. 15-field output schema. 30 enumerated features. 3 retry attempts / 3-hour retry delay / 30-min poll / 10am–7pm IST window. 2-week POC build plan (day-by-day).
- **Status per docs:** Day 1 checkmarks only — "Shambhu assistant created on Vapi ✓", "PROJECT_SPEC.md + FEATURES.md written ✓". No n8n workflow exports, no code on disk.

### Honesty note (local)
This is **spec-only on disk**. The Vapi assistant itself was configured in the Vapi dashboard (cloud), so there is no local code evidence of the system prompt, tools, or n8n flows. Resume bullets from this project should be framed as POC/spec-and-dashboard work unless Tejas confirms the n8n pipeline was actually built. Also ambiguous whether this is BluParrot company work or personal — it lives in `personal-projects/`, but the spec reads like client work for a property owner.

---

## Other Directories

- **sparqnow** (`rag-flow4` + `tejas_backup` duplicate): single-video Q&A with citation safety — Streamlit UI, [[langgraph]], [[qdrant]] client 1.16.1, sentence-transformers 2.7.0, google-genai; quote highlighting (regex over double-quoted spans), claim risk classification (factual/hypothetical/opinionated), timestamp formatting, Supabase/Redis in the dependency stack.
- **deep-fake:** EfficientNet-B4 (ImageNet) + attention layer (Conv2D 64→1 sigmoid, element-wise multiply) → GAP → BN + Dropout(0.5) → Dense(128) → sigmoid binary head; 256×256 input, Adam 1e-4, binary_crossentropy, accuracy+AUC. **Scaffold only — no training loop or data loading.**
- **parakh:** empty placeholder.
- **bcl_chatbot on disk:** ARCHITECTURE.md + PlantUML + SQL dump (see Honesty Flags).

## Deployment & Infra
- All systems are internal/company — no public URLs. FastAPI + Uvicorn everywhere; Docker for BCL; Supabase as managed Postgres; GCP (BigQuery, Secret Manager) for BCL; Redis for sessions; `.env` files present in 13 project dirs (existence only — no values recorded).
- Explicit separation of concerns documented: AI/RAG pipeline in-scope; CORS/auth/multi-worker deployment marked out-of-scope for a separate team (inline SCOPE NOTE banners in routes + `docs/DEPLOYMENT_NOTES.md`).

## Spec-Driven Development Evidence
Strongest evidence in the Tanzania repos: **40+ spec docs** under `.claude/spec/` organized per engine (engine-1/ … Engine 6/, Data Ingestion Pipeline/, Chatbot - Agronomist Ingestion/), plus `PROJECT_OVERVIEW.md`, `PLAN.md`, `decisions.md` (architecture rationale), `CLAUDE.md` (ops + Known Issues), `FULLSTACK_DATA_CONTRACT.md`, `FARMER_ADVISORY_LANGUAGE_SPEC.md`, `DEPLOYMENT_NOTES.md`. Pattern: problem statement → phase boundaries locked → deliberate constraints with rationale → admitted flaws → migration paths. Same discipline in nimish (`.claude/specs/hs-code-chatbot.md` v1.0 locked, COSTING.md, FEATURES.md, ASSUMPTIONS.md) and vapi (PROJECT_SPEC.md, FEATURES.md F01–F30).

## Resume Raw Material (Experience section — company work)
1. Built a production farm-advisory API serving **6 advisory engines** (crop stage, irrigation, fertilizer, crop protection, yield, financial risk) over live [[sentinel-2]] NDVI/NDWI timeseries, [[open-meteo]] weather and SoilGrids soil data, with [[supabase]] farm profiles [verified-in-code]
2. Implemented satellite ingestion on Sentinel Hub process API — server-side band math (B04/B08/B11), 5-day revisit walk with ±2-day windows, 20% cloud filtering, [[rasterio]] in-memory GeoTIFF parsing [verified-in-code]
3. Designed a least-cost fertilizer optimizer as a linear program (scipy linprog/HiGHS) over 9 fertilizer compositions with agronomic constraints (soil OC/pH adjustments, NDVI stress, per-acre nutrient caps) [verified-in-code]
4. Built a yield-prediction engine from EVI biomass regression (`a·exp(b·EVI)` with 9 region-specific coefficient sets) including NDVI-decline maturity detection and weather-aware harvest-window selection [verified-in-code]
5. Built a loan-default risk scorer for farm credit: coverage-ratio tiers + volatility/drought/repayment penalties, with per-field confidence accounting [verified-in-code]
6. Designed a versioned agronomy knowledge pipeline (RAG): LLM classification with ≥90% auto-approve, structured extraction with verbatim-evidence checking (no-inference rule), doc_key versioning with single-active enforcement, [[chromadb]] storage [verified-in-code]
7. Wrote the client integration contract (webhook advisory delivery, carry-forward state per farm, Gao-1996 NDWI requirement) and a farmer-language spec banning technical jargon in regional-language output [docs-only → verified spec files]
8. Built DGQA: [[gemini]] 2.5 Flash structured extraction over 450+ page defense-tender PDFs → Pydantic bid schemas, deterministic 7-rule eligibility checking and weighted scoring [verified-in-code]
9. Built an insurance policy chatbot on [[pinecone]] serverless with 3072-dim `gemini-embedding-001` embeddings (batch upsert) and grounded Gemini answers with source attribution [verified-in-code]
10. Architected a multi-tenant SQL agent for wealth-management RMs: dual-path design (deterministic SQL templates + [[langgraph]] BigQuery agent), payroll-id scoping injected at SQL-generation time, Redis checkpointing (TTL 1440s, 64-message trim), 5-retry exponential backoff [docs-heavy — see Honesty Flags]
11. Built a cross-lingual multi-source RAG assistant: [[labse]] embeddings let English queries retrieve Hindi YouTube-transcript chunks (1,156 chunks, 26 videos); parallel Wikipedia retrieval via a custom [[mcp]] server; LLM source-routing in a LangGraph StateGraph [verified-in-code]
12. Cut RAG request latency **23s → 5–8s** by moving embedding-model loading into the FastAPI lifespan [docs-only, plausible]
13. Built an HS-code classification chatbot for GCC customs tariff (12-digit codes): 7-state conversation machine, multilingual-e5-small (384-dim) retrieval over 1,156 chunks, idempotent compliance DB ingestion (4,004 HS codes, 12 agencies, 53 documents) [verified-in-code]
14. Produced a per-user cost model for chatbot deployment (~₹3.50/user/month at 1,000 users; 30M tokens/month across provider comparison) [docs-only]
15. Spec'd and configured a Hinglish outbound voice-calling agent ([[vapi]] + n8n + Google Sheets) for rental lead qualification — 8-step conversation flow, 15-field structured call output, retry/DND/time-gating policies [docs-only — spec + dashboard work]
16. Practiced spec-driven development across all projects: 40+ engine specs, locked phase boundaries, decisions logs, admitted known-issues registers [verified — spec files on disk]

## Interview Depth
- **Why RAG for agronomy instead of code?** Knowledge changes per crop/region/client; versioned documents + prompted logic let agronomists update truth without deploys. Tradeoff: Phase-1 locked to 1-doc-1-chunk and metadata filtering to avoid premature retrieval complexity.
- **Hallucination control:** evidence checker requires extracted values to be verbatim substrings with keyword proximity — failures go to humans. Same philosophy as job-doot's locked skill set ([[job-doot]]).
- **Cost engineering:** Sentinel Hub trial burn (200 advisories), per-conversation chatbot costing, Redis TTL + message trimming for token bounds — can discuss LLM unit economics concretely.
- **Multi-tenancy:** why scope at SQL-generation (rewrite to payroll-scoped sub-select) rather than post-hoc filtering.
- **Likely traps:** "Did you use PuLP?" — requirements list it but the working solver is scipy HiGGS/HiGHS (CBC broken on macOS arm64). "Which LLM in DGQA?" — Gemini 2.5 Flash, not Groq. "Is the Vapi agent live?" — POC/spec + dashboard config; n8n pipeline not evidenced on disk.

## Honesty Flags
1. **Vapi agent is spec-only on disk** — no code; Vapi-dashboard + spec work. Frame accordingly.
2. **bcl_chatbot directory contains docs (ARCHITECTURE.md + PlantUML + SQL dump), not the running code** — the code analyst's BCL detail is reconstructed from ARCHITECTURE.md. Before resume use, confirm where the actual code lives (likely a company repo not on this machine).
3. **parakh is empty; deep-fake is a model scaffold** (no training loop) — neither is resume material.
4. **Three near-identical RAG repos** (apple/tanzania-horticulture/tanzania-rag) — one architecture, three datasets. Count it once.
5. **Agri engine data is UAT-level** (nutrient tables, prices marked for replacement before production); E6 financial_policy never ingested → "undetermined" in practice.
6. **nimish spec vs env mismatch:** spec says Qdrant + Next.js + Claude; `.env.example` says ChromaDB + Groq. Stack evolved mid-project; pick the env-verified version when speaking.
7. **No deployed public URL for any BluParrot system** — "production" means client/internal use, not public.
8. **Groq model strings in Agri are not pinned in code** — say "Groq Llama-family" not a specific version unless confirmed.
