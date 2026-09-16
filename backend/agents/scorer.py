"""Scorer agent — runs local Ollama over each scraped job, once per active user,
filling in a JobUserState row per (job, user) pair. Multi-user (see
.claude/specs/multi-user/approach.md): the same job can score differently for
different users because the system prompt is built from THAT user's own profile.

Status transitions (per user):
- score 0  → status='rejected'
- score <6 → status='filtered_out'
- score >=6 → status='scored' (next stage: tailoring loop)
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from agents.prompts import build_scorer_system
from database.models import Job, JobUserState, User
from services.local_llm_client import chat_json
from services import telegram as tg
import services.alerts as alerts_svc

log = logging.getLogger(__name__)

SCORER_DELAY_SEC = 3   # gentle pacing; Ollama has no hard TPM limit but this avoids pegging the Pi


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


def score_job_for_user(db: Session, job: Job, user: User) -> dict:
    """Score one job against one user's profile, upsert their JobUserState row."""
    log.info("Scoring job %d for user %s: %s @ %s", job.id, user.username, job.title, job.company)
    system = build_scorer_system(user)
    result = chat_json(system, _build_user_msg(job), temperature=0.1, max_tokens=512)

    score = max(0.0, min(10.0, float(result.get("score", 0))))
    state = (
        db.query(JobUserState)
        .filter(JobUserState.job_id == job.id, JobUserState.user_id == user.id)
        .first()
    )
    if not state:
        state = JobUserState(job_id=job.id, user_id=user.id)
        db.add(state)
    state.score = score
    state.domain_flag = result.get("domain_flag")
    state.top_matches = result.get("top_matches") or []
    state.top_gaps = result.get("top_gaps") or []
    state.status = _next_status(score)
    db.commit()
    log.info("  → user=%s score=%.1f domain=%s status=%s",
              user.username, score, state.domain_flag, state.status)
    return result


def score_pending(db: Session, limit: int | None = None) -> dict:
    """For every active user, score every job that doesn't yet have a JobUserState
    row for them. `limit` bounds jobs scored PER USER per pass (not a global cap)."""
    users = db.query(User).all()
    counts = {"scored": 0, "filtered_out": 0, "rejected": 0, "errors": 0}
    for user in users:
        already_scored = (
            db.query(JobUserState.job_id).filter(JobUserState.user_id == user.id).subquery()
        )
        q = db.query(Job).filter(~Job.id.in_(already_scored)).order_by(Job.id)
        if limit:
            q = q.limit(limit)
        jobs = q.all()
        if not jobs:
            continue
        log.info("Scoring %d pending job(s) for user %s", len(jobs), user.username)

        consecutive_fail = 0
        for i, job in enumerate(jobs):
            try:
                result = score_job_for_user(db, job, user)
                new_status = _next_status(max(0.0, min(10.0, float(result.get("score", 0)))))
                counts[new_status] = counts.get(new_status, 0) + 1
                consecutive_fail = 0
            except Exception as e:
                log.exception("Scoring failed for job %d / user %s: %s", job.id, user.username, e)
                counts["errors"] += 1
                consecutive_fail += 1
                # Ollama likely down — stop this user's pass instead of retry-storming;
                # the job stays unscored for them and picks back up next pass.
                if consecutive_fail >= 2:
                    log.warning("Local LLM unavailable — ending scoring pass for %s after %d "
                                "consecutive failures; %d job(s) remain for the next pass",
                                user.username, consecutive_fail, len(jobs) - i - 1)
                    break
            if i < len(jobs) - 1:
                time.sleep(SCORER_DELAY_SEC)

    if counts["errors"]:
        msg = (
            f"⚠️ Scoring failed for {counts['errors']} job(s) — local LLM (Ollama) may be down. "
            f"They will retry tomorrow."
        )
        tg.send(msg)
        alerts_svc.set_alert(
            "scoring_failure", "warning",
            f"Scoring failed for {counts['errors']} job(s).",
            "Jobs will retry tomorrow. Check the Ollama service on the Pi if this persists.",
        )
    else:
        alerts_svc.clear_alert("scoring_failure")
    return counts
