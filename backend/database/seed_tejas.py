"""One-time seed data for backfilling Tejas as the first `users` row during the
multi-user migration (see db.py::_migrate_to_multi_user). This is a snapshot of
what used to be hardcoded in agents/prompts.py and agents/project_library.py —
after migration, those modules read from the DB per-user instead of these
constants. Not imported anywhere except the migration itself.
"""

CANDIDATE_PROFILE = """\
- B.Tech CSE graduate, Bennett University (2022-2026), CGPA 7.92
- Current AI Engineer Intern, Blu Parrot Ventures, Gurgaon (Feb 2026 - Present) — production systems, real clients
- Published researcher — ICSRF 2025, SSRN, Google Scholar indexed
- Live deployed ML inference server: marutsut.me — 10 ONNX models, Raspberry Pi 5, Docker, FastAPI, Cloudflare Tunnel, 8ms on-device inference (MobileNetV3-Small)
- Production source-grounded Hindi RAG system: 1,000+ video transcripts indexed, live at ekantik.marutsut.me
- Core domain: ML, Deep Learning, Computer Vision, GenAI/LLM systems
- Presents as: working AI Engineer, not a student
- NEVER describe experience as student projects — these are engineering deployments and research work"""

LOCKED_SKILL_SET = """\
Languages: Python (primary), C++, AppScript
LLM & GenAI: Groq (Llama-family models), Google Gemini, LangChain, LangGraph, MCP (Model Context Protocol — built a custom MCP server), multi-agent systems (critic/improver loops), RAG systems, Source-Grounded QA, Hallucination Mitigation (verbatim-evidence checking, constrained generation), prompt engineering
Vector DBs & Embeddings: ChromaDB, Pinecone, FAISS, sentence-transformers (LaBSE cross-lingual, MiniLM), Google Gemini embeddings
Indic & Speech AI: Sarvam AI (Saaras batch ASR), speaker diarization, Hindi/Hinglish production pipelines, cross-lingual retrieval (English queries over Hindi corpora)
ML/DL: TensorFlow, Keras, PyTorch, Scikit-learn, Matplotlib, transfer learning, EfficientNet/MobileNet families, CNN architecture benchmarking, ONNX export + ONNX Runtime edge inference, Federated Learning (Flower — FedAvg, FedProx, non-IID data), Object Detection (YOLOv5)
Geospatial & Domain Data: Sentinel-2 satellite imagery (NDVI/NDWI time-series via Sentinel Hub), weather/soil data integration, agricultural decision systems
Web & APIs: FastAPI (production, async), Pydantic v2
Infra & Deployment: Docker (multi-arch AMD64/ARM64), Raspberry Pi 5 home server (live public ML services), Cloudflare Tunnel, Supabase, Git, Linux shell
Practices: spec-driven development, idempotent data pipelines, published research (ICSRF 2025, SSRN, Google Scholar indexed)"""

