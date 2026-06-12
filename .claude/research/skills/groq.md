---
title: Groq
type: skill
verdict: strong
---
## Evidence
- [[job-doot]] — all 4 agents (scorer/critic/improver/email-classifier) on `llama-3.3-70b-versatile`; free-tier budget engineering (per-agent temps/token caps, 4→60s exponential backoff, 2–3s inter-call delays). Verified in `backend/services/groq_client.py` + `agents/`.
- [[ekantik]] — production LLM (`openai/gpt-oss-120b` on Groq, temp 0.2) behind the live ekantik.marutsut.me RAG endpoint; refusal path skips the Groq call entirely when retrieval is empty.
- [[bluparrot]] — Smart Query Assistant routing/answer LLM (`llama-3.3-70b-versatile`); nimish HS-code chatbot (dual model: 70b + 8b-instant); Agri Engine 4 pest-remedy prompts.

## Resume verdict
Yes — LOCKED_SKILL_SET and resume. Phrase as "Groq-hosted Llama-family inference for production agents/RAG (rate-limit-aware retry, structured-output prompting)". Don't pin Agri model versions (not pinned in code).

## Interview readiness
Can discuss free-tier unit economics (30 req/min, 14k TPM), backoff design, JSON-mode vs delimiter outputs, and why Groq over OpenAI for cost/latency. Caveat: ekantik's model is an OSS model hosted on Groq, NOT an OpenAI product — phrase carefully.
