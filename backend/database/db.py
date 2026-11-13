import logging
import os
import secrets
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/jobs.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

# WAL so backend + gmail-watcher can both touch the same file safely.
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  (register models)
    os.makedirs(os.path.dirname(DATABASE_URL.split("///")[-1]) or ".", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _migrate_to_multi_user()


def _ensure_columns():
    """Lightweight idempotent migration: add columns that create_all won't add to
    a table that already exists. SQLite ADD COLUMN is safe and non-locking."""
    wanted = {
        "jobs": {
            "apply_type": "VARCHAR",
        },
        "notifications": {
            "tag": "VARCHAR",
            "tech": "TEXT",
        },
        "resumes": {
            "similarity_to_master": "FLOAT",
            "jd_skill_coverage": "FLOAT",
            "user_id": "INTEGER",
        },
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, sqltype in cols.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}")


def _migrate_to_multi_user():
    """One-time, idempotent migration (see .claude/specs/multi-user/approach.md):
    backfill Tejas as the first `users` row from what used to be hardcoded in
    agents/prompts.py, copy existing Job score/status/matches/gaps/date_applied
    into job_user_state keyed to that user, and backfill Resume.user_id.

    Additive-first: nothing is deleted until it has been copied elsewhere. The old
    columns are dropped from `jobs` only as a best-effort last step (SQLite 3.35+);
    if that fails on an older SQLite build, they're just left as unused columns —
    harmless, since the ORM no longer reads/writes them.

    Detects whether it has already run by checking for `jobs.status` — once
    dropped (or on a fresh multi-user install where it never existed), this is a
    no-op on every subsequent startup.
    """
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(jobs)")}
        if "status" not in cols:
            return  # already migrated, or fresh install — nothing to do

        from database import seed_tejas
        from services.auth import hash_password

        row = conn.exec_driver_sql("SELECT id FROM users WHERE username = 'tejas'").fetchone()
        if row:
            tejas_id = row[0]
        else:
            password = os.getenv("DASHBOARD_PASSWORD") or secrets.token_urlsafe(16)
            master_resume = ""
            for p in (Path("master_resume.tex"), Path("/app/master_resume.tex")):
                if p.exists():
                    master_resume = p.read_text(encoding="utf-8")
                    break
            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
            telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
            conn.exec_driver_sql(
                "INSERT INTO users (username, password_hash, is_admin, telegram_enabled, "
                "telegram_bot_token, telegram_chat_id, candidate_profile, locked_skill_set, "
                "project_library, role_type_prefs, location_prefs, salary_pref, "
                "master_resume_tex, created_at) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "tejas", hash_password(password), bool(telegram_token),
                    telegram_token, telegram_chat,
                    seed_tejas.CANDIDATE_PROFILE, seed_tejas.LOCKED_SKILL_SET,
                    seed_tejas.PROJECT_LIBRARY, seed_tejas.ROLE_TYPE_PREFS,
                    seed_tejas.LOCATION_PREFS, seed_tejas.SALARY_PREF, master_resume,
                    datetime.utcnow().isoformat(),
                ),
            )
            tejas_id = conn.exec_driver_sql(
                "SELECT id FROM users WHERE username = 'tejas'"
            ).fetchone()[0]

            groq_key = os.getenv("GROQ_API_KEY")
            if groq_key:
                conn.exec_driver_sql(
                    "INSERT INTO groq_keys (user_id, key, label, is_active, created_at) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (tejas_id, groq_key, "primary (from .env)", datetime.utcnow().isoformat()),
                )
            log.warning(
                "Multi-user migration: created users row for 'tejas' (id=%d). "
                "Dashboard login now requires a username — use 'tejas' with the same "
                "password as before (from DASHBOARD_PASSWORD).", tejas_id,
            )

        already_migrated = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM job_user_state"
        ).fetchone()[0]
        if not already_migrated:
            rows = conn.exec_driver_sql(
                "SELECT id, score, domain_flag, top_matches, top_gaps, status, date_applied "
                "FROM jobs"
            ).fetchall()
            for (job_id, score, domain_flag, top_matches, top_gaps, jstatus, date_applied) in rows:
                conn.exec_driver_sql(
                    "INSERT INTO job_user_state (job_id, user_id, score, domain_flag, "
                    "top_matches, top_gaps, status, date_applied, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (job_id, tejas_id, score, domain_flag, top_matches, top_gaps,
                     jstatus or "scored", date_applied, datetime.utcnow().isoformat()),
                )
            log.warning("Multi-user migration: copied %d job(s) into job_user_state for tejas",
                        len(rows))

        conn.exec_driver_sql(
            "UPDATE resumes SET user_id = ? WHERE user_id IS NULL", (tejas_id,)
        )

        for col in ("score", "domain_flag", "top_matches", "top_gaps", "status", "date_applied"):
            # DROP COLUMN fails if an old index still references it (e.g. status
            # had index=True in the single-tenant model) — clear that first.
            try:
                conn.exec_driver_sql(f"DROP INDEX IF EXISTS ix_jobs_{col}")
            except Exception:
                pass
            try:
                conn.exec_driver_sql(f"ALTER TABLE jobs DROP COLUMN {col}")
            except Exception as e:
                log.warning("Could not drop jobs.%s (SQLite too old?) — leaving as an "
                            "unused column, harmless: %s", col, e)
