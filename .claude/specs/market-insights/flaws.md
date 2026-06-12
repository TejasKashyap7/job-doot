# Market Insights — Flaws

---

## FLAW-1: Charts are meaningless until enough data accumulates
**Status: OPEN — known limitation, not a bug, just timing**

**The problem:**
After day 1 of scraping you have maybe 50 jobs. A bar chart of "top skills in demand"
from 50 jobs is statistically useless and could be misleading. You need at least 2–3
weeks of data (roughly 700–1500 jobs) before trends are meaningful.

**Example:**
On day 3, PyTorch appears in 8 job listings and TensorFlow in 2. You conclude the
market has moved to PyTorch. But that's noise — those 10 jobs are from 2 companies
that happen to prefer PyTorch. With 30 days of data, the real ratio becomes clear.

**Options:**
- **Option A — Hide the insights page entirely until a minimum job count is reached.**
  Add a check: if `SELECT COUNT(*) FROM jobs` < 200, show a placeholder
  "Not enough data yet — come back in ~2 weeks" instead of charts.
- **Option B — Show charts but add a data quality banner** at the top: "Based on
  X jobs scraped over Y days — trends become reliable after 500+ jobs."
- **Option C — Show charts from day 1 and let the user interpret.** Add a small
  note in the UI about sample size. User is aware of the limitation.

---

## FLAW-3: No decision on how far back the insights data should go — and what that costs
**Status: OPEN — decide before building the insights page**

**The problem:**
We have never defined the retention window for insights. Should the charts show the
last 3 months? Last year? Everything since day one forever? This matters for two
reasons: (1) old data actively misleads you — skills in demand 2 years ago are not
the same as today, and (2) keeping everything forever means the DB grows unbounded
and the aggregation queries get slower as months pass.

**The numbers — what actually gets stored:**

Per day of running:
- ~70 jobs scraped (after dedup)
- ~25 of those tailored (scored ≥6, ~35%)
- ~20 emails processed (non-NEUTRAL)

| What | Size per row | Per day | Per month | Per year |
|------|-------------|---------|-----------|----------|
| jobs table (raw_description is ~4KB) | ~5KB | 350KB | ~10MB | ~120MB |
| resumes table (latex_content ~20KB) | ~22KB | 550KB | ~16MB | ~195MB |
| PDF files on disk | ~120KB | 3MB | ~90MB | ~1.1GB |
| email_log | ~1.5KB | 30KB | ~0.9MB | ~11MB |
| **Total DB** | | ~930KB | **~27MB** | **~326MB** |
| **Total incl. PDFs** | | ~3.9MB | **~117MB** | **~1.4GB** |

So after **1 year**: DB is ~326MB, PDFs on disk are ~1.1GB, total ~1.4GB.
After **2 years**: ~2.8GB. After **5 years**: ~7GB.

A 64GB SD card won't fill up. But SD cards on Pi degrade from write cycles — the
WAL checkpointing writes continuously. An SSD via USB or NVMe HAT eliminates this.
For the insights page specifically: running `json_each()` over 25,000 rows (1 year)
is instant in SQLite. Over 100,000 rows (4 years) starts to feel it without indexes.

**Why old insights data hurts you specifically:**
The AI job market changes fast. Skills that were hot in 2024 (basic ChatGPT integration)
are table stakes or irrelevant by 2026. Showing a 3-year trend chart will make
older skills look more in-demand than they are because they have more months of data
behind them. A rolling 12-month window gives you the real current picture.

**Options:**
- **Option A — 12-month rolling window for insights, keep everything in DB.**
  The insights queries always filter `WHERE date_scraped >= date('now', '-12 months')`.
  Full job history stays in DB for your personal records but insights only show
  the last year. No data is ever deleted. Simple, no cleanup logic needed.
  DB at 5 years: ~1.6GB — perfectly fine for SQLite.

- **Option B — 12-month rolling window for insights + purge old data.**
  Keep insights window at 12 months AND run a monthly cleanup job that deletes
  job rows older than 12 months (except `status='applied'` — keep those forever
  as your application history). Also deletes old PDFs from disk. DB stays small
  (~326MB max), disk stays clean. Requires building the cleanup job (see storage-management spec).

- **Option C — Configurable window via env var.**
  `INSIGHTS_WINDOW_DAYS=365` in `.env`. Default 365. User can change it.
  Gives flexibility without hardcoding. Combine with Option A or B for the underlying
  retention strategy.

---

## FLAW-2: Skill extraction relies on scorer's top_matches/top_gaps which are summaries, not raw keywords
**Status: OPEN — informational, affects chart granularity**

**The problem:**
The scorer agent writes `top_matches` and `top_gaps` as summarised phrases, not raw
JD keywords. So one JD might get `top_matches: ["RAG systems", "vector databases"]`
while another gets `["retrieval augmented generation", "Pinecone"]` — referring to
the same skill. The aggregation query will count these as different skills, splitting
the frequency count and under-representing the real demand.

**Example:**
"LLM fine-tuning" appears 12 times in top_matches. "Fine-tuning large models" appears
8 times. "PEFT/LoRA" appears 5 times. All mean the same thing. Your chart shows 3 bars
instead of 1 bar at 25. You think fine-tuning is less popular than it is.

**Options:**
- **Option A — Accept it for now.** The charts are directionally correct even if not
  perfectly deduplicated. Skill grouping is an optimisation for later.
- **Option B — Add a skill normalisation map** (a small dict like
  `{"fine-tuning large models": "LLM fine-tuning", "PEFT": "LLM fine-tuning"}`)
  applied at query time to merge synonyms before counting.
- **Option C — Change the scorer prompt** to output skills from a locked vocabulary
  list (same as `LOCKED_SKILL_SET` taxonomy) so aggregation is clean from day 1.
  Bigger change but produces the cleanest data.
