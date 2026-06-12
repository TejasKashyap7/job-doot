---
title: Ekantik Vartalap RAG
type: project-dossier
path: /Users/tejas/Documents/LangChain/Ekantik Project
deployed: https://ekantik.marutsut.me
tags: [langchain, chromadb, rag, labse, groq, fastapi, hindi, source-grounded]
status: COMPLETE — merged from spec-analyst + code-analyst reports, 2026-06-12
---

# Ekantik Vartalap RAG — Full Dossier

## TL;DR
A source-grounded Hindi QA system over the Ekantik Vartalap discourses of Premanand Ji Maharaj: 1,347 playlist videos discovered, **1,004 Hindi transcripts ingested** (~40k chunks) into a 684 MB persistent [[chromadb]] store with [[labse]] embeddings, served by a [[fastapi]] app ([[groq]] `openai/gpt-oss-120b`, temp 0.2) that answers **only** from retrieved discourse excerpts — citing ekantik numbers and refusing in plain Hindi when the answer isn't in the sources. Live at ekantik.marutsut.me on the Pi (native uvicorn, synced via a custom HTTP bridge over [[cloudflare-tunnel]]). The capstone of a deliberate topic-by-topic [[langchain]] self-study curriculum.

## Problem & Purpose
From the live homepage (Hindi): "answers are shown only for questions actually asked and answered in the Ekantik Vartalap sessions." It's a research/lookup tool for devotees — not a chatbot that speculates. Strong ethical guardrails: a dedicated disclaimer page ("experimental, non-commercial AI-assisted research project… does not claim spiritual authority"), per-answer verification notice, and mandatory source citations.

## Architecture
```
YouTube playlist (1,347 videos, Bhajan Marg channel)
  → yt-dlp --flat-playlist --dump-json  → ekantik_videos_v1.json (filter private/deleted/no-duration;
        regex r"^\s*#\s*(\d+)" extracts declared_ekantik_number from title)
  → youtube-transcript-api (languages=["hi"]) → transcripts/hindi/ekantik_{n}.json   [1,004 files]
  → RecursiveCharacterTextSplitter(1200, overlap 250, separators ["\n\n","\n","।"," ",""])  ← Hindi danda-aware
  → LaBSE (768-dim, local HF cache 1.8 GB) → ChromaDB "Ekantik_Vartalap" (684 MB, ~40k vectors)
  → FastAPI: POST /query → normalize_query_to_hindi (langdetect + GoogleTranslator en→hi)
        → MMR retriever (k=7, lambda_mult=1) → if no docs: refuse WITHOUT calling LLM
        → Groq openai/gpt-oss-120b (temp 0.2) with grounding prompt → Hindi answer + ekantik citations
```

## Complete Tech Stack

| Tech | Where used | Evidence |
|------|------------|----------|
| [[langchain]] (community, core, text-splitters) | embeddings wrapper, Chroma wrapper, PromptTemplate, splitter | `FastAPI/ekantiks_api.py:35-71`, `phase1.ipynb` |
| [[chromadb]] persistent | vector store, collection `Ekantik_Vartalap` | `ekantiks_api.py:49-55`; 684 MB on disk (`chroma.sqlite3` 571 MB + HNSW index) |
| [[labse]] via HuggingFaceEmbeddings | 768-dim multilingual embeddings, local HF_HOME cache | `ekantiks_api.py:41-46` |
| [[groq]] via langchain_groq.ChatGroq | LLM `openai/gpt-oss-120b`, temperature 0.2 | `ekantiks_api.py:65-68` |
| [[mmr-retrieval]] | k=7, lambda_mult=1 | `ekantiks_api.py:103-105` |
| langdetect + [[deep-translator]] GoogleTranslator | en→hi query normalization | `ekantiks_api.py:136-163` |
| youtube-transcript-api + yt-dlp | ingestion | `phase1.ipynb` cells 9/15; documented yt-dlp command |
| [[fastapi]] + Jinja2 + vanilla JS frontend | 5 routes + Hindi UI | `ekantiks_api.py:13-197`, `frontend/` |
| python-dotenv | `.env` at `LangChain/.env` (Groq key; existence only) | `ekantiks_api.py:58-60` |

