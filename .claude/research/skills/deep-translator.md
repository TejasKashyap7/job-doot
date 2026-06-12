---
title: deep-translator (GoogleTranslator)
type: skill
verdict: weak
---
## Evidence
- [[ekantik]] — langdetect + GoogleTranslator en→hi query normalization in front of the retriever [verified-in-code: `ekantiks_api.py:136-163`].
- [[bluparrot]] — Smart Query Assistant: Hindi→English transcript translation in 2000-char segments post-retrieval.

## Resume verdict
Not a skill — a utility library. The resume-worthy idea it serves is the cross-lingual pipeline design (see [[labse]]); mention translation normalization inside those bullets, never as a standalone claim.

## Interview readiness
Can explain where translation sits relative to retrieval (after, in Smart Query; before, as belt-and-braces in ekantik) and why. Caveat: silent langdetect failures noted in the ekantik dossier.
