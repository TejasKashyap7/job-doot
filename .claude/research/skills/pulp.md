---
title: PuLP (Linear Programming)
type: skill
verdict: weak
---
## Evidence
- [[bluparrot]] — PuLP ≥2.7 appears in Agri requirements, but the working fertilizer-optimizer solver is **scipy `linprog` (HiGHS)** — PuLP's CBC backend fails on macOS arm64 [verified: `fertilizer_engine/optimizer.py` + dossier interview-trap note].

## Resume verdict
Do NOT claim PuLP as used — it's on the do-not-claim list. The honest, stronger claim is "least-cost fertilizer optimization as a linear program (scipy linprog/HiGHS) over 9 fertilizer compositions with agronomic constraints".

## Interview readiness
The LP formulation itself (objective, nutrient-coverage constraints, per-fertilizer bounds, hard nutrient caps) is fully defensible — just attribute it to scipy. "Did you use PuLP?" is a flagged trap question: answer that CBC was broken on arm64 and scipy HiGHS solves it.
