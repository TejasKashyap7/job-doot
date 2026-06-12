---
title: Lens
type: project-dossier
path: /Users/tejas/Documents/lens
deployed: https://lens.marutsut.me (403 currently)
tags: [sarvam-ai, gemini, react, typescript, fastapi, speaker-diarization, indic-ai]
verified: 2026-06-12
git-history: "709da11 2026-06-05 19:57 Initial commit — Lens eye clinic pipeline; 9a570a1 2026-06-05 22:51 Graceful partial recovery when classification fails"
---

# Lens — Full Dossier

## TL;DR (one paragraph)

Lens is a batch video-understanding pipeline plus a polished demo site that takes a raw eye-clinic checkup recording (file upload or YouTube URL), strips the audio with [[ffmpeg]], transcribes and speaker-diarizes it with [[sarvam-ai]] Saaras v3 Batch API (auto language detection across Hindi/Punjabi/Haryanvi/Rajasthani/Hinglish), uses [[gemini]] 2.5 Flash twice — first to assign Doctor/Patient/Irrelevant roles from conversational patterns, then to extract and classify every patient response to a lens-check question as Clear/Unclear/Doable/Other with timestamps and confidence — and validates the LLM output against the transcript verbatim to kill hallucinations. Backend is [[fastapi]] with background-task jobs and a polling status API; frontend is [[react]] 18 + [[typescript]] + [[vite]] with [[tailwind-css]], [[framer-motion]], and [[lucide-react]]. It was built in essentially **one day (5 June 2026, two commits)** as a spec-first POC explicitly designed as a cold pitch to **LensKart** ("Company X"): turn 10 minutes of video review into 10 seconds of timestamp-jumping. Deployed at lens.marutsut.me on the Pi (currently 403). **Important correction to received context: there is NO IndicTrans2 and NO Bulbul-v2 TTS anywhere in this codebase** — the pipeline is ASR + diarization + LLM classification only; descriptions are produced in English by Gemini, not by a translation model.

## Problem & Purpose

From `/Users/tejas/Documents/lens/.claude/specs/manager-submission.md`:

> Every eye checkup follows the same pattern. The optometrist changes a lens. The customer says something — *"saaf hai," "thoda blurry hai," "chal jayega."* … That verbal response from the customer — the one that happens after every single lens change — is the most valuable piece of information in the entire checkup. The problem is that right now, nobody is capturing it. … For fifty videos a day, that is someone's entire workday — just watching recordings.

From `/Users/tejas/Documents/lens/.claude/specs/overview.md`:

> A pipeline that takes a raw eye clinic video, transcribes it across multiple Indian speakers and languages, and produces a structured report of patient responses — classified as Clear, Unclear, or Doable.

**Business framing** (`.claude/specs/pitch-narrative.md` — "For Internal Use Only"): Lens is a deliberate cold-pitch POC for **LensKart's** store operations. The pitch script: "Your team then goes directly to those timestamps, watches 10 seconds of video instead of 10 minutes." The ask is a one-store, one-week pilot with real videos. The narrative doc even includes a "What to Say vs What Not to Say" section (never name Sarvam/Gemini/Google/OpenAI to the client; never reveal knowledge of their annotation team) and a strategy for letting LensKart connect the dots that human-confirmed timestamps become labelled training data for their own models.

**Input:** any video format (MP4/MOV/AVI…), any number of speakers, any Indic language or dialect (Hindi, Tamil, Haryanvi, Hinglish, Indian English…), variable audio quality.
**Output:** structured table — `timestamp_start, timestamp_end, original_text (verbatim), classification (Clear|Unclear|Doable|Other), description (plain English for a clinic reviewer), confidence (0.0–1.0)` — as JSON (and CSV per spec).
**Explicitly out of scope** (overview.md): visual analysis / lip reading, speakers beyond Doctor & Patient in the output table, real-time/streaming processing (batch only).

## Architecture

Four-phase batch pipeline orchestrated by `server/pipeline.py` (328 lines), exposed via a [[fastapi]] app (`server/app.py`, 74 lines) with an in-memory `JOBS` dict and FastAPI `BackgroundTasks` (no queue, no DB). Frontend polls job status every 3 s.

