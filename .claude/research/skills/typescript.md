---
title: TypeScript
type: skill
verdict: strong
---
## Evidence
- [[lens]] — TypeScript 5.5.3 in strict mode (noUnusedLocals/Parameters) across the whole frontend; exported interfaces (`ResponseEntry`, `TranscriptEntry`) exactly mirroring the backend Pydantic schemas [verified-in-code: `ui/tsconfig.json:14-17`].

## Resume verdict
Yes — list as "React + TypeScript". Strict-mode usage with backend-mirrored types is honest evidence of working proficiency.

## Interview readiness
Can discuss strict-mode discipline and keeping frontend types in lockstep with API schemas. Caveat: one project's worth of depth — don't claim advanced type-system work (generics-heavy libraries, conditional types).
