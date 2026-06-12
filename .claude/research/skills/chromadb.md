---
title: ChromaDB
type: skill
verdict: strong
---
## Evidence
- [[ekantik]] — 684 MB persistent collection (~40k LaBSE vectors, 1,004 transcripts) operated live on a Raspberry Pi; vector-level idempotency via `video_already_ingested()` dedup on `video_id` [verified-on-disk + live].
- [[bluparrot]] — Tanzania RAG knowledge store with 9-field metadata contract and `is_active=true` filtering behind an abstract `VectorStore`; nimish HS-code retrieval (1,156 chunks); Smart Query Assistant YouTube store.

## Resume verdict
Yes — LOCKED_SKILL_SET and resume (under "Vector DBs"). Strongest claim: operating a 684 MB persistent store on edge hardware with idempotent ingestion.

## Interview readiness
Can discuss persistence, metadata filtering, dedup strategy, and the documented ChromaDB→Pinecone migration path (abstract store interface). No caveats beyond "1,300+ discovered / 1,004 ingested" phrasing in ekantik.
