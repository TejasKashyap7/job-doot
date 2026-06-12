# Ingest — Approach

## Status
BUILT

## What it does
Accepts job rows (from CSV or webhook JSON), deduplicates them, and inserts new ones
into the `jobs` table with `status='scraped'`. This is the entry point for all job
data into the pipeline.

## Flow
```
CSV file / webhook JSON payload
        ↓
ingest_rows(db, rows)
        ↓
For each row:
    Validate: title and company must be non-empty → skip if missing
    Compute source_hash = SHA256(f"{title}|{company}|{apply_url}")
    Check: is source_hash already in jobs table? → skip (dedup)
    Coerce: remote_flag = "remote" in location.lower()
    Coerce: easy_apply from any truthy string ("1", "true", "yes", etc.)
    Insert Job row with status='scraped'
        ↓
Commit all inserts in one transaction
Return {"inserted": N, "skipped": M}
```

## Deduplication
`source_hash` is the dedup key — computed once at insert time, stored permanently.
Same job posted again tomorrow (same title + company + apply_url) = same hash = skipped.
This is what prevents the daily scraper from re-processing jobs it's already seen.

## Expected CSV column names
```
title         (required)
company       (required)
location
salary
remote_flag   (optional, also inferred from location string)
easy_apply    (optional)
apply_url
description   ← NOTE: stored as raw_description in the DB
```

## Trigger points
- Automatic: `scheduler.py` → `load_csv(db, CSV_PATH)` at 06:00 IST
- Manual: `POST /admin/trigger-scrape` (dashboard button, auth required)
- Webhook: `POST /webhook/jobs` with `{"jobs": [...]}` (no auth — see flaws.md FLAW-3 in dashboard)

## Location → remote flag
`"remote" in location.lower()` — if the location string contains the word "remote",
`remote_flag` is set to True. This is a simple heuristic, not perfect (see flaws.md).
