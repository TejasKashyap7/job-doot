# Scoring — Approach

## Status
BUILT

## What it does
Runs each newly ingested job through Groq (Llama 3.3 70B) to produce a relevance
score and structured metadata. This is the first filter. Jobs scoring ≥6 are shown
as actionable on the dashboard; only jobs scoring **≥9 are auto-tailored** (cost
control — see `resume-tailoring/approach.md`). The rubric is tuned to Tejas's actual
target: **core-AI / R&D roles**, not applied/consulting/wrapper roles.

## Flow
```
Job row in DB with status='scraped'
        ↓
score_job(db, job)  [agents/scorer.py]
        ↓
Groq: SCORER_SYSTEM prompt + job title/company/location/salary/JD
        ↓
JSON response: { score, top_matches, top_gaps, domain_flag }
        ↓
Persist to Job row:
    job.score, job.top_matches, job.top_gaps, job.domain_flag
        ↓
Status transitions:
    score == 0   → 'rejected'
    score < 6    → 'filtered_out'
    score >= 6   → 'scored'   ← shown on dashboard as actionable
```
Only `scored` jobs with **score ≥ 9** are auto-tailored (the expensive step). Jobs
scoring 6–8 stay `scored` and visible; a CV can still be made for them on demand via
`POST /admin/tailor/{job_id}`. See the tailoring cost gate below and in
`resume-tailoring/approach.md`.

## Scoring rubric (locked in prompts.py)
- 9-10: Strong match, most JD requirements directly covered
- 7-8: Good match, minor gaps learnable quickly
- 5-6: Partial match, significant gaps but correct domain
- 3-4: Weak match, domain adjacent
- 1-2: Poor match
- 0: Out of scope entirely (pure SWE, frontend, data analyst, Android, DevOps without ML)

## Role-fit targeting (2026-07-06) — core-AI / R&D, NOT applied/consulting/wrapper

Tejas is a **core AI / R&D** engineer. Skill-overlap alone is not enough — the *type*
of role matters, and the old rubric scored applied/consulting roles too high (Infosys
"GenAI + Cloud + ServiceNow" → 7; Accenture/Capco applied → 8–9). The rubric (in
`agents/prompts.py`) now layers role-type on top of skill match:

- **REWARD (bias toward 8–10 when skills match):** research / R&D — Research Engineer,
  Research Scientist, Applied Scientist, ML/DL Research, model **training / fine-tuning**,
  foundation-model / LLM research, **agentic / agent-building** roles, "Member of
  Technical Staff" at AI labs/product companies, genuine R&D posts.
- **PENALIZE (cap low, ≤5–6 even if the skill words match):** "applied AI" at
  consulting/services firms (Accenture, Capco, Infosys, TCS, Wipro, Cognizant, Deloitte);
  GenAI-**wrapper** / prompt-plumbing-only; full-stack-with-AI; cloud/backend-with-GenAI-
  sprinkled (AWS/Azure/ServiceNow integration); data-analyst-labelled-AI.
- **0 (out of scope):** unchanged — pure SWE/frontend/data-analyst/Android/DevOps-without-ML.

The search **keywords** (in `services/scraper.py`) are also widened toward research/R&D
titles so those roles enter the funnel; the rubric above then filters applied/consulting
back down. `top_gaps`/`top_matches` should state the real reason (incl. role-type) so
scoring is legible, not vague.

## Key guard
`LOCKED_SKILL_SET` in `agents/prompts.py` is the single source of truth for what
skills the candidate has. Scorer uses it to evaluate matches/gaps. Same set is
used by the improver — ensures consistent profile across both agents.

## Rate limiting
3s delay between calls (`SCORER_DELAY_SEC = 3`) to respect Groq TPM limits.

## Trigger points
- Automatic: `scheduler.py` → `score_pending()` runs immediately after each CSV ingest
- Manual: `POST /admin/score-pending` or `POST /admin/score-one/{job_id}` (dashboard buttons)

## API cost
Groq free tier. Each score call uses ~512 tokens output + JD input (~1500 tokens).
Typical daily batch of 20 jobs ≈ 40K tokens — well within free limits.
