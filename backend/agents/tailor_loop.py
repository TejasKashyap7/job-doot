"""Critic ↔ Improver loop for one (job, user) pair. Multi-user (see
.claude/specs/multi-user/approach.md): each user has their own master resume,
project library, and Groq keys, so the same job gets tailored independently per
user — status lives on JobUserState, not on Job.

Round 1: critic on master resume
  → APPROVED → compile, ready
  → NEEDS WORK → improver
Round 2: critic on improved → improver if still needs work
Round 3: final improver pass + critic check
  → APPROVED → ready
  → still NEEDS WORK → compile anyway, mark 'review_needed'

Always saves the final LaTeX + PDF + critic verdict + changelog into Resume row.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from sqlalchemy.orm import Session

from agents import critic, improver
from agents.prompts import build_improver_system
from agents.quality_check import evaluate
from database.models import GroqKey, Job, JobUserState, Resume, User
from services.latex_compiler import compile_latex, LatexCompileError

log = logging.getLogger(__name__)

MAX_ROUNDS = 3
INTER_CALL_DELAY = 2  # gentle on Groq TPM
# Cost gate: only AUTO-tailor jobs scoring >= this. Tailoring is Groq-expensive
# (critic + improver x up to 3 rounds); auto-tailoring every scored job (>=6) was
# exhausting the free-tier quota so most CVs silently failed. Tune via env.
TAILOR_MIN_SCORE = float(os.getenv("TAILOR_MIN_SCORE", "9"))
# Hard cap on jobs auto-tailored per consumer pass PER USER. ~2 tailors is enough
# to exhaust a single Groq account's free-tier budget; multiple keys (rotation)
# push this further before falling back, but the cap still bounds one pass.
TAILOR_MAX_PER_PASS = int(os.getenv("TAILOR_MAX_PER_PASS", "2"))


def _user_groq_keys(db: Session, user: User) -> list[str]:
    rows = (
        db.query(GroqKey.key)
        .filter(GroqKey.user_id == user.id, GroqKey.is_active.is_(True))
        .order_by(GroqKey.id)
        .all()
    )
    return [r[0] for r in rows]


def _get_state(db: Session, job: Job, user: User) -> JobUserState:
    state = (
        db.query(JobUserState)
        .filter(JobUserState.job_id == job.id, JobUserState.user_id == user.id)
        .first()
    )
    if not state:
        raise ValueError(f"No JobUserState for job {job.id} / user {user.username}")
    return state


def tailor_for_job(db: Session, job: Job, user: User) -> Resume:
    """Run the loop for one (job, user) pair. Persists Resume row, sets state.status."""
    if not job.raw_description:
        raise ValueError(f"Job {job.id} has no description")
    if not user.master_resume_tex:
        raise ValueError(f"User {user.username} has no master_resume_tex set")

    state = _get_state(db, job, user)
    log.info("[job %d / user %s] tailor loop start: %s @ %s",
              job.id, user.username, job.title, job.company)
    state.status = "tailoring"
    db.commit()

    keys = _user_groq_keys(db, user)
    system_improver = build_improver_system(user)
    master_latex = user.master_resume_tex
    current_latex = master_latex
    last_critic = None
    last_improver = None
    iteration = 0

    tailoring_failed = False
    try:
        if not keys:
            raise RuntimeError(f"User {user.username} has no active Groq keys")
        for rnd in range(1, MAX_ROUNDS + 1):
            iteration = rnd
            log.info("[job %d / user %s] round %d: critic", job.id, user.username, rnd)
            last_critic = critic.review(current_latex, job.title, job.company,
                                         job.raw_description, api_keys=keys)
            time.sleep(INTER_CALL_DELAY)

            if last_critic["verdict"] == "APPROVED":
                log.info("[job %d / user %s] approved at round %d", job.id, user.username, rnd)
                break

            # Last round: don't bother improving again — we'll compile current as-is
            if rnd == MAX_ROUNDS:
                log.info("[job %d / user %s] still needs work after %d rounds — accepting "
                         "current LaTeX", job.id, user.username, MAX_ROUNDS)
                break

            log.info("[job %d / user %s] round %d: improver (%d shortcomings)",
                     job.id, user.username, rnd, len(last_critic["shortcomings"]))
            last_improver = improver.improve(
                system_improver, current_latex, job.title, job.company, job.raw_description,
                last_critic["shortcomings"], api_keys=keys,
            )
            new_latex = last_improver["latex"]
            if new_latex == current_latex:
                log.warning("[job %d / user %s] improver returned identical LaTeX at round %d "
                            "— stopping early", job.id, user.username, rnd)
                break
            current_latex = new_latex
            time.sleep(INTER_CALL_DELAY)
    except Exception as e:
        # All of this user's Groq keys down/rate-limited (or any agent error): don't
        # lose the job. Fall back to their master résumé — the rule is: if we can't
        # tailor, use the old CV as-is.
        tailoring_failed = True
        log.warning("[job %d / user %s] tailoring unavailable (%s) — using master résumé",
                    job.id, user.username, e)
        current_latex = master_latex

    # Compile whatever we ended up with. A PDF MUST exist for every tailored job
    # (Flaw 11 ruling: no opportunity is missed — gaps are dashboard metadata, the
    # resume itself is always submission-ready). Fallback chain:
    #   tailored LaTeX → master resume LaTeX.
    pdf_id = f"{job.id}_{user.id}"
    try:
        pdf_path = compile_latex(current_latex, pdf_id)
        compile_ok = True
        compile_err = ""
    except LatexCompileError as e:
        compile_ok = False
        compile_err = str(e) + ("\n" + e.log_excerpt[-1500:] if e.log_excerpt else "")
        log.error("[job %d / user %s] compile failed: %s — falling back to master resume",
                  job.id, user.username, compile_err[:300])
        try:
            current_latex = master_latex  # persist what the PDF actually contains
            pdf_path = compile_latex(current_latex, pdf_id)
            compile_err += "\n[FALLBACK] Tailored LaTeX failed to compile; master resume PDF produced instead."
        except LatexCompileError as e2:
            log.error("[job %d / user %s] master fallback also failed: %s",
                      job.id, user.username, e2)
            pdf_path = None

    final_status = (
        "ready" if (compile_ok and last_critic and last_critic["verdict"] == "APPROVED")
        else "review_needed"
    )

    # Flaw 2: mechanical tailoring checks over the final resume (no Groq call).
    quality = evaluate(master_latex, current_latex, job.raw_description)
    log.info("[job %d / user %s] tailoring check: similarity=%.3f coverage=%s confidence=%s missing=%s",
             job.id, user.username, quality["similarity"], quality["coverage"],
             quality["confidence"], quality["missing_skills"])

    resume = Resume(
        job_id=job.id,
        user_id=user.id,
        latex_content=current_latex,
        pdf_path=str(pdf_path) if pdf_path else None,
        iteration_count=iteration,
        critic_verdict=last_critic["verdict"] if last_critic else "UNKNOWN",
        changelog=(last_improver or {}).get("changelog", "") if last_improver else "",
        unfixable_items=(last_improver or {}).get("unfixable", "") if last_improver else "",
        similarity_to_master=quality["similarity"],
        jd_skill_coverage=quality["coverage"],
        created_at=datetime.utcnow(),
    )
    if tailoring_failed:
        resume.critic_verdict = "TAILORING UNAVAILABLE"
        resume.unfixable_items = (resume.unfixable_items or "") + \
            "\n\n[TAILORING UNAVAILABLE] All Groq keys rate-limited/down — master résumé used as-is."
    if not compile_ok:
        resume.unfixable_items = (resume.unfixable_items or "") + f"\n\n[COMPILE ERROR]\n{compile_err}"
    db.add(resume)

    state.status = final_status
    db.commit()
    log.info("[job %d / user %s] done: status=%s pdf=%s rounds=%d",
             job.id, user.username, final_status, pdf_path, iteration)
    return resume


def tailor_pending(db: Session, limit: int | None = None) -> dict:
    """For every user, run the tailor loop on their scored jobs at/above the cost
    gate (TAILOR_MIN_SCORE)."""
    users = db.query(User).all()
    counts = {"ready": 0, "review_needed": 0, "errors": 0}
    for user in users:
        q = (
            db.query(JobUserState, Job)
            .join(Job, JobUserState.job_id == Job.id)
            .filter(JobUserState.user_id == user.id, JobUserState.status == "scored",
                    JobUserState.score >= TAILOR_MIN_SCORE)
            .order_by(JobUserState.score.desc(), JobUserState.job_id)
        )
        if limit:
            q = q.limit(limit)
        rows = q.all()
        if not rows:
            continue
        log.info("Tailoring %d job(s) for user %s", len(rows), user.username)
        for state, job in rows:
            try:
                tailor_for_job(db, job, user)
                counts[state.status] = counts.get(state.status, 0) + 1
            except Exception as e:
                log.exception("Tailor failed for job %d / user %s: %s", job.id, user.username, e)
                counts["errors"] += 1
    return counts
