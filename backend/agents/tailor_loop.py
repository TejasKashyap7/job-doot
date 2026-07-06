"""Critic ↔ Improver loop for one job.

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
from pathlib import Path

from sqlalchemy.orm import Session

from agents import critic, improver
from agents.quality_check import evaluate
from database.models import Job, Resume
from services.latex_compiler import compile_latex, LatexCompileError

log = logging.getLogger(__name__)

MAX_ROUNDS = 3
INTER_CALL_DELAY = 2  # gentle on Groq TPM
# Cost gate: only AUTO-tailor jobs scoring >= this. Tailoring is Groq-expensive
# (critic + improver x up to 3 rounds); auto-tailoring every scored job (>=6) was
# exhausting the free-tier quota so most CVs silently failed. Tune via env.
TAILOR_MIN_SCORE = float(os.getenv("TAILOR_MIN_SCORE", "9"))
# Hard cap on jobs auto-tailored per consumer pass. ~2 tailors is enough to exhaust the
# Groq free-tier budget, so cap low; the rest wait for the next pass (or use the master).
TAILOR_MAX_PER_PASS = int(os.getenv("TAILOR_MAX_PER_PASS", "2"))


def _read_master_resume() -> str:
    # Path resolves the same in container (/app/master_resume.tex) and locally
    # (backend/master_resume.tex when uvicorn cwd is backend/).
    candidates = [Path("master_resume.tex"), Path("/app/master_resume.tex")]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError("master_resume.tex not found in cwd or /app")


def tailor_for_job(db: Session, job: Job) -> Resume:
    """Run the loop for one job. Persists Resume row, sets job.status."""
    if not job.raw_description:
        raise ValueError(f"Job {job.id} has no description")

    log.info("[job %d] tailor loop start: %s @ %s", job.id, job.title, job.company)
    job.status = "tailoring"
    db.commit()

    try:
        current_latex = _read_master_resume()
    except FileNotFoundError as e:
        log.error("[job %d] master_resume.tex not found: %s — resetting to 'scored'", job.id, e)
        job.status = "scored"
        db.commit()
        raise
    master_latex = current_latex  # original, for the Flaw 2 change-check
    last_critic = None
    last_improver = None
    iteration = 0

    tailoring_failed = False
    try:
        for rnd in range(1, MAX_ROUNDS + 1):
            iteration = rnd
            log.info("[job %d] round %d: critic", job.id, rnd)
            last_critic = critic.review(current_latex, job.title, job.company, job.raw_description)
            time.sleep(INTER_CALL_DELAY)

            if last_critic["verdict"] == "APPROVED":
                log.info("[job %d] approved at round %d", job.id, rnd)
                break

            # Last round: don't bother improving again — we'll compile current as-is
            if rnd == MAX_ROUNDS:
                log.info("[job %d] still needs work after %d rounds — accepting current LaTeX",
                         job.id, MAX_ROUNDS)
                break

            log.info("[job %d] round %d: improver (%d shortcomings)",
                     job.id, rnd, len(last_critic["shortcomings"]))
            last_improver = improver.improve(
                current_latex, job.title, job.company, job.raw_description,
                last_critic["shortcomings"],
            )
            new_latex = last_improver["latex"]
            if new_latex == current_latex:
                log.warning("[job %d] improver returned identical LaTeX at round %d — stopping early", job.id, rnd)
                break
            current_latex = new_latex
            time.sleep(INTER_CALL_DELAY)
    except Exception as e:
        # Groq down/rate-limited (or any agent error): don't lose the job. Fall back to
        # the master résumé — Tejas's rule: if we can't tailor, use the old CV as-is.
        tailoring_failed = True
        log.warning("[job %d] tailoring unavailable (%s) — using master résumé", job.id, e)
        current_latex = master_latex

    # Compile whatever we ended up with. A PDF MUST exist for every tailored job
    # (Flaw 11 ruling: no opportunity is missed — gaps are dashboard metadata, the
    # resume itself is always submission-ready). Fallback chain:
    #   tailored LaTeX → master resume LaTeX.
    try:
        pdf_path = compile_latex(current_latex, job.id)
        compile_ok = True
        compile_err = ""
    except LatexCompileError as e:
        compile_ok = False
        compile_err = str(e) + ("\n" + e.log_excerpt[-1500:] if e.log_excerpt else "")
        log.error("[job %d] compile failed: %s — falling back to master resume",
                  job.id, compile_err[:300])
        try:
            master_latex = _read_master_resume()
            pdf_path = compile_latex(master_latex, job.id)
            current_latex = master_latex  # persist what the PDF actually contains
            compile_err += "\n[FALLBACK] Tailored LaTeX failed to compile; master resume PDF produced instead."
        except (LatexCompileError, FileNotFoundError) as e2:
            log.error("[job %d] master fallback also failed: %s", job.id, e2)
            pdf_path = None

    final_status = (
        "ready" if (compile_ok and last_critic and last_critic["verdict"] == "APPROVED")
        else "review_needed"
    )

    # Flaw 2: mechanical tailoring checks over the final resume (no Groq call).
    quality = evaluate(master_latex, current_latex, job.raw_description)
    log.info("[job %d] tailoring check: similarity=%.3f coverage=%s confidence=%s missing=%s",
             job.id, quality["similarity"], quality["coverage"],
             quality["confidence"], quality["missing_skills"])

    resume = Resume(
        job_id=job.id,
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
            "\n\n[TAILORING UNAVAILABLE] Groq was rate-limited/down — master résumé used as-is."
    if not compile_ok:
        resume.unfixable_items = (resume.unfixable_items or "") + f"\n\n[COMPILE ERROR]\n{compile_err}"
    db.add(resume)

    job.status = final_status
    db.commit()
    log.info("[job %d] done: status=%s pdf=%s rounds=%d",
             job.id, final_status, pdf_path, iteration)
    return resume


def tailor_pending(db: Session, limit: int | None = None) -> dict:
    """Run tailor loop on scored jobs at/above the cost gate (TAILOR_MIN_SCORE)."""
    q = (db.query(Job)
         .filter(Job.status == "scored", Job.score >= TAILOR_MIN_SCORE)
         .order_by(Job.score.desc(), Job.id))
    if limit:
        q = q.limit(limit)
    jobs = q.all()
    log.info("Tailoring %d job(s)", len(jobs))
    counts = {"ready": 0, "review_needed": 0, "errors": 0}
    for job in jobs:
        try:
            tailor_for_job(db, job)
            counts[job.status] = counts.get(job.status, 0) + 1
        except Exception as e:
            log.exception("Tailor failed for job %d: %s", job.id, e)
            counts["errors"] += 1
    return counts
