import csv
import hashlib
import logging
import re
from typing import Iterable
from sqlalchemy.orm import Session
from database.models import Job

log = logging.getLogger(__name__)


def _hash_job(title: str, company: str, apply_url: str, description: str = "") -> str:
    return hashlib.sha256(f"{title}|{company}|{apply_url}|{description[:200]}".encode()).hexdigest()


def _coerce_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "t"}


def ingest_rows(db: Session, rows: Iterable[dict]) -> dict:
    """Insert new jobs, skip duplicates by (title, company, apply_url) hash. Returns counts."""
    inserted, skipped = 0, 0
    for row in rows:
        title = (row.get("title") or "").strip()
        company = (row.get("company") or "").strip()
        apply_url = (row.get("apply_url") or "").strip()
        if not title or not company:
            skipped += 1
            continue

        raw_description = (
            row.get("description") or row.get("job_description") or
            row.get("jd") or row.get("raw_description") or ""
        ).strip()

        h = _hash_job(title, company, apply_url, raw_description)
        if db.query(Job.id).filter(Job.source_hash == h).first():
            skipped += 1
            continue

        loc = (row.get("location") or "").strip()
        remote = bool(re.search(r"\bremote\b", loc, re.IGNORECASE))

        db.add(Job(
            title=title,
            company=company,
            location=loc,
            salary=(row.get("salary") or "").strip() or None,
            remote_flag=remote,
            easy_apply=_coerce_bool(row.get("easy_apply", False)),
            apply_url=apply_url or None,
            raw_description=raw_description,
            status="scraped",
            source_hash=h,
        ))
        inserted += 1

    db.commit()
    log.info("Ingest done: inserted=%d skipped=%d", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped}


def load_csv(db: Session, csv_path: str) -> dict:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return ingest_rows(db, reader)
