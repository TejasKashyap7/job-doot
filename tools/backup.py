#!/usr/bin/env python3
"""Monthly off-site DB backup (Flaws 7 & 16).

Takes a SAFE, consistent snapshot of jobs.db (SQLite online-backup API — works while the
app is writing, WAL and all), verifies it (PRAGMA integrity_check), gzips it into a
private backup repo, and pushes. Host python3 stdlib only — no venv, no app deps.

Run by Pi cron, e.g.  0 3 1 * *  (03:00 on the 1st of each month). Independent of the
backend so a crash at month-end doesn't skip the backup.

Config (env, with sensible Pi defaults):
  JOBDOOT_DB          path to the live DB        (default /home/tejas/job-doot/data/jobs.db)
  JOBDOOT_BACKUP_REPO git clone of the backup repo (default /home/tejas/job-doot-backup)

One-time restore test (Flaw 16), run by hand once:
  gunzip -c ~/job-doot-backup/jobs-YYYY-MM.db.gz > /tmp/r.db
  sqlite3 /tmp/r.db "select count(*) from jobs"
"""
import datetime
import gzip
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = Path(os.getenv("JOBDOOT_DB", "/home/tejas/job-doot/data/jobs.db"))
BACKUP_REPO = Path(os.getenv("JOBDOOT_BACKUP_REPO", "/home/tejas/job-doot-backup"))


def _git(*args: str) -> None:
    subprocess.run(["git", "-C", str(BACKUP_REPO), *args], check=True)


def main() -> int:
    if not DB.exists():
        print(f"[backup] DB not found: {DB}", file=sys.stderr)
        return 1
    if not (BACKUP_REPO / ".git").exists():
        print(f"[backup] backup repo not a git clone: {BACKUP_REPO}", file=sys.stderr)
        return 1

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")  # monthly file, overwritten in-month
    tmp = Path("/tmp") / f"jobs-{stamp}.db"

    # 1. Consistent hot snapshot (safe even while the app writes to the live DB).
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    dst = sqlite3.connect(str(tmp))
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()

    # 2. Verify the snapshot actually opens and isn't torn.
    chk = sqlite3.connect(str(tmp))
    try:
        result = chk.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        chk.close()
    if result != "ok":
        print(f"[backup] integrity_check FAILED: {result}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return 2

    # 3. Gzip into the backup repo.
    out = BACKUP_REPO / f"jobs-{stamp}.db.gz"
    with open(tmp, "rb") as f_in, gzip.open(out, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    tmp.unlink(missing_ok=True)

    # 4. Commit + push (no-op commit is fine to skip).
    _git("add", out.name)
    status = subprocess.run(["git", "-C", str(BACKUP_REPO), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.strip()
    if not status:
        print(f"[backup] no change since last backup ({out.name})")
        return 0
    _git("commit", "-m", f"backup {stamp}")
    _git("push")
    print(f"[backup] OK: {out.name} ({out.stat().st_size} bytes) pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
