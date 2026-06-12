---
title: FAISS
type: skill
verdict: moderate
---
## Evidence
- [[bluparrot]] — Smart Query Assistant per-thread conversation-memory store (all-MiniLM-L6-v2 embeddings) inside the LangGraph pipeline [verified-in-code].
- [[ekantik]] — earlier `FAISS.ipynb` practice plus a Ramayana FAISS index (`ramayana_faiss`) in the LangChain learning workspace.

## Resume verdict
Yes for LOCKED_SKILL_SET under "Vector DBs" (already claimed there); fine as one item in a vector-DB list. Don't make FAISS a headline skill on its own — usage is memory-store + learning experiments, not large-scale ANN tuning.

## Interview readiness
Can explain why FAISS for ephemeral per-thread memory vs ChromaDB for the persistent corpus. Don't claim index-type expertise (IVF/HNSW tuning) — never exercised in these projects.
