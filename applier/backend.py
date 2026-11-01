"""Read-only access to the backend's data via `docker exec` into its container.

data/jobs.db is owned by root inside the container, so the host-side applier asks the
container's Python to read it and print JSON. Nothing here writes to jobs.db.
"""
import json
import subprocess

_JOBS = r"""
import json, sqlite3, sys
uid, min_score = int(sys.argv[1]), float(sys.argv[2])
c = sqlite3.connect('/app/data/jobs.db')
rows = c.execute('''
  SELECT j.id, j.title, j.company, j.apply_url, s.score
  FROM jobs j JOIN job_user_state s ON s.job_id = j.id
  WHERE s.user_id = ? AND s.score >= ? AND j.apply_url LIKE '%linkedin.com/jobs/view/%'
  ORDER BY j.date_scraped DESC
''', (uid, min_score)).fetchall()
print(json.dumps([dict(id=r[0], title=r[1], company=r[2], url=r[3], score=r[4]) for r in rows]))
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
    return _run(cfg["backend_container"], _JOBS, cfg["pick_jobs_from_user_id"], cfg["min_score"])


def telegram_creds(cfg) -> dict | None:
    try:
        return _run(cfg["backend_container"], _TG, cfg["notify_user_id"])
    except Exception:
        return None
