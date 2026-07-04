import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

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


def _ensure_columns():
    """Lightweight idempotent migration: add columns that create_all won't add to
    a table that already exists. SQLite ADD COLUMN is safe and non-locking."""
    wanted = {
        "resumes": {
            "similarity_to_master": "FLOAT",
            "jd_skill_coverage": "FLOAT",
        },
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, sqltype in cols.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}")
