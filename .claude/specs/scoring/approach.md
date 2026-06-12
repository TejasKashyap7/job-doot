# Scoring — Approach

## Status
BUILT

## What it does
Runs each newly ingested job through Groq (Llama 3.3 70B) to produce a relevance
score and structured metadata. This is the first filter — only jobs scoring ≥6
proceed to the expensive tailoring loop.

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
    score >= 6   → 'scored'   ← proceeds to tailoring
```

## Scoring rubric (locked in prompts.py)
- 9-10: Strong match, most JD requirements directly covered
- 7-8: Good match, minor gaps learnable quickly
- 5-6: Partial match, significant gaps but correct domain
- 3-4: Weak match, domain adjacent
- 1-2: Poor match
- 0: Out of scope entirely (pure SWE, frontend, data analyst, Android, DevOps without ML)

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