```
   User (React UI, port 5173)
        │  POST /api/upload (file)  or  POST /api/process (YouTube URL)
        ▼
   FastAPI (port 8000) ── returns job_id (uuid4[:8]) ── GET /api/status/{job_id} every 3s
        │  BackgroundTasks → run_pipeline / run_pipeline_file
        ▼
 [Phase 1] Audio Extraction        ffmpeg -ar 16000 -ac 1  (yt-dlp first for URLs)
        ▼  16 kHz mono WAV
 [Phase 2] Speech Analysis         Sarvam Saaras v3 Batch API (saaras:v3,
        │                          language_code="unknown", with_diarization,
        │                          with_timestamps; upload→Azure Blob presigned
        ▼                          URL; poll 5s × 120 = 10 min timeout)
 [Phase 3] Role Understanding      Gemini 2.5 Flash, JSON mode →
        ▼                          Doctor / Patient / Irrelevant per entry
 [Phase 4] Classification          Gemini 2.5 Flash, JSON mode, 3 retries
        │                          (15s/30s backoff) → Pydantic validation →
        │                          verbatim hallucination filter
        ▼
   JOBS[job_id] = { status: done|partial|error, results[], transcript[], stage_times{} }
```

**Key design decisions and rationale** (`.claude/specs/tech-stack.md`, `architecture.md`):
- **FFmpeg via raw subprocess** (no wrapper lib): "Handles every codec, container, and format without configuration."
- **Sarvam Batch API, not REST**: "Only mode that supports diarization. REST API (sync) does not." Diarization verified by a native speaker on Punjabi (100%), Haryanvi, Rajasthani.
- **Language detection `unknown`**: per-entry auto-detection rather than hardcoding a language — handles code-switching clinics.
- **Gemini 2.5 Flash for both LLM phases**: "Cheap, fast, strong multilingual." 1M-token context means a 1-hour video (~35K transcript tokens) needs no chunking. Cost analysis vs Claude Sonnet/GPT-4o: ~₹0.01/video vs ₹0.40 at 1000 videos/day.
- **Role assignment by conversational pattern, not voice**: "The Doctor asks and directs. The Patient answers and rarely directs. This conversational pattern is how Gemini identifies roles — not by language or voice." This also makes the pipeline survive total diarization failure (fallback collapses everything to one speaker; Gemini still infers roles from context).
- **Graceful degradation**: if Phase 4 fails after retries, the job ends in status `partial` — transcript with roles is still returned (commit `9a570a1`, "Graceful partial recovery when classification fails").
- **Scaling philosophy**: one video per instance; "Add Celery + Redis only when >10 concurrent videos become real."

## Complete Tech Stack

