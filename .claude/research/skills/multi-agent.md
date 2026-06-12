---
title: Multi-Agent Systems
type: skill
verdict: strong
---
## Evidence
- [[job-doot]] — critic↔improver tailoring loop with separation of duties (critic never rewrites), max-3-rounds bound, early-exit on no-diff, UNFIXABLE protocol, and human-review fallback status; 4 distinct agents sharing one LOCKED_SKILL_SET anti-hallucination primitive [verified-in-code: `agents/tailor_loop.py`, `agents/prompts.py`].
- [[bluparrot]] — LangGraph multi-node agents: Smart Query Assistant (parallel retrievers + routing decision node), BCL dual-path SQL agent (docs-heavy).

## Resume verdict
Yes — resume and LOCKED_SKILL_SET (as "multi-agent LLM systems"). Strongest phrasing: "bounded critic/improver agent loop with structural anti-hallucination guarantees" — the design is genuinely his.

## Interview readiness
Deep: why bounded loops beat open-ended agent conversations, separation of duties, giving honesty a syntactic home (UNFIXABLE channel), delimiter-vs-JSON output protocols. Caveat: job-doot output quality is formally unverified until M3's human PDF gate — say so if asked about results.
