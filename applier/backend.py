"""Read-only access to the backend's data via `docker exec` into its container.

data/jobs.db is owned by root inside the container, so the host-side applier asks the
container's Python to read it and print JSON. Nothing here writes to jobs.db.
"""
import json
import subprocess

_JOBS = r"""
import json, sqlite3, sys
uid, min_score, include_offsite = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3] == "1"
c = sqlite3.connect('/app/data/jobs.db')
cols = {r[1] for r in c.execute('PRAGMA table_info(jobs)')}
has_type = 'apply_type' in cols
type_sql = "j.apply_type" if has_type else "NULL"
where_type = "" if (include_offsite or not has_type) else " AND (j.apply_type IS NULL OR j.apply_type != 'offsite')"
rows = c.execute(f'''
  SELECT j.id, j.title, j.company, j.apply_url, s.score, {type_sql}
  FROM jobs j JOIN job_user_state s ON s.job_id = j.id
  WHERE s.user_id = ? AND s.score >= ? AND j.apply_url LIKE '%linkedin.com/jobs/view/%'{where_type}
  ORDER BY CASE {type_sql} WHEN 'easy' THEN 0 WHEN 'offsite' THEN 2 ELSE 1 END, j.date_scraped DESC
''', (uid, min_score)).fetchall()
print(json.dumps([dict(id=r[0], title=r[1], company=r[2], url=r[3], score=r[4], apply_type=r[5]) for r in rows]))
"""

# Jobs fetched (scraped) since an IST midnight; date_scraped is naive UTC (datetime.utcnow).
_FETCHED = r"""
import json, sqlite3, sys
c = sqlite3.connect('/app/data/jobs.db')
print(json.dumps(c.execute('SELECT count(*) FROM jobs WHERE date_scraped >= ?', (sys.argv[1],)).fetchone()[0]))
"""

_TG = r"""
import json, sqlite3, sys
c = sqlite3.connect('/app/data/jobs.db')
r = c.execute('SELECT telegram_enabled, telegram_bot_token, telegram_chat_id FROM users WHERE id=?',
              (int(sys.argv[1]),)).fetchone()
print(json.dumps(r and {'enabled': bool(r[0]), 'token': r[1], 'chat_id': r[2]}))
"""


def _run(container: str, code: str, *args) -> object:
    out = subprocess.run(
        ["docker", "exec", container, "python", "-c", code, *map(str, args)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return json.loads(out.stdout)


def candidate_jobs(cfg) -> list[dict]:
    # Company-site ("offsite") jobs are skipped until the Phase 2 company-site applier ships.
    return _run(cfg["backend_container"], _JOBS, cfg["pick_jobs_from_user_id"], cfg["min_score"],
                "1" if cfg.get("include_offsite") else "0")


def fetched_since(cfg, utc_naive_iso: str) -> int:
    return int(_run(cfg["backend_container"], _FETCHED, utc_naive_iso))


def telegram_creds(cfg) -> dict | None:
    try:
        return _run(cfg["backend_container"], _TG, cfg["notify_user_id"])
    except Exception:
        return None