| Tech | Where used | Evidence (file:line) |
|---|---|---|
| [[python]] (3.11+ per spec; local pycache is 3.13) | backend | `.claude/specs/tech-stack.md:3`; `server/__pycache__/` |
| [[fastapi]] | HTTP server, CORS, BackgroundTasks | `server/app.py:8-9` |
| [[pydantic]] v2 | `PatientResponse` output validation (`.model_dump()`) | `server/pipeline.py:19,32-38,326` |
| [[uvicorn]] | run command in docstring | `server/app.py:3` (`uvicorn server.app:app --reload --port 8000`) |
| `requests` | all Sarvam HTTP calls | `server/pipeline.py:16` |
| `python-dotenv` | loads `.env` at repo root | `server/pipeline.py:17,21` |
| `google-genai` SDK | Gemini client | `server/pipeline.py:18,28` (`from google import genai`) |
| [[ffmpeg]] (CLI) | video→16kHz mono WAV | `server/pipeline.py:125-130` |
| [[yt-dlp]] (CLI) | YouTube audio download (`youtube:player_client=android`, `bestaudio/best`, `--no-playlist`) | `server/pipeline.py:136-141` |
| [[sarvam-ai]] Saaras v3 Batch API | ASR + [[speaker-diarization]] | `server/pipeline.py:25` (base URL), `:162` (`"saaras:v3"`) |
| [[gemini]] 2.5 Flash | role assignment + classification | `server/pipeline.py:29` (`MODEL = "gemini-2.5-flash"`) |
| [[react]] 18.3.1 + react-dom | SPA frontend | `ui/package.json:12-13` |
| [[typescript]] 5.5.3 (strict, noUnusedLocals/Parameters) | frontend | `ui/package.json:24`, `ui/tsconfig.json:14-17` |
| [[vite]] 5.3.4 (+ @vitejs/plugin-react 4.3.1) | build/dev server | `ui/package.json:25`, `ui/vite.config.ts` |
| [[tailwind-css]] 3.4.7 (+ postcss 8.4.40, autoprefixer 10.4.19) | styling; custom primary `#DEDBC8`, font "Instrument Serif" | `ui/package.json:23`, `ui/tailwind.config.js:6-11` |
| [[framer-motion]] 11.3.0 | all animations, `useInView`, `AnimatePresence`, signature easing `[0.16, 1, 0.3, 1]` | `ui/package.json:14`; used across all components |
| [[lucide-react]] 0.400.0 | ~18 icons (Scissors, Waves, Users, ListChecks, CheckCircle2, …) | `ui/package.json:15` |
| Google Fonts (Almarai 300/400/700/800, Instrument Serif italic) | typography via CDN | `ui/index.html:8-13` |
| Azure Blob Storage (Sarvam-managed) | audio upload target via presigned URLs | `server/pipeline.py:179-183` |

**Not present anywhere** (despite external claims): IndicTrans2, Bulbul-v2 TTS, any TTS, any database, [[docker]], nginx, [[cloudflare-tunnel]] config, requirements.txt, .env.example, tests beyond standalone scripts.

## Pipeline Detail

Two entry points, identical phases: `run_pipeline(job_id, youtube_url, jobs)` (`pipeline.py:79`) and `run_pipeline_file(job_id, video_path, jobs)` (`pipeline.py:43`). Each phase is wrapped in `asyncio.to_thread(...)` and timed with `time.time()`; per-stage seconds stored in `stage_times` (rounded to 0.1 s) so the UI shows real durations.

1. **Phase 1 — Audio Extraction** (`stage=1`, label "Audio Extraction"). URL path: `yt-dlp --extractor-args youtube:player_client=android -f bestaudio/best --no-playlist -o raw.%(ext)s` (`pipeline.py:136-141`), then both paths run `ffmpeg -i src -ar 16000 -ac 1 -y dst` → `audio.wav` (`pipeline.py:125-130`). ffmpeg failure raises with first 400 chars of stderr; yt-dlp failure with first 600.
2. **Phase 2 — Speech Analysis** (`stage=2`). `_sarvam_diarize` (`pipeline.py:155-218`), six HTTP steps against `https://api.sarvam.ai/speech-to-text/job/v1`:
   - POST create job with `{"model": "saaras:v3", "mode": "transcribe", "language_code": "unknown", "with_timestamps": true, "with_diarization": true}` → `job_id`
   - POST `/upload-files` → presigned Azure Blob URL
   - PUT audio bytes with `Content-Type: audio/wav`, **`x-ms-blob-type: BlockBlob`** (undocumented Azure requirement discovered during testing — `tech-stack.md`/`model-evaluation.md`) and explicit `Content-Length` (file read fully into memory so length is known)
   - POST `/{job_id}/start`
   - poll GET `/{job_id}/status` every **5 s**, max **120 iterations (10 min)**; `Completed` breaks, `Failed` raises, for-else raises timeout
   - POST `/download-files` requesting **`0.json`** (Sarvam names output by file_id, not input filename — another discovered quirk), GET the presigned download URL
   - Parse `diarized_transcript.entries` (speaker_id, start/end seconds, transcript). **Fallback** (`pipeline.py:209-217`): if empty, wrap the plain `transcript` field as a single entry with `speaker_id "0"` and 0.0 timestamps — Phase 3 still works from context.