## Ingestion Pipeline Detail
1. **Playlist sweep:** yt-dlp flat-playlist dump → 1,347 entries; filtered for private/deleted/null-duration; ekantik number regexed from title; output `temp/ekantik_videos_v1.json`.
2. **Transcript fetch:** Hindi-only (`languages=["hi"]`); catches TranscriptsDisabled/NoTranscriptFound; failures logged to `transcript_failures.json` (1 recorded: ekantik_1055). Naming: `ekantik_{n}.json`, fallback `video_{youtube_id}.json`.
3. **Resumability (two layers):** file-level — skip if output JSON already exists; **vector-level idempotency** — `video_already_ingested()` queries Chroma `where={"video_id": ...}, limit=1` and skips the whole video if present. Dedup key = `video_id`.
4. **Transcript JSON preserves timestamps** (`snippets[].start/duration`) — but chunk metadata keeps only `video_id`, `declared_ekantik_number`, `language` (timestamps lost at chunk level; see Honesty Flags).
5. **Chunking:** 1200 chars / 250 overlap with Hindi-aware separators (Devanagari danda `।` ranked above space) — ~40 chunks per transcript (e.g., ekantik_1107), ≈40k chunks total.

## Retrieval & Generation Detail
- **MMR with lambda_mult=1** — deliberately degenerates to pure relevance (no diversity penalty); k=7.
- **Token-saving refusal path:** if the retriever returns nothing, the LLM is never called — the canned Hindi refusal (with contact email) is returned directly.
- **Grounding prompt (verbatim, `ekantiks_api.py:73-101`):** "आप श्री प्रेमानंद जी महाराज के प्रवचनों पर आधारित उत्तर देने वाले सहायक हैं… आपको **केवल इन्हीं अंशों के आधार पर** उत्तर देना है… उत्तर 6–10 पंक्तियों में… अपनी ओर से कोई नई बात न जोड़ें… उत्तर के अंत में संबंधित declared_ekantik_number अवश्य लिखें… यदि उत्तर स्पष्ट रूप से उपलब्ध न हो, तो साफ लिखें: 'इस प्रश्न का उत्तर दिए गए प्रवचनों में स्पष्ट रूप से नहीं मिलता'"
- **Language handling:** langdetect; en → GoogleTranslator en→hi; hi → unchanged; any other language passes through (LaBSE's cross-lingual space still gives a chance of retrieval).

## Endpoints / Interfaces
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Hindi landing page (project mission) |
| GET | `/ask` | question form (textarea + async JS fetch) |
| POST | `/query?query=` | the RAG endpoint — returns plain text answer |
| GET | `/contact` | contact/attribution |
| GET | `/disclaimer` | ethics & limitations page |
Static: `main.css` (blue #0b3c6f / yellow #f4c430 theme), `ask.js` (35 lines), Radha Keli Kunj logo.

## Metrics & Hard Numbers
1,347 playlist videos · 1,004 transcripts ingested · 1 logged failure · chunk 1200/250 · k=7 · temp 0.2 · 6–10-line answers · ChromaDB 684 MB (sqlite 571 MB) · LaBSE cache 1.8 GB · transcripts 106 MB · ~40k chunks · videos run ~60–83 min each · deployment zips ~297 MB · upload chunking 64 KB with 20 MB progress logging and 1h timeout.

## Deployment & Infra
- **Pi-native, no Docker:** uvicorn directly on the Pi (192.168.0.197, user tejasnewrasp), public via [[cloudflare-tunnel]] at ekantik.marutsut.me.
- **Custom deployment tool `send_to_pi.py`:** tars+gzips a folder and streams it (64 KB chunks, token header) to `https://bridge.marutsut.me/upload` — an HTTP upload bridge on the Pi through the tunnel, avoiding SSH/SCP. Used to sync the 684 MB ChromaDB.
- `deploment/` (sic) folder mirrors API+frontend for the Pi.
- Git repo: github.com/TejasKashyap7/ekantik. Timeline from file dates: playlist fetch Dec 2024 → transcripts Jan 2025 → deployed ~Jan 21, 2025 → refinements through May 2025.

## Spec-Driven Development Evidence
**Weak here (honest):** no CLAUDE.md, no .claude/specs — this project predates Tejas's spec-driven practice. Structure comes from three clearly-phased notebooks (`phase1/phase2/fastAPI.ipynb`) with strong inline documentation, an excellent engineered prompt, and explicit ethical pages. The spec discipline shows up in later projects ([[bluparrot]], [[federated-learning]], [[job-doot]]).

## Neighboring Projects in /Users/tejas/Documents/LangChain
The Ekantik Project sits inside a broader [[langchain]] learning workspace. Sibling directories (verified by listing 2026-06-12):

- **YTChatBot/** — precursor to Ekantik: YouTube chatbot notebooks (`ytChatBot.ipynb`, `ytChatBot_Dynamic.ipynb`) with `yt_vectors` / `yt_dynamic_vectors` stores. Clear evolutionary ancestor of the Ekantik RAG.
- **Agents/** — LangChain agents practice (Tool Calling, tools, AgentInWork).
- **Chains/** — `sequentialchians.ipynb` (sequential chains practice).
- **DocumentLoaders/** — `all_docLoader.ipynb` + sample PDF/TXT/CSV loads.
- **Models/** — ChatModels + Embeddings experiments.
- **Prompts/** — single-message vs message-list prompt experiments.
- **Retrivers/** (sic) — `retrivers.ipynb`, `vectorStoreRetrivers.ipynb`.
- **Structured_Output/** — dict-type / JSON-schema structured output experiments.
- **TextSplitters/** — `all_text_splitters.ipynb`.
- **vectorStore/** — `chroma.ipynb`, `FAISS.ipynb`, plus a Ramayana [[faiss]] index (`ramayana_faiss`) — earlier devotional-text vector experiment.
- Root: `requirments.txt` (sic), `test.ipynb`.

Takeaway: Ekantik is the capstone project of a deliberate, topic-by-topic LangChain self-study curriculum (loaders → splitters → embeddings → vector stores → retrievers → chains → agents → full product). Related deployed projects: [[job-doot]], [[bluparrot]], [[lens]], [[smart-agri]], [[federated-learning]].

## Resume Raw Material
1. Built and deployed a source-grounded Hindi RAG system over 1,300+ long-form discourse videos — answers only when the answer exists in transcripts, with mandatory source citations and a graceful Hindi refusal path [verified-in-code + live]
2. Implemented a resumable, idempotent ingestion pipeline: 1,004 Hindi transcripts fetched via youtube-transcript-api with file-level skip and vector-level `video_id` dedup against ChromaDB [verified-in-code]
3. Designed Hindi-aware chunking: RecursiveCharacterTextSplitter (1200/250) with Devanagari danda (।) as a first-class separator [verified-in-code]
4. Chose [[labse]] (768-dim, 109-language) embeddings so English queries retrieve Hindi chunks in one vector space; added langdetect + GoogleTranslator en→hi normalization on top [verified-in-code]
5. Cut LLM cost on unanswerable queries to zero — refusal is decided at retrieval time, before any Groq call [verified-in-code]
6. Engineered a constrained generation prompt (answers 6–10 lines, no new facts, cite every referenced ekantik number, scripted refusal sentence) [verified-in-code]
7. Operated a 684 MB persistent ChromaDB collection (~40k chunks) with MMR retrieval (k=7) on a Raspberry Pi [verified-on-disk + live]
8. Built a custom deployment bridge: chunked-streaming tar.gz uploads over a Cloudflare-tunneled HTTP endpoint (bridge.marutsut.me) to sync vector DBs to the Pi without SSH [verified-in-code]
9. Shipped a complete bilingual product: Hindi UI, ethics/disclaimer pages, per-answer verification notices [verified-live]

## Interview Depth
- **Why MMR with lambda_mult=1?** Honest answer: with λ=1 MMR reduces to pure relevance — the diversity knob was tried and effectively turned off; redundancy across discourses is acceptable because the prompt asks to cite *all* referenced ekantiks.
- **Why translate queries when LaBSE is cross-lingual?** Belt-and-braces: retrieval works cross-lingually, but the Hindi-only corpus + Hindi prompt mean a Hindi query string keeps the whole chain in one language.
- **Hallucination control:** three layers — retrieval-gated LLM call, source-only prompt with scripted refusal, citation requirement. Same philosophy later formalized in [[job-doot]]'s locked skill set and BluParrot's evidence checker.
- **What would you fix?** Sync endpoint is blocking (no async/streaming); timestamps lost at chunk level (no deep-link to video moment); `innerHTML` rendering (XSS risk); no rate limiting; deprecated LangChain wrappers; hardcoded absolute paths.

## Honesty Flags
1. **"1300+ videos" needs care:** 1,347 discovered, **1,004 transcripts actually ingested** (Hindi captions unavailable for the rest). Say "1,300+ videos processed, 1,000+ transcripts indexed".
2. **Timestamps are NOT preserved into the vector store** — memory/resume claims of "preserving timestamps" are true only of the raw transcript JSONs, not the retrieval layer.
3. **MMR's diversity is off (λ=1)** — don't claim "MMR-based semantic search for diversity" without the caveat.
4. **No Docker here** — Pi runs uvicorn natively; don't fold this into Docker claims.
5. Known code-quality gaps if probed: sync endpoint, no input validation/rate limiting, innerHTML, silent langdetect failures, hardcoded email in the refusal message, three duplicate 684 MB vector DB copies on disk.
6. LLM is Groq-hosted `openai/gpt-oss-120b` — an OSS model on Groq, NOT an OpenAI API product; phrase carefully.
