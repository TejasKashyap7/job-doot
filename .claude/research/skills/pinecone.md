---
title: Pinecone
type: skill
verdict: moderate
---
## Evidence
- [[bluparrot]] — Bajaj insurance chatbot: Pinecone serverless index `bajaj-vector-search-index`, 3072-dim `gemini-embedding-001` embeddings, batch upsert, k=10 retrieval with source attribution [verified-in-code: `Bajaj/server.py`, `embed_embeddings.py` scripts].

## Resume verdict
Yes for LOCKED_SKILL_SET (under Vector DBs) and resume — one real, code-verified production-style project. Phrase as "Pinecone serverless vector search (3072-dim Gemini embeddings, batch upsert, grounded answers with source citations)".

## Interview readiness
Can discuss serverless index setup, embedding dimensionality choices, and retrieval-grounded prompting. Single-project depth — don't claim multi-index ops, scaling, or hybrid-search experience.
