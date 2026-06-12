---
title: Gemini
type: skill
verdict: strong
---
## Evidence
- [[lens]] — Gemini 2.5 Flash twice per pipeline: role assignment from conversational patterns + JSON-mode classification with Pydantic validation and a verbatim hallucination filter; single-prompt over 1M-token context (no chunking) [verified-in-code].
- [[bluparrot]] — DGQA: structured extraction over 450+ page defense-tender PDFs via `.with_structured_output()`, temp 0, 3-retry [verified-in-code]; Bajaj `gemini-embedding-001` (3072-dim); Tanzania RAG LLM provider; BCL agent LLM.

## Resume verdict
Yes — LOCKED_SKILL_SET and resume. Strongest phrasing: "Gemini structured extraction over 450+ page documents" and "JSON-mode classification with schema validation and hallucination filtering".

## Interview readiness
Can discuss cost engineering (written ₹0.01 vs ₹0.40/video model vs Claude/GPT-4o), long-context vs chunking trade-offs, and layered hallucination control. Caveat: DGQA's LLM is Gemini, not Groq — keep the attribution straight.
