---
title: Tejas Kashyap — Profile (single source of truth)
type: profile
updated: 2026-11-11
rule: Every resume, LinkedIn edit, intro, pitch or application is copied FROM this page. Change facts here first, then propagate.
---

# Tejas Kashyap — Profile

> **Single source of truth.** Evidence behind each line: [[MASTER-MATRIX]] and the dossiers.
> Confidential employer detail: `private/lenskart-internal.md` (git-ignored, never public).

## Identity

| | |
|---|---|
| Current role | **AI Engineer – Research & Development, Lenskart** (full-time, since 26 Oct 2026) |
| HR designation (background checks only) | AI & ML Engineer, Data Intelligence & AI, Lenskart Solutions Ltd |
| Based in | New Delhi (Lenskart, Aerocity) |
| Education | B.Tech CSE, Bennett University (2022–2026), CGPA 7.92 |
| Email | tejas06012005@gmail.com |
| LinkedIn | linkedin.com/in/tejas-kashyap-1450a2252 |
| Headline | AI Engineer, R&D @ Lenskart |

## Experience (newest first)

1. **Lenskart — AI Engineer, R&D** (Oct 2026 – present, full-time) → [[lenskart]]
   - Owns a multilingual (EN/HI/Hinglish) voice-to-voice conversational agent for noisy
     retail. Taking it from POC to a production MVP on the cloud.
   - Designed the real-time turn-taking engine (VAD, adaptive end-of-turn, barge-in, echo
     rejection) and the LLM orchestration (state machine, live-context grounding,
     flag → tool protocol).
   - Designed the SLM fine-tuning pipeline (Unsloth + LoRA). Leads an intern on in-house
     STT/TTS/SLM training.
2. **Lenskart — AI Intern** (Jul – Oct 2026)
   - On-device STT/TTS/SLM feasibility study; vendor benchmark for Indian languages;
     built the voice-agent POC.
3. **Blu Parrot Ventures — AI Engineer Intern** (Feb – Jul 2026, Gurugram) → [[bluparrot]]
   - LangGraph agents, RAG systems, multilingual Hindi/Hinglish assistants.
   - Satellite farm-advisory platform; defence-tender extraction with Gemini.
4. **Bennett Undergraduate Research Society — Core member, PR & outreach** (Oct 2022 – May 2023)

## Research

- *Temple Waste Management System Using YOLOv5 for Real-Time Segregation and
  Sustainability Enhancement*: ICSRF 2025 (Amrita Vishwa Vidyapeetham), SSRN, Google Scholar.
  Built and annotated their own dataset because none existed.

## Personal projects (claimable; see dossiers)

- [[smart-agri]]: 10 ONNX plant-disease models served from a Raspberry Pi 5; 8-CNN-family
  edge benchmark (MobileNetV3-Small: 8 ms).
- [[federated-learning]]: Flower, with FedProx implemented by hand; 99% on skewed non-IID
  data, matching centralized training.
- [[ekantik]]: source-grounded Hindi RAG over 1,004 discourse transcripts (ChromaDB + LaBSE).
- [[job-doot]]: multi-agent job-hunting pipeline (scorer, critic/improver resume loop, auto-apply).
- [[lens]]: 1-day Indic medical-video pipeline (Sarvam ASR + diarization → Gemini classification).
- Built a drone from scratch (flight dynamics, embedded systems).

> ⚠ The public `*.marutsut.me` links are DEAD (domain expired 2026-11-03). Don't put them
> on a resume or LinkedIn until there's a new host.

## Positioning

**Theme:** *"I train and engineer models, I don't just wrap APIs."* Going under the hood
since college (implemented VGG / ResNet / DenseNet / Inception / EfficientNet from scratch).
Now doing speech and language R&D.

**Core strengths (in order):**
- conversational / voice AI;
- Indic multilingual speech and LLMs;
- LLM orchestration and grounding (hallucination control);
- applied DL and edge deployment;
- RAG;
- spec-first engineering.

**Stack:** Python, C++, PyTorch / TensorFlow / Keras, Unsloth + LoRA (pipeline design),
Silero VAD, Whisper, Sarvam, Gemini, Groq, LangChain / LangGraph, ChromaDB / Pinecone / FAISS,
FastAPI, Docker, Linux, Raspberry Pi, AWS (in progress), AppScript.

## Pitches

**10 seconds**
> I'm Tejas, an AI Engineer in Lenskart's R&D team. I build Hindi-English voice agents that
> work in noisy stores, and I'm training our own small language and speech models.

**30 seconds**
> I'm an AI Engineer in Lenskart's R&D team. I own a voice-to-voice conversational agent in
> English, Hindi and Hinglish that has to work in a loud retail store. I started with a
> feasibility study on running speech-to-text, text-to-speech and the language model fully
> on-device. I showed that isn't viable yet for Hindi, then built the proof of concept and
> I'm now taking it to production on the cloud. In parallel I lead an intern on training our
> own small language and speech models. Before Lenskart I built LLM agents and RAG systems
> at Blu Parrot, and I've published research on real-time object detection.

**2 minutes** = the 30-second version plus one deep story. Pick by audience:
- *Engineers:* turn-taking under noise. Adaptive end-of-utterance, barge-in that ignores
  the agent's own voice, and the loudness gate that stops STT hallucinating.
- *Product/business:* the on-device → cloud decision. Secrets server-side, ship updates once
  instead of to every device, a trade-off on latency.
- *Research:* FedProx by hand on non-IID data, or the 8-CNN edge benchmark.

**Never say publicly:** product or codename, exact use case, device or vendor, rollout
plans, internal numbers, leadership dynamics. Never claim models are trained yet.

## Job-search preferences (as of 2026-11-11)

- **Status: actively looking**, while employed full-time at Lenskart.
- **Constraints:**
  - 30-day notice (probation period: 180 days from 26 Oct 2026);
  - 2-year non-compete (Lenskart competitors);
  - NDA on R&D work.
- **Target roles:** AI / ML Engineer and R&D roles: model training & fine-tuning, speech
  (STT/TTS), conversational/voice AI, LLM/SLM.
- **Cities:** India: remote, Gurgaon, Delhi, Noida, Bangalore. Open to relocating for the right role (matches job-doot `location_prefs`).
- **Pay floor:** **12 LPA** (current CTC is in `private/`; never put it on a resume or in an application unless a form explicitly requires it).

## Change log

- 2026-11-11: created. Added the Lenskart full-time role (from HR record + Tejas brief +
  Excalidraw blueprint). Intern → FTE. Status: actively looking.
- 2026-11-11: pay floor 12 LPA; cities confirmed. Agent code was written with AI help, so claim design and ownership. `backend/master_resume.tex` updated (Lenskart role, speech skills, dead marutsut links removed).