3. **Phase 3 — Role Understanding** (`stage=3`). `_gemini_roles` (`pipeline.py:247-256`): single prompt, full transcript JSON inlined, `gemini-2.5-flash` with `response_mime_type: application/json`. Prompt (`:223-244`) assigns Doctor/Patient/Irrelevant; rules include "Songs or non-speech at the start → Irrelevant" and "If same speaker_id appears in different roles, use the dominant pattern." No retry on this phase.
4. **Phase 4 — Classification** (`stage=4`). `_gemini_classify` (`pipeline.py:294-327`):
   - Same model, JSON mode, **3 attempts with 15 s then 30 s sleeps** (for-else re-raises last exception)
   - Prompt (`:261-291`) has 9 numbered STRICT RULES — verbatim-only `original_text`, Patient-only, direct responses to vision-check questions only, "If the video is not an eye clinic session, return []", "Do not invent entries"
   - Non-list response → `[]`
   - Each entry validated through `PatientResponse` (Pydantic, `Literal["Clear","Unclear","Doable","Other"]`)
   - **Hallucination filter** (`:317-326`): builds `all_texts = {e["transcript"] for e in role_entries}` and drops any result whose `original_text` is not a verbatim substring of a real transcript line
5. **Terminal states**: success → `status "done", stage 5` with `results` + `transcript`; Phase-4-only failure → `"partial"` with transcript preserved and `results: []`; any earlier failure → `"error"`. `finally:` blocks `shutil.rmtree(..., ignore_errors=True)` the per-job temp dir (prefix `lens_{job_id}_`) and, for uploads, the upload temp dir.

## Endpoints / Interfaces

**Backend** (`server/app.py`; CORS allows only `http://localhost:5173`):

| Method | Path | Lines | Behavior |
|---|---|---|---|
| GET | `/api/health` | 32-34 | `{"ok": true}` |
| POST | `/api/process` | 37-50 | body `{url}` (Pydantic `ProcessRequest`); seeds `JOBS[job_id]` (status queued, stage 0); schedules `run_pipeline`; returns `{"job_id"}` (uuid4 first 8 chars) |
| POST | `/api/upload` | 53-66 | multipart file; saved to `tempfile.mkdtemp(prefix="lens_upload_")`; schedules `run_pipeline_file`; returns `{"job_id"}` |
| GET | `/api/status/{job_id}` | 69-73 | full job dict, or `{"error": "Job not found", "status": "error"}` |

