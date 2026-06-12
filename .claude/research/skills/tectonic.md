---
title: Tectonic (LaTeX → PDF)
type: skill
verdict: moderate
---
## Evidence
- [[job-doot]] — automated LaTeX→PDF resume compilation: tectonic 0.15.0 static Rust binary (fetched in Dockerfile, musl builds for x86_64/aarch64), sandboxed temp-dir compile, 120s timeout, log-excerpt error capture; compile failure routes the job to `review_needed` [verified-in-code: `backend/services/latex_compiler.py:44-50`].

## Resume verdict
Mention inside the job-doot pipeline bullet ("LLM-emitted LaTeX compiled with tectonic"); not a standalone skill. The decision rationale (stateless single binary vs TeX Live on a Pi) is the claimable part.

## Interview readiness
Can explain why tectonic over pdflatex/reportlab and the delimiter-protocol LLM output that feeds it. Narrow tool — keep claims scoped to this pipeline.
