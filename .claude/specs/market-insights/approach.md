# Market Insights — Approach

## Status
NOT STARTED — data collection already happening passively via scorer,
build this page once enough data (2–3 weeks of daily scrapes) has accumulated

## What we're building
A `/insights` page on the dashboard that aggregates the job data we're already
collecting and visualises what the market is actually demanding. Zero extra API calls,
zero extra data collection — everything comes from the `jobs` table that the scorer
already populates.

## What data we already have (per job)
- `top_matches` — JSON list of skills from the JD that match the candidate (from scorer)
- `top_gaps` — JSON list of skills in the JD that the candidate lacks (from scorer)
- `domain_flag` — in-scope / out-of-scope / borderline
- `title`, `company`, `location`, `salary`
- `score`, `date_scraped`
- `remote_flag`

## Charts and what they answer

### 1. Top Skills in Demand (bar chart)
Flatten all `top_matches` + `top_gaps` arrays across all jobs, count frequency of
each skill term. Shows what the market wants most, regardless of whether we have it.

> "LLM fine-tuning is in 43 JDs this month. RAG is in 31. Computer Vision still
> at 28. PyTorch mentioned more than TensorFlow now."

### 2. Skill Gap Frequency (bar chart, separate)
Only from `top_gaps`. Shows what skills are demanded most that we DON'T have.
This is the most actionable chart — it tells you what to learn next.

> "MLOps skills appear in 18 JDs we can't fully match. Kubernetes in 12."

### 3. Skills Over Time (line chart, weekly buckets)
Same skill frequency but grouped by `date_scraped` week. Shows what's rising vs
declining in demand over the weeks the pipeline has been running.

> "GenAI roles spiked last week. CV roles flat. NLP trending down."

### 4. Domain Breakdown (donut chart)
Count of `domain_flag` values: in-scope / borderline / out-of-scope.
Tells you what fraction of jobs being posted in the market are actually relevant.

### 5. Top Hiring Companies (horizontal bar)
Count of jobs per company name. Which companies are actively hiring for AI roles.

### 6. Location Distribution (bar)
Jobs by location string. Remote vs Gurgaon vs Noida vs Pune etc.

### 7. Score Distribution (histogram)
Distribution of scores 0–10 across all scraped jobs. Useful sanity check —
if everything is scoring 3–4, the scorer prompt may need tuning.

## Tech approach
- New route: `GET /insights` in `main.py`
- New template: `templates/insights.html`
- All aggregation done in Python via SQLAlchemy/raw SQL queries — no new DB tables
- Charts rendered client-side via **Chart.js** (CDN, no npm, fits the existing
  plain HTML approach)
- Data passed from route to template as JSON context vars

## Key SQL patterns needed
```sql
-- skill frequency: unnest top_matches JSON arrays across all jobs
SELECT json_each.value AS skill, COUNT(*) AS freq
FROM jobs, json_each(jobs.top_matches)
GROUP BY skill ORDER BY freq DESC LIMIT 20;

-- weekly skill trend: same but grouped by strftime('%Y-W%W', date_scraped)
-- domain breakdown: COUNT(*) GROUP BY domain_flag
-- company frequency: COUNT(*) GROUP BY company ORDER BY COUNT DESC LIMIT 15
```

## Time filter
Add a "last 30 days / 90 days / 180 days" toggle. Default: 180 days (decided in
Flaw 8 — balances recency with enough data for reliable trends).

## Access
Protected by `require_login` same as the rest of the dashboard.
Add "Insights" link to the nav in `base.html`.

---

## Beyond Frequency: Market Intelligence

Raw skill frequency counts are misleading. "Python" appearing in 10,000 listings
tells you nothing useful if most of those listings pay ₹4 LPA. The insights page
should answer the question: **what skills, roles, and companies actually translate
to good outcomes** — not just what appears most often.

### Additional charts and analyses

#### 8. Skill × Salary Correlation (ranked bar)
For each skill that appears in jobs with a parseable salary, compute the median
salary of those jobs. Rank skills by median pay, not post count.

> "LangGraph roles: median ₹28 LPA. FastAPI roles: median ₹14 LPA. Django: ₹9 LPA.
> Python (generic): ₹7 LPA."

This is the single most actionable chart — it tells you which skills to prioritise
learning for salary growth, not just for employability.

#### 9. Company Profiles (expandable table)
For each company that appears 2+ times, aggregate:
- Roles they hire for
- Skills they consistently require
- Salary range (min / median / max from parseable listings)
- Locations and remote policy
- Experience level they target (fresher / 2–3yr / 5+yr, inferred from JD text)
- Score distribution of their listings (are they high-bar or low-bar?)

> "Sarvam AI: 4 listings, all GenAI Engineer, requires LLM fine-tuning + Hindi TTS,
> salaries ₹20–35 LPA, remote-friendly, targets 2–4yr exp."

#### 10. Experience Level Demand by Role (stacked bar)
Parse JD text for experience signals ("0-2 years", "fresher", "3+ years", "senior",
"lead") and group by role title family (MLE, GenAI Eng, Data Scientist, MLOps).
Shows where the market actually wants you now vs. where to aim in 2 years.

> "GenAI Engineer: 60% want 0–3yr exp. MLOps Engineer: 70% want 5+yr. Good news."

#### 11. Skills That Co-occur With High-Scoring Jobs (correlation table)
Among jobs that scored ≥8, which skills appear most? Different from raw frequency —
filters to jobs that actually match the candidate's profile well. Shows which skills
to double down on for maximum pipeline conversion.

#### 12. Emerging vs Declining Skills (trend lines, 30/90/180 day buckets)
Track skill frequency per time bucket. Flag skills whose frequency has grown >20%
in the last 30 days vs. the prior 30 days (emerging) and those that dropped >20%
(declining). This is the "where is the market going" signal.

> "LangGraph: +40% in 30 days. Spark: -25%. Agents/tool-use: +60%."

## Salary parsing note
Salary data from scraped jobs is messy — "12-18 LPA", "₹25,000/month", "competitive".
Parse what you can (regex for LPA / per month ranges), store as float min/max on Job,
skip unparseable values. Even 40% salary coverage gives meaningful signal for the
pay-correlation charts. Add `salary_min` and `salary_max` Float columns to the Job
model when building this page.
