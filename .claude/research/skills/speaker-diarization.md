---
title: Speaker Diarization
type: skill
verdict: strong
---
## Evidence
- [[lens]] — Sarvam Saaras v3 batch diarization integrated end-to-end; verified by a native speaker on Punjabi (100%) / Haryanvi / Rajasthani overlapping-speech clips; designed resilience: if diarization returns empty, the transcript collapses to one pseudo-speaker and Gemini still recovers Doctor/Patient roles from conversational structure (who asks vs who answers) [verified-in-code: `pipeline.py:209-217`, role prompt :223-244].

## Resume verdict
Yes as part of the Lens pipeline bullet — phrase as "speaker-diarized multilingual ASR with role recovery", making clear it is API integration + downstream design, not building a diarization model.

## Interview readiness
Strong on the system design: anonymous speaker IDs → role mapping by dialogue pattern, failure fallback, why batch mode (only diarization-capable Sarvam mode). Caveat: no behavior defined if Gemini can't determine roles (flaws.md #5); didn't train/tune the diarizer itself.