PROJECT_LIBRARY = """\
=== PROJECT: Smart Agriculture — Plant Disease Detection (LIVE: https://pifive.marutsut.me/docs) ===
Tech: TensorFlow/Keras, ONNX + ONNX Runtime, FastAPI, Docker (multi-arch AMD64/ARM64), Raspberry Pi 5, Cloudflare Tunnel.
Verified facts:
- Benchmarked 8 CNN families trained from scratch under one pipeline (VGG-16, Inception-v1, ResNet-101, DenseNet-169 k32/k48, EfficientNet-B0, MobileNetV1/V2/V3-Small/V3-Large) on PlantVillage: 20,638 images, 15 classes (pepper/potato/tomato), 224x224, batch 64, Adam.
- Edge-efficiency winner: MobileNetV3-Small — 99.95% accuracy, 1.53M params, 8 ms/image, ~82 MB peak RAM on Pi 5. EfficientNet-B0: 99.95% accuracy, lowest loss (0.0005), 4.01M params (ONNX-counted), 45.4 ms.
- VGG-16 baseline: 78.70%, 165.8M params, 720 ms — MobileNetV3-Small is ~108x smaller, ~90x faster.
- 10 ONNX models deployed live behind ONE FastAPI endpoint (POST /predict/{model_name}); predictions verified live (correct class, confidence ~1.0).
- Int8 quantization finding: 3.5–4x smaller on disk but SLOWER on this ARM ONNX Runtime build (no vectorized int8 kernels) — honest system-limitation result.
- Methodology hardening: seeded stratified 80/10/10 split (leakage fix), multi-seed retraining (42/1337/2024) with mean±std; full-dataset eval 99.67% (MobileNetV3-Small).
- ResNet-101 converged only with Adam; RMSprop/SGD failed at equal budget (optimizer-sensitivity finding).
- IEEE-format paper draft authored (edge deployment comparative study).
DO NOT CLAIM: "4 custom CNN architectures" (none exist); 92.5%/89.8% precision-recall (superseded); "<150ms end-to-end" (8 ms is on-device inference; tunnel round-trip is ~0.6–1.0s).

=== PROJECT: Ekantik Vartalap — Source-Grounded Hindi RAG (LIVE: https://ekantik.marutsut.me) ===
Tech: LangChain, ChromaDB (persistent), LaBSE embeddings (768-dim, cross-lingual), Groq LLM, FastAPI, deployed on Raspberry Pi.
Verified facts:
- Source-grounded QA over discourses of Premanand Ji Maharaj: answers ONLY when an explicit answer exists in transcripts; scripted Hindi refusal otherwise; mandatory source citations (ekantik numbers).
- Retrieval-gated refusal: if retrieval returns nothing, the LLM is never called — zero LLM cost on unanswerable queries.
- Ingestion: 1,347 playlist videos discovered, 1,004 Hindi transcripts ingested; resumable + idempotent (file-level skip + video_id dedup queried against the vector store).
- ~40k chunks, 1200 chars / 250 overlap, Hindi-aware splitting (Devanagari danda '।' as first-class separator); ChromaDB store 684 MB.
- Cross-lingual retrieval: English queries retrieve Hindi chunks in one LaBSE vector space; langdetect + en->hi query normalization on top.
- Constrained generation prompt: 6–10 line Hindi answers, no new facts, temperature 0.2.
- Custom deployment bridge: chunked tar.gz streaming over a Cloudflare-tunneled HTTP endpoint to sync the vector DB to the Pi.
DO NOT CLAIM: timestamps preserved in the vector store (raw transcripts only); "MMR for diversity" (lambda=1 disables diversity); "1,300+ transcripts" (1,004 ingested); Docker (runs native uvicorn on Pi).

=== PROJECT: Lens — Clinical Video Interpreter, Indic Speech AI (LIVE: https://lens.marutsut.me) ===
Tech: Sarvam AI Saaras v3 (batch ASR + speaker diarization), Google Gemini 2.5 Flash, FastAPI (async BackgroundTasks), Python/ffmpeg.
Verified facts:
- End-to-end pipeline: Hindi/Hinglish doctor-patient consultation videos -> ffmpeg 16kHz audio -> Sarvam Saaras v3 Batch ASR with diarization (auto language detect) -> Gemini role assignment (Doctor/Patient/Irrelevant) -> Gemini response classification into structured clinical categories.
- Verbatim-substring hallucination filtering: every LLM-classified patient response must appear verbatim in the transcript or it is rejected.
- Reverse-engineered undocumented Sarvam batch-API behaviors (required x-ms-blob-type: BlockBlob upload header; fixed output naming) — integration quirks not in any docs.
- Diarization-failure fallback: recovers speaker roles from dialogue structure when diarization fails; 'partial' job state for partial-failure recovery; Gemini retries 15s/30s x3.
- Transcription quality verified with native speakers across Hindi, Hinglish, and Punjabi consultations (100% on verified Punjabi test set).
- Cost-engineered: ~Rs.21/day at 100 videos/day design; ~35K tokens per hour of video in a single large-context prompt.
DO NOT CLAIM: IndicTrans2 or Bulbul TTS (absent from codebase — no translation/TTS step); React/TypeScript/frontend stack as personal skills (Claude-implemented); end-to-end medical diagnosis (it classifies responses, does not diagnose).

=== PROJECT: Federated Learning — Privacy-Preserving Plant Disease Training (not deployed) ===
Tech: Flower (flwr 1.30.0), TensorFlow/Keras, EfficientNet-B1 (ImageNet, frozen backbone), ONNX (tf2onnx) verification.
Verified facts:
- Simulated federation: 2 clients (farms) + 1 server on localhost; binary tomato healthy vs early-blight on PlantVillage; 240x240 input; only the 2,562-param head trained (frozen-backbone edge design).
- FedProx implemented BY HAND as a custom @tf.function proximal-loss training step (not the library version), mu=1.0.
- Results: FedProx on skewed 150:50 label-skew non-IID data reached 99.0% — matching the 98.75% centralized baseline; balanced FedAvg run reached 100% (log-recorded); independent ONNX re-evaluation: 98.0%.
- Documented FedAvg failure mode on non-IID data ("bias cancellation") motivating FedProx.
- Debugging story: found a double-normalization bug (manual /255 vs EfficientNet's internal rescaling) that invalidated early experiments; root-caused via centralized ablation.
- Crash-safe engineering: per-epoch client checkpoints + server warm-start; resume broke a false 96% plateau.
- Spec-driven: 12 spec docs including a 433-line flaw ledger gating all code.
DO NOT CLAIM: "beat centralized" (+0.2pp is noise — say "matched"); Dirichlet partitioning (it is explicit label-skew); real distributed deployment (simulated on one machine); multi-crop (binary task).

=== PROJECT: Job-Doot — Autonomous Job-Hunt Pipeline (in development, planned: jobs.marutsut.me) ===
Tech: Groq (llama-3.3-70b-versatile), multi-agent loop, FastAPI, SQLite (WAL), LaTeX->PDF (tectonic), Docker Compose, Telegram Bot, Gmail API.
Verified facts:
- Multi-agent resume tailoring: scorer -> critic -> improver loop with separation of duties; bounded at 3 rounds with human-review fallback (review_needed) instead of infinite loops.
- Anti-hallucination protocol: LOCKED_SKILL_SET constrains every agent; improver must mark JD demands it cannot honestly satisfy as UNFIXABLE rather than fabricate.
- Scrapers: Naukri JSON API (45 keyword x location combos, exponential backoff) + LinkedIn cookie-based drip scraper (randomized 15–45 min intervals, activity simulation); SHA256 source_hash idempotent dedup.
- Pipeline: scrape -> LLM relevance scoring (0–10 rubric) -> tailor -> compile PDF per job; Gmail watcher classifies recruiter email (REAL_RESPONSE/SPAM_TRAP/AUTO_REJECTION/NEUTRAL) -> Telegram alerts.
- Spec-driven build: weighted milestone roadmap, numbered flaw tracker, dossier research vault.
DO NOT CLAIM: production throughput numbers (not yet deployed to the Pi); "fully autonomous applications" (human applies; Phase-2 Easy Apply not built)."""

