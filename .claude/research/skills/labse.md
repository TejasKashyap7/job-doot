---
title: LaBSE (Multilingual Embeddings)
type: skill
verdict: strong
---
## Evidence
- [[ekantik]] — 768-dim LaBSE embeddings over ~40k Hindi chunks; English queries retrieve Hindi content in one cross-lingual vector space, live at ekantik.marutsut.me [verified-in-code + live].
- [[bluparrot]] — Smart Query Assistant: the documented "cross-lingual trick" — English query retrieves Hindi YouTube-transcript chunks directly because LaBSE (109 languages) maps both into one space; translation happens only after retrieval [verified-in-code].

## Resume verdict
Yes — LOCKED_SKILL_SET and resume. This is a genuine differentiator: "cross-lingual retrieval with LaBSE — English queries over Hindi corpora without query-time translation" appears in two independent projects.

## Interview readiness
Can explain why a single multilingual embedding space beats translate-then-embed, and the belt-and-braces langdetect+translation layer added on top in ekantik. No caveats.
