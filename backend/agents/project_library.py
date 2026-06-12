"""PROJECT_LIBRARY — the single runtime source of truth about Tejas's projects.

Distilled from the verified dossiers in .claude/research/dossiers/ (code-level
evidence). The improver agent SELECTS projects from this library per JD and writes
bullets grounded ONLY in these facts. Every entry carries a DO-NOT-CLAIM list from
the dossier honesty flags — those are hard bans.

Maintenance rule: when Tejas finishes a new project (or a fact changes), add/update
the entry here in the same change that updates the dossier vault. Keep entries
compact — this text is injected into every improver call.
"""

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
