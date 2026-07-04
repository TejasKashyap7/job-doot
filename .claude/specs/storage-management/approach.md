# Storage Management — Approach

## Status
NOT STARTED — build this before Pi deployment

## The numbers (what actually accumulates)

Per day of pipeline running:
- ~70 jobs scraped, ~25 tailored, ~20 emails classified

| What | Per day | Per month | Per year | Per 2 years |
|------|---------|-----------|----------|-------------|
| jobs table rows | ~70 rows / 350KB | ~10MB | ~120MB | ~240MB |
| resumes table rows | ~25 rows / 550KB | ~16MB | ~195MB | ~390MB |
| PDF files on disk | ~25 files / 3MB | ~90MB | ~1.1GB | ~2.2GB |
| email_log rows | ~20 rows / 30KB | ~0.9MB | ~11MB | ~22MB |
| **Total DB** | ~930KB | **~27MB** | **~326MB** | **~652MB** |
| **Total incl. PDFs** | ~3.9MB | **~117MB** | **~1.4GB** | **~2.8GB** |

**Bottom line:**
- Capacity is a non-problem even at 5 years of running
- Write wear is also no longer a concern: the Pi now runs on an **NVMe SSD** (not an
  SD card), which has far higher write endurance — see flaws.md FLAW-1 (RESOLVED)
- After 1 year: ~1.4GB total. After 2 years: ~2.8GB. Perfectly manageable.

## Retention policy (what to keep vs delete)

| Data | Keep for | Reason |
|------|----------|--------|
| `applied` jobs | Forever | Your application history — never delete |
| Resumes for `applied` jobs | Forever | Reference — what resume got you that interview |
| Non-applied jobs | 90 days | Enough for trend analysis, then stale |
| Resumes for non-applied jobs | 90 days | No value once job is old/irrelevant |
| PDFs for non-applied jobs | 90 days | Biggest disk cost — clean aggressively |
| `email_log` rows | 60 days | Short-lived operational data |
| `filtered_out` / `rejected` jobs | 30 days | Only needed for dedup guard |

## Cleanup job

A weekly APScheduler job (runs every Sunday at 02:00 IST, well outside the
06:00 scrape window) that:

1. Deletes PDF files from disk for jobs older than 90 days with status != 'applied'
2. Deletes Resume rows for those same jobs
3. Deletes Job rows older than 30 days with status in ('filtered_out', 'rejected')
4. Deletes Job rows older than 90 days with status not in ('applied')
5. Deletes EmailLog rows older than 60 days
6. Runs `VACUUM` on the SQLite DB after deletion to reclaim space (once a month)
7. Writes a cleanup summary to logs: rows deleted, MB reclaimed

## Where the code lives

`backend/services/cleanup.py` — imported by `scheduler.py`.

```python
# scheduler.py addition
sched.add_job(
    weekly_cleanup,
    trigger=CronTrigger(day_of_week='sun', hour=2, minute=0, timezone=TZ),
    id="weekly_cleanup",
    replace_existing=True,
)
```

## Storage stats endpoint

`GET /admin/storage-stats` — returns JSON with:
```json
{
  "db_size_mb": 45.2,
  "pdf_count": 312,
  "pdf_size_mb": 37.4,
  "total_mb": 82.6,
  "jobs_total": 4821,
  "jobs_applied": 47,
  "oldest_job_date": "2026-06-07",
  "last_cleanup_ran": "2026-06-08T02:00:00"
}
```

Also surface a summary line on the dashboard header:
`DB 45MB · PDFs 37MB · Last cleanup: 2 days ago`

## VACUUM behaviour
SQLite `VACUUM` rewrites the entire DB file to reclaim space after deletions.
On a 300MB DB this takes ~5-10 seconds and causes a brief write lock.
Running it at 02:00 IST Sunday means zero overlap with normal usage.
Run VACUUM once a month (first Sunday of month), not every week.
