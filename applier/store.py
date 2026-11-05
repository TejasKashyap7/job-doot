"""The applier's own SQLite file (data/applier/applier.db).

Kept separate from data/jobs.db: that file is owned by root (the backend container)
and the applier runs as the desktop user on the Pi host. Both live under ./data, so the
dashboard container can still read this file later (/qa page).
"""
import sqlite3
from datetime import datetime, timedelta

from .config import DATA

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    applicant TEXT NOT NULL,
    job_id INTEGER NOT NULL,
    url TEXT, title TEXT, company TEXT,
    status TEXT NOT NULL,          -- applied|skipped|failed|paused
    detail TEXT,                   -- reason / question / error
    steps INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_attempts_applicant_job ON attempts(applicant, job_id);
CREATE TABLE IF NOT EXISTS qa_bank (
    id INTEGER PRIMARY KEY,
    applicant TEXT NOT NULL,
    question TEXT NOT NULL,
    field_type TEXT,
    options TEXT,
    answer TEXT,
    status TEXT NOT NULL DEFAULT 'UNANSWERED',   -- UNANSWERED|ANSWERED
    job_id INTEGER,
    first_seen TEXT NOT NULL,
    answered_at TEXT,
    UNIQUE(applicant, question)
);
"""

# Statuses (detail prefix) that mean "never try this job again".
FINAL = ("applied", "already_applied", "not_easy_apply", "closed", "needs_human")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / "applier.db", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def log_attempt(conn, applicant, job, status, detail="", steps=0):
    conn.execute(
        "INSERT INTO attempts(applicant, job_id, url, title, company, status, detail, steps, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (applicant, job["id"], job.get("url"), job.get("title"), job.get("company"),
         status, (detail or "")[:1000], steps, now()),
    )
    conn.commit()


def excluded_job_ids(conn, applicant) -> set[int]:
    """Jobs not to try now: finished ones, ones failed twice, and ones waiting on an
    unanswered Q&A question (they come back once Tejas answers)."""
    rows = conn.execute(
        "SELECT job_id, status, detail FROM attempts WHERE applicant=?", (applicant,)
    ).fetchall()
    out, fails = set(), {}
    for r in rows:
        if r["status"] == "applied" or (r["detail"] or "").split(":")[0] in FINAL:
            out.add(r["job_id"])
        elif r["status"] == "failed":
            fails[r["job_id"]] = fails.get(r["job_id"], 0) + 1
    out |= {j for j, n in fails.items() if n >= 2}
    waiting = conn.execute(
        "SELECT DISTINCT job_id FROM qa_bank WHERE applicant=? AND status='UNANSWERED' AND job_id IS NOT NULL",
        (applicant,),
    ).fetchall()
    out |= {r["job_id"] for r in waiting}
    return out


def add_question(conn, applicant, question, field_type, options, job_id) -> bool:
    """Returns True if this is a new question (worth a Telegram ping)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO qa_bank(applicant, question, field_type, options, job_id, first_seen)"
        " VALUES (?,?,?,?,?,?)",
        (applicant, question.strip(), field_type, " | ".join(options or []), job_id, now()),
    )
    conn.commit()
    return cur.rowcount == 1


def answered(conn, applicant) -> list[dict]:
    rows = conn.execute(
        "SELECT question, answer FROM qa_bank WHERE applicant=? AND status='ANSWERED'", (applicant,)
    ).fetchall()
    return [dict(r) for r in rows]


def unanswered(conn, applicant) -> list[dict]:
    rows = conn.execute(
        "SELECT id, question, field_type, options, job_id FROM qa_bank"
        " WHERE applicant=? AND status='UNANSWERED' ORDER BY id", (applicant,)
    ).fetchall()
    return [dict(r) for r in rows]


def answer(conn, qa_id: int, text: str):
    conn.execute(
        "UPDATE qa_bank SET answer=?, status='ANSWERED', answered_at=? WHERE id=?",
        (text, now(), qa_id),
    )
    conn.commit()


def day_summary(conn, applicant, hours=24) -> dict:
    since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT status, detail, title, company FROM attempts WHERE applicant=? AND created_at>=?",
        (applicant, since),
    ).fetchall()
    out = {"applied": [], "skipped": 0, "failed": [], "paused": 0, "needs_human": []}
    for r in rows:
        if r["status"] == "applied":
            out["applied"].append(f"{r['title']} — {r['company']}")
        elif r["status"] == "failed":
            out["failed"].append(f"{r['title']} — {r['company']}: {(r['detail'] or '')[:80]}")
        elif r["status"] == "skipped":
            out["skipped"] += 1
            if (r["detail"] or "").startswith("needs_human:"):
                out["needs_human"].append(f"{r['title']} — {r['company']}: {(r['detail'] or '')[12:200]}")
        else:
            out["paused"] += 1
    return out
