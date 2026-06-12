---
title: MMR Retrieval
type: skill
verdict: weak
---
## Evidence
- [[ekantik]] — MMR retriever configured with k=7 but `lambda_mult=1`, which degenerates MMR to pure relevance ranking — the diversity knob was tried and effectively turned off [verified-in-code: `ekantiks_api.py:103-105`; Honesty Flag #3].

## Resume verdict
Do not claim "MMR-based semantic search for diversity" — the dossier explicitly flags this. Say "semantic retrieval (k=7)" or mention MMR only with the λ=1 caveat. Not a skills-section item.

## Interview readiness
Actually a good honesty story: can explain the MMR trade-off formula and why λ=1 was the right call here (the prompt cites all referenced ekantiks, so redundancy across discourses is acceptable). Just never present it as diversity-tuned retrieval.