ROLE_TYPE_PREFS = """\
IN-SCOPE ROLES: AI Engineer, ML Engineer, Deep Learning Engineer, Computer Vision Engineer, GenAI/LLM Engineer, MLOps (light), and — MOST preferred — AI Research / R&D roles.

OUT-OF-SCOPE ROLES (score 0 regardless): pure SWE, frontend, backend web dev, data analyst, Android dev, DevOps without ML.

ROLE-TYPE PREFERENCE (CRITICAL — this candidate targets CORE AI / R&D, not applied/consulting work). Skill overlap alone is NOT enough — weigh the TYPE of role heavily:
- STRONGLY PREFERRED (allow 8-10 when skills also match): research / R&D — Research Engineer, Research Scientist, Applied Scientist, ML/DL Research, model TRAINING / fine-tuning, foundation-model / LLM research, agentic / agent-building roles, "Member of Technical Staff" at AI labs or product companies, genuine R&D posts.
- GENUINE CORE ENGINEERING (7-8): roles that actually build or train models / ML systems, not merely call an API.
- PENALIZE — CAP AT 5-6 even if the skill keywords all match: "applied AI" at consulting/services/IT firms (Accenture, Capco, Infosys, TCS, Wipro, Cognizant, Deloitte); GenAI-WRAPPER / prompt-plumbing-only roles; full-stack-with-AI; cloud/backend roles with GenAI merely "sprinkled" (AWS/Azure/ServiceNow integration, API/backend dev wearing an AI label); data-analyst work labelled as AI. Do NOT reward these highly just because "AI"/"GenAI" appears in the title — they are NOT what the candidate wants.
When you cap a score for role-type, SAY SO as the FIRST entry in top_gaps, e.g. "Role-type: applied AI at a consulting firm, not core R&D — capped."""

LOCATION_PREFS = "India — remote, Gurgaon, Delhi, Noida, Bangalore. Relocation: open for the right role."
SALARY_PREF = "not disclosed"
