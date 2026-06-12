---
title: Sarvam AI (Saaras ASR)
type: skill
verdict: strong
---
## Evidence
- [[lens]] — integrated Sarvam Saaras v3 Batch API for ASR + diarization across Hindi/Punjabi/Haryanvi/Rajasthani/Hinglish (`language_code: "unknown"` auto-detect); reverse-engineered two undocumented quirks (`x-ms-blob-type: BlockBlob` Azure upload header; results keyed as `0.json`); 6-step async job flow with 5s polling / 10-min timeout; diarization-failure fallback [verified-in-code: `server/pipeline.py:155-218`]. Punjabi transcription verified 100% by a native speaker (eval doc).

## Resume verdict
Yes — LOCKED_SKILL_SET and resume, under Indic AI. Phrase as "Sarvam AI Saaras v3 batch ASR + speaker diarization integration for multilingual Indic medical-video analysis".

## Interview readiness
Strong debugging story: thin-docs third-party API, presigned Azure Blob uploads, polling design. Caveats: no IndicTrans2/Bulbul TTS anywhere in the code (do NOT claim them); the 100% accuracy figure is native-speaker eyeballing, not a metric harness.
