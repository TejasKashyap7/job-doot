---
title: Lenskart (employer) — public-safe
type: project-dossier
employer: Lenskart Solutions Limited
role: AI Engineer – Research & Development (full-time, Oct 2026 – present); AI Intern (Jul – Oct 2026)
location: New Delhi (Aerocity)
tags: [conversational-ai, speech, voice-agent, vad, slm, lora, unsloth, on-device-ml, aws]
verified: 2026-11-11 (Tejas voice brief + own architecture blueprint + HR record)
confidentiality: PUBLIC-SAFE tier only. Internal detail lives in private/lenskart-internal.md (git-ignored, Mac + Pi only).
---

# Lenskart — Dossier (public-safe)

> **Rule for this file:** everything here may appear on a resume, LinkedIn, or an external
> pitch. Under NDA (R&D, 2-year non-compete), so public text stays at *domain level*:
> - no product names, codenames or exact use case;
> - no device or vendor names, no rollout plans;
> - no internal numbers.
>
> Interview-depth details are in the git-ignored `private/lenskart-internal.md`.

## TL;DR

AI Engineer in Lenskart's **R&D team**. He converted from AI Intern (Jul–Oct 2026) to
full-time (26 Oct 2026). He owns a **multilingual (English / Hindi / Hinglish)
voice-to-voice conversational agent** for a **noisy retail environment**:
- He took it from feasibility study to a working proof of concept.
- He is now taking it to a production-grade MVP on cloud infrastructure.
- In parallel he leads an intern on **training in-house small language models and speech
  models (STT/TTS)**, and he designed the LoRA fine-tuning and data pipeline for it.
- Not live yet: this is an R&D product.

HR designation: "AI & ML Engineer" (department: Data Intelligence & AI). Title used
publicly: **AI Engineer – Research & Development**.

## What he did (public-safe)

### Internship — Jul–Oct 2026
1. **Domain ramp-up:** learned the medical/optometry domain and the existing systems, and
   presented them to the team.
2. **On-device feasibility study:**
   - evaluated running STT, TTS and an SLM *entirely on a mobile device*;
   - surveyed and benchmarked on-device models;
   - concluded that a fully local, multilingual (Hindi) voice agent isn't production-viable
     with today's open models, which drove the decision to go to the cloud.
3. **Provider benchmark:** compared commercial speech/LLM APIs for Indian languages and
   picked the best fit.
4. **Built the end-to-end voice-agent POC.**

### Full-time — Oct 2026 →
5. **Owning POC → MVP → production.** Made the cloud architecture call:
   - secrets stay server-side;
   - central updates instead of shipping to a fleet of devices;
   - accepted a latency trade-off.
6. **Integrating with internal platform APIs** together with the full-stack team.
7. **Leading an intern** on in-house model training.

## Engineering highlights (safe to discuss at technical depth, without product context)

- **Real-time speech front-end for noise:**
  - streaming VAD (Silero, LSTM) on 32 ms frames with overlap;
  - debounced speech-state latch;
  - **adaptive end-of-turn hangover** (waits longer after short utterances);
  - a max-utterance cap;
  - a pre-roll buffer to keep word onsets;
  - a loudness gate that stops STT hallucinating on near-silent clips.
- **Barge-in / interruption handling:** a combined loudness + VAD "assertive speech" signal
  to reject the agent's own TTS leaking into the mic, with dropout tolerance, a minimum
  sustained duration and an arm delay.
- **LLM orchestration:**
  - a finite-state orchestrator with safety keyword escalation to a human;
  - a single-flight queue;
  - layered context (persona / process / live-state snapshot) rendered into natural language;
  - an **inline flag → tool-call protocol** (flags stripped before speech);
  - self-correction (empty / repeated / banned output → regenerate).
- **Grounding the agent in live app state:** knows what the user has *actually heard*
  (fresh vs stale prompt detection) and spots hesitation patterns, which are surfaced to the
  model as soft hints, not facts.
- **Model-training pipeline (designed):**
  - SLM fine-tuning with **Unsloth + LoRA**;
  - data flow: ingest → extract → format → unstructured → structured → human-in-the-loop;
  - a "golden dataset" spec for speech: real noise, diarization, multilingual, regional
    accents, device/mic mismatch, dedup;
  - forced alignment (Whisper) to QA audio–transcript pairs.

## Resume Raw Material (public-safe bullets — pick 3–4)

1. Own an R&D **multilingual (English/Hindi/Hinglish) voice-to-voice conversational agent**
   for a high-noise retail setting, from feasibility study through POC to a production MVP.
2. Ran an **on-device feasibility study** of STT, TTS and SLMs on mobile hardware, and
   benchmarked commercial speech APIs for Indian languages. The findings set the move to a
   cloud architecture.
3. Designed the real-time **turn-taking engine**: streaming VAD, adaptive end-of-utterance
   detection, noise and self-echo rejection, and barge-in, tuned for noisy environments.
4. Designed the LLM orchestration layer: a finite-state controller, layered context from
   live application state, an inline flag-to-tool protocol, safety escalation to a human,
   and self-correction.
5. Designed an **SLM fine-tuning pipeline (Unsloth + LoRA)** with human-in-the-loop data
   curation. Lead an intern on in-house STT/TTS/SLM training.

## Pitch lines

- **One-liner:** "I'm an AI Engineer in Lenskart's R&D team. I build a Hindi-English voice
  agent that has to work in a noisy store, and I'm working on training our own small
  language and speech models so it can run in-house."
- **Strongest story:** the feasibility verdict. He was asked to make it 100% on-device,
  tested everything that fits, proved it isn't viable yet for Hindi speech, and moved the
  design to cloud-first. He then made the call to go server-side so updates ship once
  instead of to every device.

## Honesty flags

- **Do NOT claim yet:**
  - "trained / fine-tuned LLMs, SLMs, STT or TTS models": pipeline designed, training not run;
  - production, users, or impact numbers: not live, 0 users;
  - latency or accuracy figures: none measured or shared.
- **Code authorship (Tejas, 2026-11-11):** the agent code was written *with AI help*.
  Claim *designed / architected / owned / built with AI-assisted development*. Never
  "hand-implemented". Be ready to explain every design decision; that's the defensible part.
- Update this file when: training starts or finishes, pre-prod or production launch, the
  first real numbers come in, or the intern project concludes.

Related: [[lens]] (earlier Lenskart-domain POC), [[sarvam-ai]], [[indic-ai]], [[multi-agent]], [[fastapi]].
