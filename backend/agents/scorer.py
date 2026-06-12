"""Scorer agent — runs Groq over each scraped job, fills score/domain_flag/matches/gaps.

Status transitions:
- score 0  → status='rejected'
- score <6 → status='filtered_out'
- score >=6 → status='scored' (next stage: tailoring loop)
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from agents.prompts import SCORER_SYSTEM
from database.models import Job
from services.groq_client import chat_json
from services import telegram as tg
import services.alerts as alerts_svc

log = logging.getLogger(__name__)

SCORER_DELAY_SEC = 3   # spec: 3s between calls to respect TPM


def _build_user_msg(job: Job) -> str:
    return (
        f"JOB TITLE: {job.title}\n"
        f"COMPANY: {job.company}\n"
        f"LOCATION: {job.location or 'unspecified'}\n"
        f"SALARY: {job.salary or 'unspecified'}\n"
        f"\nJOB DESCRIPTION:\n{job.raw_description or '(no description provided)'}"
    )


def _next_status(score: float) -> str:
    if score == 0:
        return "rejected"
    if score < 6:
        return "filtered_out"
    return "scored"


def score_job(db: Session, job: Job) -> dict:
    """Score one job, persist results, return the parsed Groq response."""
    log.info("Scoring job %d: %s @ %s", job.id, job.title, job.company)
    result = chat_json(SCORER_SYSTEM, _build_user_msg(job), temperature=0.1, max_tokens=512)

    score = max(0.0, min(10.0, float(result.get("score", 0))))
    job.score = score
    job.domain_flag = result.get("domain_flag")
    job.top_matches = result.get("top_matches") or []
    job.top_gaps = result.get("top_gaps") or []
    job.status = _next_status(score)
    db.commit()
    log.info("  → score=%.1f domain=%s status=%s", score, job.domain_flag, job.status)
    return result


def score_pending(db: Session, limit: int | None = None) -> dict:
    """Score every job in status='scraped'. Returns aggregate counts."""
    q = db.query(Job).filter(Job.status == "scraped").order_by(Job.id)
    if limit:
        q = q.limit(limit)
    jobs = q.all()
    log.info("Scoring %d pending job(s)", len(jobs))

    counts = {"scored": 0, "filtered_out": 0, "rejected": 0, "errors": 0}
    for i, job in enumerate(jobs):
        try:
            score_job(db, job)
            counts[job.status] = counts.get(job.status, 0) + 1
        except Exception as e:
            log.exception("Scoring failed for job %d: %s", job.id, e)
            counts["errors"] += 1
        if i < len(jobs) - 1:
            time.sleep(SCORER_DELAY_SEC)
    if counts["errors"]:
        msg = (
            f"⚠️ Scoring failed for {counts['errors']} job(s) — Groq may be down. "
            f"They will retry tomorrow."
        )
        tg.send(msg)
        alerts_svc.set_alert(
            "scoring_failure", "warning",
            f"Groq scoring failed for {counts['errors']} job(s).",
            "Jobs will retry tomorrow. Check Pi logs if this persists.",
        )
    else:
        alerts_svc.clear_alert("scoring_failure")
    return counts
