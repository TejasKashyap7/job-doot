---
title: Vapi (Voice Agents)
type: skill
verdict: moderate
---
## Evidence
- [[bluparrot]] — "Shambhu" Hinglish outbound PG-rental lead-qualification agent: 8-step conversation flow, 15-field structured call output, 3 registered tools (save_lead_data, schedule_visit, check_availability), retry/DND/time-gating ops policies (F01–F30). **Spec-only on disk** (`personal-projects/vapi`: PROJECT_SPEC.md + FEATURES.md); the assistant itself was configured in the Vapi cloud dashboard.

## Resume verdict
Moderate at best (Tejas's own ruling). OK to mention as "spec'd and configured a Hinglish voice-calling agent (Vapi + n8n + Google Sheets POC design)" — never as a built/shipped system. Probably not LOCKED_SKILL_SET.

## Interview readiness
Can discuss conversation design, structured end-of-call extraction, and ops policies in depth — it's a well-specified design. Caveat: no code on disk, no n8n workflow exports; if asked "is it live?", the honest answer is POC/spec + dashboard config.