No auth on any route (flaw #11, acknowledged in spec). No WebSocket/SSE — plain polling.

**Frontend** — single-page app, anchor-link navigation (Overview / How It Works / Try Demo / Contact), no router, no global state (local `useState` only). `App.tsx` renders four sections:

- **Hero.tsx** (254 lines) — "LENS" headline at 22–28vw, 8 concentric animated iris rings (120px→1260px, 3.2s→13s pulse durations), 3 drifting glow blobs (17–27s), 12 bokeh particles (7–22s), desktop pill nav + mobile hamburger, "75% review time saved" stat, `WordsPullUp` staggered text reveal.
- **HowItWorks.tsx** (130 lines) — 4 feature cards mirroring the pipeline (01 Audio Extraction "< 30s for a 15-min video", 02 Speech Analysis "Hindi, Punjabi, Haryanvi, Rajasthani, Hinglish", 03 Role Understanding, 04 Classification), staggered 0.12 s scale+fade.
- **Demo.tsx** (635 lines) — the workhorse: drag-drop/file upload, YouTube URL input, and a **mock demo mode** with hardcoded stage timings (2200/5500/3000/2500 ms ≈ 13.2 s total) plus 5 mock results and a 27-line mock transcript; real mode polls `GET /api/status/{job_id}` every **3000 ms** with silent catch-and-continue on network blips; renders live 4-stage progress with per-stage timings, handles `done`/`partial`/`error` distinctly (partial shows transcript with a classification-failed notice).
- **ResultsTable.tsx** (174 lines) — summary bar + responsive table (12-col grid desktop, stacked mobile), animated confidence bars, classification color coding: Clear `#86EFAC`, Unclear `#FCA5A5`, Doable `#FCD34D`, Other `#94A3B8`. Exports `ResponseEntry` TS interface (exact mirror of backend `PatientResponse`).
- **TranscriptView.tsx** (147 lines) — collapsible diarized transcript, Doctor/Patient entry counts in header, 520px max-height scroll, role badges (Doctor `#FCD34D`, Patient `#86EFAC`, Irrelevant gray). Exports `TranscriptEntry` interface.
- **WordsPullUp.tsx** (72 lines) — reusable word-by-word reveal (y:110%→0, 0.06–0.08 s stagger).
- **Contact.tsx** (100 lines) — phone `tel:9817135031`, email `mailto:tejas06012005@gmail.com`, LinkedIn link.

## Metrics & Hard Numbers

| Number | What | Source |
|---|---|---|
| 16000 Hz / 1 channel | ASR input WAV (ffmpeg `-ar 16000 -ac 1`) | `pipeline.py:126` |
| 5 s / 120 iters / 10 min | Sarvam poll interval / max polls / timeout | `pipeline.py:189-199` |
| 55 min + 5 min overlap | designed (NOT built) chunking for long videos | `tech-stack.md:17-21`, `flaws.md` #4 |
| 3 attempts; 15 s, 30 s | Gemini Phase-4 retry/backoff | `pipeline.py:299-310` |
| 3000 ms | frontend status poll interval | `Demo.tsx:9` |
| 2200/5500/3000/2500 ms (13.2 s) | mock demo stage durations | `Demo.tsx:21-24` |
| 8 chars | job ID length (uuid4 prefix) | `app.py:39` |
| 1M tokens / ~35K tokens | Gemini context vs 1-hour-video transcript | `architecture.md` |
| ~1500 tokens | transcript of a typical 5-min clinic video | `tech-stack.md` |
| ~₹21/day @100 videos; ~₹210/day @1000 (Gemini ₹1/₹10 + Sarvam ₹20/₹200) | cost model | `tech-stack.md` |
| ~₹0.01 vs ₹0.40 per video | Gemini 2.5 Flash vs Claude Sonnet cost comparison | `tech-stack.md` |
| 100% | Sarvam Punjabi transcription accuracy (native-speaker verified) | `tech-stack.md`, `model-evaluation.md` |
| 90 s | Punjabi overlapping-speech diarization test clip | `model-evaluation.md`; `samples/clip_punjabi_haryanvi_90s.wav` |
| 75% | "review time saved" marketing stat | `Hero.tsx:248` |
| < 30 s | claimed audio-extraction time for a 15-min video | `HowItWorks.tsx:13` |
| 2–4 min | expected Speech Analysis duration, longer videos | `Demo.tsx:574` comment |
| 5 langs verified-or-listed | Hindi, Punjabi, Haryanvi, Rajasthani, Hinglish (Tamil/Telugu/Bhojpuri untested) | `HowItWorks.tsx`, `model-evaluation.md` |
| port 8000 / 5173 | backend / Vite dev server | `app.py:3`, `app.py:18` |
| 400 / 600 chars | stderr truncation for ffmpeg / yt-dlp errors | `pipeline.py:130,143` |
| 2 commits, same day | entire git history (2026-06-05 19:57 and 22:51) | `git log` |
| 10 spec docs | `.claude/specs/*.md` written before/alongside code | directory listing |

## Deployment & Infra

- **Repo contains NO deployment artifacts**: no Dockerfile, no docker-compose, no nginx, no Cloudflare config, no requirements.txt, no CI. Git tracks only `server/` + `ui/` + `.gitignore` (22 files).
- **Local run**: `uvicorn server.app:app --reload --port 8000` (backend docstring) + `npm run dev` (Vite, 5173). Build: `tsc && vite build` → `ui/dist/` exists locally, so a production build has been made.
- **Deployed URL**: https://lens.marutsut.me — presumably served from the Raspberry Pi 5 behind the same [[cloudflare-tunnel]] used for other marutsut.me subdomains (cf. [[job-doot]] runbook), but **none of that wiring lives in this repo**. **Currently returns HTTP 403** (noted per mission; not investigated/fixed). Likely a tunnel-ingress or origin-auth misconfiguration; with the API CORS-locked to `localhost:5173`, even a working static deploy of the UI could not hit the backend cross-origin as coded.
- **Spec'd production posture** (`architecture.md:243-263`): any cloud VM/container, `X-API-Key` header auth, temp storage in `/tmp` cleaned per run, one video per instance, Celery + Redis only beyond 10 concurrent videos. None of this implemented.
- **Secrets**: `/Users/tejas/Documents/lens/.env` exists with `SARVAM_API_KEY` and `GEMINI_API_KEY` (live values present in the file; gitignored; no `.env.example`). The Sarvam key is on Tejas's own paid credits (free tier was consumed during testing — `flaws.md` #14). Values intentionally not reproduced here; **keys were visible in plaintext locally and should be rotated before any sharing of the machine/repo**.
- **Job state is in-memory only** — server restart loses all jobs.

## Spec-Driven Development Evidence

Strong, unusually disciplined for a one-day build. Ten markdown specs in `/Users/tejas/Documents/lens/.claude/specs/`, written before/around the code:

- `overview.md` — I/O contract, classification values, out-of-scope list
- `architecture.md` + `architecture-public.md` (a sanitized share-safe variant) — phase-by-phase design with prototype-vs-production split
- `tech-stack.md` — every tool choice with explicit rationale and rejected alternatives (Gemini vs Claude/GPT-4o cost table; Batch vs REST API)
- `model-evaluation.md` — empirical pre-build testing: Saaras v3 verified on real YouTube comedy sketches (not benchmarks) by a native Haryanvi/Punjabi speaker; 90-second overlapping-speech diarization test; Gemini tested on non-clinic audio to confirm it returns `[]` rather than hallucinating; documented two undocumented Sarvam quirks (`x-ms-blob-type: BlockBlob` header; output named `0.json`)
- `flaws.md` — a 20-item pre-mortem flaw tracker with severity tiers (Critical/Important/Moderate/Minor) and checkbox status; only #1 (classification labels) marked resolved — mirrors the flaw-resolution workflow used in [[job-doot]]
- `pitch-narrative.md`, `manager-onepager.md`, `manager-submission.md` — business/GTM docs targeting LensKart, including a scripted pitch and a "never name the vendors" rule
- `context-for-llm.md` — a hand-maintained LLM context file (slightly stale: says FastAPI "not built yet" while it is)
- Test scripts per phase in `test/` (sarvam_rest.py, sarvam_batch.py, sarvam_diarization.py, phase3_interpretation.py, phase4_classification.py) with real outputs preserved in `outputs/` — evidence each phase was proven standalone before integration.

## Resume Raw Material

1. Built an end-to-end Hindi/Hinglish medical-video analysis pipeline (eye-clinic lens checkups) — video → [[ffmpeg]] 16 kHz mono audio → [[sarvam-ai]] Saaras v3 batch ASR with [[speaker-diarization]] → [[gemini]] 2.5 Flash role assignment and response classification → validated JSON results. [verified-in-code]
2. Integrated Sarvam AI's 6-step async Batch ASR API (job create → presigned Azure Blob upload → start → 5 s polling with 10-min timeout → result download), reverse-engineering two undocumented requirements (`x-ms-blob-type: BlockBlob` upload header; results keyed as `0.json` by file_id). [verified-in-code]
3. Designed an LLM hallucination guard: every classified patient quote is rejected unless it appears verbatim as a substring of a real diarized transcript line, on top of Gemini JSON-mode + Pydantic `Literal` schema validation. [verified-in-code]
4. Achieved language-agnostic operation via Saaras v3 auto language detection (`language_code: "unknown"`), with diarization verified at 100% transcription accuracy on Punjabi by a native speaker; also tested on Haryanvi and Rajasthani clips. [docs-only — eval doc + sample files exist; no automated metric harness]
5. Implemented diarization-failure resilience: if Sarvam returns no speaker entries, the plain transcript is collapsed to a single pseudo-speaker and Doctor/Patient roles are still recovered by Gemini from conversational structure (who asks vs who answers) rather than voice. [verified-in-code]
6. Shipped graceful partial-failure UX: a dedicated `partial` job state preserves the role-labelled transcript when classification fails after 3 retries (15 s/30 s backoff), surfaced distinctly in the UI. [verified-in-code]
7. Built a [[fastapi]] async job server — upload or YouTube-URL ingestion (yt-dlp with Android player-client workaround), uuid job IDs, `BackgroundTasks` execution, per-stage wall-clock timing exposed via a polling status API, guaranteed temp-dir cleanup in `finally`. [verified-in-code]
8. Built the marketing + demo frontend in [[react]] 18 / [[typescript]] strict / [[vite]] / [[tailwind-css]] / [[framer-motion]] / [[lucide-react]]: animated 8-ring iris hero, live 4-stage pipeline visualization with real per-stage timings, classification results table with confidence bars, collapsible diarized transcript with role badges, plus a self-contained 13-second mock demo mode. [verified-in-code]
9. Network-resilient frontend polling: 3 s interval with silent retry on fetch failure until a terminal state (`done`/`partial`/`error`). [verified-in-code]
10. Cost-engineered the LLM layer: chose Gemini 2.5 Flash over Claude Sonnet/GPT-4o with a written cost model (~₹0.01 vs ₹0.40 per video; ~₹210/day total at 1000 videos/day including ASR). [docs-only]
11. Exploited Gemini's 1M-token context to classify entire 1-hour transcripts (~35K tokens) in a single prompt, eliminating transcript chunking. [docs-only rationale; single-prompt design verified-in-code]
12. Practiced spec-driven development: 10 design docs (architecture, tech-stack with rejected alternatives, model evaluation, 20-item severity-tiered flaw pre-mortem) authored before integration; each pipeline phase proven by a standalone test script with preserved outputs. [verified — docs and test artifacts on disk]
13. Designed prompt-level safety rails for a medical-adjacent domain: 9 strict classification rules including "if the video is not an eye clinic session, return []" — verified empirically against non-clinic audio. [verified-in-code + eval doc]
14. Framed and scripted a B2B POC pitch to LensKart (one-store pilot ask; human-in-the-loop review that doubles as labelled-dataset generation). [docs-only]
15. Built and demo-deployed in ~1 day (two commits, same evening) on personal Sarvam credits; deployed to lens.marutsut.me on a Raspberry Pi 5. [git-verified for timing; deployment wiring not in repo]

**Do NOT claim** (absent from code): IndicTrans2, Bulbul-v2 TTS, any TTS step, any translation model, batch chunking of long videos, databases, Docker, auth.

## Interview Depth

**Hard problems actually solved:**
- *Sarvam Batch API integration* — undocumented Azure Blob constraints (`x-ms-blob-type`, exact `Content-Length` requiring full in-memory read) and non-obvious output naming (`0.json`). Good story about debugging third-party APIs with thin docs.
- *Hallucination control without fine-tuning* — three stacked layers: JSON response mime-type, Pydantic `Literal` schema, and the verbatim-substring filter against the source transcript. Honest caveat: substring matching is conservative — Gemini quoting across two diarization segments, or normalizing whitespace/punctuation, would be silently dropped (false negatives traded for zero false positives; correct trade for a "jump to timestamp" reviewer tool).
- *Role assignment from dialogue structure* — diarization gives anonymous speaker IDs; mapping them to Doctor/Patient via the ask/answer pattern is robust to speaker-ID instability and even to diarization failure. Honest caveat: flaws.md #5 admits there's no defined behavior if Gemini can't determine roles.
- *Failure-mode taxonomy* — `done`/`partial`/`error` with per-stage timing telemetry; the second (and last) commit was specifically the partial-recovery path.

**Design tradeoffs to discuss:**
- Batch ASR (only diarization-capable mode) vs latency — minutes-scale processing is fine because the product is post-hoc review, not live.
- In-memory JOBS dict vs DB — deliberate POC scoping, written down in spec with the upgrade path (Celery+Redis threshold: >10 concurrent).
- Single mega-prompt vs chunked classification — 1M context makes chunking unnecessary up to ~1 hour; the >55-min plan (55-min chunks, 5-min overlap) is designed but unbuilt, and speaker-ID reset across chunks is an acknowledged unsolved problem (flaws.md #4).
- Gemini 2.5 Flash vs stronger models — cost table in tech-stack.md; classification is short-text, context-rich → cheap model suffices.

**Likely interview questions + honest answers:**
- *"How do you know the confidence scores mean anything?"* — I don't; flaws.md #16 explicitly flags them as uncalibrated, used only as a reviewer guide, never for auto-accept.
- *"What about Tamil/Telugu?"* — Untested (flaws.md #6); verified languages are Punjabi/Haryanvi/Rajasthani/Hindi. Hinglish code-switching is also flagged untested in docs despite the UI listing it.
- *"How does it scale to 50 stores?"* — Currently one video per instance, in-memory state; spec documents the Celery+Redis threshold and an Azure-to-Azure SAS-URL optimization (designed, unbuilt).
- *"Security?"* — No auth on endpoints (flaws.md #11), CORS pinned to localhost dev origin; spec'd `X-API-Key` for production. Honest: POC.
- *"Why not Whisper?"* — Sarvam is Indic-specialized with native diarization in one API; model-evaluation.md shows it was empirically verified on the exact dialects in scope by a native speaker.

## Honesty Flags

1. **IndicTrans2 and Bulbul-v2 TTS do NOT exist in this project.** Grep across the entire tree (excluding node_modules noise) finds zero references. Any external note attributing them to Lens is wrong — possibly conflated with another project (e.g. [[bluparrot]] or [[ekantik]] voice work). There is no translation step and no TTS step; English descriptions come from the Gemini prompt.
2. **"Saaras v3 + speaker diarization + Gemini classification" — fully verified in code.** Mission context was right on these.
3. **One-day project.** Entire git history is two commits on 2026-06-05 (19:57 and 22:51). The polish (specs, animated UI) makes it look longer-lived than it is. (An earlier sub-report said "4 June / 12 June" — git says both commits are 5 June.)
4. **19 of 20 tracked flaws unresolved** in `flaws.md`, including critical ones: long-video chunk merging undesigned, trigger mechanism undefined, results destination undefined, no auth, no logging, uncalibrated confidence.
5. **Demo mock mode** — Demo.tsx ships hardcoded mock results/transcript and fake stage timings (13.2 s). The real pipeline works, but anyone who saw "the demo" may have seen the mock. The "75% review time saved" hero stat and "< 30s extraction" card are marketing numbers with no measurement behind them.
6. **`context-for-llm.md` is stale** — claims the FastAPI server and end-to-end chaining are "not built yet"; both exist. Code beats docs here (in the project's favor).
7. **No requirements.txt / pyproject / .env.example / Docker / tests-as-tests** — Python deps are unpinned and implicit; `test/` scripts are gitignored dev scratch, not a test suite. `outputs/phase4_classification.json` is 2 bytes (`[]`) — the preserved Phase-4 artifact is an empty result.
8. **Deployment is off-repo.** lens.marutsut.me (403) has no corresponding config in the repo; the backend CORS allowlist (`http://localhost:5173` only) means the deployed UI could not talk to the API as committed — the deploy either runs modified code or only serves the static UI (with mock mode).
9. **Live API keys sit in plaintext `.env`** (gitignored, but present on disk). Sarvam key is on personal paid credits (free tier exhausted — flaws.md #14). Rotate before sharing anything.
10. **Pitch docs reveal intent** — `pitch-narrative.md` is a scripted LensKart cold pitch including instructions to conceal vendor names and insider knowledge. Fine for a personal repo, but don't surface that doc externally; use `architecture-public.md` (the sanitized variant) instead.
