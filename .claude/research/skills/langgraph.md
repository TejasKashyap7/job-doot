---
title: LangGraph
type: skill
verdict: strong
---
## Evidence
- [[bluparrot]] — Smart Query Assistant: full StateGraph (`thread_check → memory → [youtube ∥ wiki] → merge → decision → answer → save`) with strict-JSON LLM routing and per-thread FAISS memory [verified-in-code]; sparqnow video-QA also LangGraph; BCL SQL agent uses a LangGraph fallback graph with Redis checkpointing (docs-heavy — see honesty flag).

## Resume verdict
Yes — LOCKED_SKILL_SET and resume, anchored to the Smart Query Assistant (code-verified). For BCL, say "architected/documented" rather than implying sole code ownership — the directory holds docs, not running code.

## Interview readiness
Can discuss StateGraph design, parallel retrieval nodes, LLM source-routing, and checkpointer-based memory. Caveat: BCL code lives in a company repo not on this machine — don't claim line-level detail there.
