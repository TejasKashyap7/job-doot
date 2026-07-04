import logging
import os
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, time as dtime
from pathlib import Path

from fastapi import FastAPI, Depends, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from database.db import init_db, get_db, SessionLocal
from database.models import Job, Resume
from services.ingest import ingest_rows, load_csv
from services.auth import COOKIE_NAME, check_password, make_cookie_value, require_login
import services.alerts as alerts_svc
from agents.scorer import score_pending, score_job
from agents.tailor_loop import tailor_pending, tailor_for_job
from agents.quality_check import confidence_label
from scheduler import start_scheduler, CSV_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("jobhunter")

IST = ZoneInfo("Asia/Kolkata")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["get_alerts"] = alerts_svc.get_alerts

scheduler = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global scheduler
    init_db()
    db = SessionLocal()
    try:
        stuck = db.query(Job).filter(Job.status == "tailoring").update({"status": "scored"})
        db.commit()
        if stuck:
            log.warning("Reset %d job(s) stuck at 'tailoring' from previous crashed run", stuck)
    finally:
        db.close()
    master_paths = [Path("master_resume.tex"), Path("/app/master_resume.tex")]
    if not any(p.exists() for p in master_paths):
        log.warning("CRITICAL: master_resume.tex not found — tailor loop will fail on next run")
    scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Job Hunter", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ---------------- Health & ingest ----------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook/jobs")
def webhook_jobs(request: Request, payload: dict, db: Session = Depends(get_db)):
    secret = os.getenv("WEBHOOK_SECRET", "")
    if secret and request.headers.get("Authorization") != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    rows = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="Expected JSON {'jobs': [...]}")
    return ingest_rows(db, rows)


@app.post("/admin/trigger-scrape", dependencies=[Depends(require_login)])
def trigger_scrape(db: Session = Depends(get_db)):
    return load_csv(db, CSV_PATH)


@app.post("/admin/score-pending", dependencies=[Depends(require_login)])
def admin_score_pending(limit: int | None = None, db: Session = Depends(get_db)):
    return score_pending(db, limit=limit)


@app.post("/admin/score-one/{job_id}", dependencies=[Depends(require_login)])
def admin_score_one(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return score_job(db, job)


@app.post("/admin/tailor-pending", dependencies=[Depends(require_login)])
def admin_tailor_pending(limit: int | None = None, db: Session = Depends(get_db)):
    return tailor_pending(db, limit=limit)


@app.post("/admin/tailor/{job_id}", dependencies=[Depends(require_login)])
def admin_tailor_one(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if not job.raw_description:
        raise HTTPException(400, "job has no description")
    resume = tailor_for_job(db, job)
    return {
        "job_id": job.id, "status": job.status, "iterations": resume.iteration_count,
        "verdict": resume.critic_verdict, "pdf_path": resume.pdf_path,
        "unfixable": resume.unfixable_items,
        "similarity_to_master": resume.similarity_to_master,
        "jd_skill_coverage": resume.jd_skill_coverage,
        "tailoring_confidence": confidence_label(
            resume.similarity_to_master, resume.jd_skill_coverage),
    }


@app.get("/admin/pdf/{job_id}", dependencies=[Depends(require_login)])
def admin_pdf(job_id: int, db: Session = Depends(get_db)):
    resume = (
        db.query(Resume).filter(Resume.job_id == job_id)
        .order_by(Resume.created_at.desc()).first()
    )
    if not resume or not resume.pdf_path:
        raise HTTPException(404, "no PDF for this job")
    return FileResponse(resume.pdf_path, media_type="application/pdf",
                        filename=f"resume_{job_id}.pdf")


@app.get("/admin/jobs", dependencies=[Depends(require_login)])
def list_jobs(db: Session = Depends(get_db), limit: int = 50):
    rows = db.query(Job).order_by(Job.date_scraped.desc()).limit(limit).all()
    return [
        {"id": j.id, "title": j.title, "company": j.company, "location": j.location,
         "salary": j.salary, "easy_apply": j.easy_apply, "score": j.score,
         "status": j.status,
         "date_scraped": j.date_scraped.isoformat() if j.date_scraped else None}
        for j in rows
    ]


# ---------------- Auth ----------------

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login_submit(request: Request, password: str = Form(...)):
    if not check_password(password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Wrong password."},
            status_code=401,
        )
    resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        COOKIE_NAME, make_cookie_value(),
        httponly=True, samesite="lax", secure=False, path="/",
    )
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


# ---------------- Dashboard helpers ----------------

ACTIVE_STATUSES = {"ready", "review_needed", "scored", "tailoring"}


def _score_class(score: float | None) -> str:
    if score is None:
        return "grey"
    if score >= 8:
        return "green"
    if score >= 6:
        return "yellow"
    return "grey"


def _has_pdf(db: Session, job_id: int) -> bool:
    resume = (
        db.query(Resume.pdf_path).filter(Resume.job_id == job_id)
        .order_by(Resume.created_at.desc()).first()
    )
    return bool(resume and resume[0])


def _attach_pdf_flag(db: Session, jobs: list[Job]) -> list[dict]:
    """Convert ORM rows to dicts the template can use, adding has_pdf."""
    if not jobs:
        return []
    job_ids = [j.id for j in jobs]
    latest_ids = (
        db.query(Resume.job_id, func.max(Resume.id).label("max_id"))
        .filter(Resume.job_id.in_(job_ids))
        .group_by(Resume.job_id)
        .subquery()
    )
    latest_resumes = {
        job_id: (bool(pp), sim, cov) for (job_id, pp, sim, cov) in
        db.query(Resume.job_id, Resume.pdf_path,
                 Resume.similarity_to_master, Resume.jd_skill_coverage)
        .join(latest_ids, Resume.id == latest_ids.c.max_id)
        .all()
    }
    out = []
    for j in jobs:
        has_pdf, sim, cov = latest_resumes.get(j.id, (False, None, None))
        out.append({
            "id": j.id, "title": j.title, "company": j.company,
            "location": j.location, "salary": j.salary, "remote_flag": j.remote_flag,
            "score": j.score, "status": j.status, "apply_url": j.apply_url,
            "date_scraped": j.date_scraped, "date_applied": j.date_applied,
            "has_pdf": has_pdf,
            # Flaw 2 tailoring tag: ok / review / unchanged / None (no resume yet)
            "confidence": confidence_label(sim, cov) if has_pdf else None,
        })
    return out


def _needs_review_count(db: Session) -> int:
    """Active jobs whose latest resume tripped a Flaw 2 tailoring flag."""
    active_ids = [row[0] for row in
                  db.query(Job.id).filter(Job.status.in_(ACTIVE_STATUSES)).all()]
    if not active_ids:
        return 0
    latest_ids = (
        db.query(Resume.job_id, func.max(Resume.id).label("max_id"))
        .filter(Resume.job_id.in_(active_ids))
        .group_by(Resume.job_id).subquery()
    )
    rows = (
        db.query(Resume.similarity_to_master, Resume.jd_skill_coverage)
        .join(latest_ids, Resume.id == latest_ids.c.max_id).all()
    )
    return sum(1 for (sim, cov) in rows
               if confidence_label(sim, cov) in ("unchanged", "review"))


def _counts(db: Session) -> dict:
    active = db.query(Job).filter(Job.status.in_(ACTIVE_STATUSES)).count()
    archive = db.query(Job).filter(Job.status == "applied").count()
    filtered = db.query(Job).filter(Job.status == "filtered_out").count()
    return {"active": active, "archive": archive, "filtered": filtered,
            "needs_review": _needs_review_count(db)}


# ---------------- Dashboard pages ----------------

@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def dashboard(request: Request, db: Session = Depends(get_db),
              min_score: int = 0, status: str = "", q: str = "", review: int = 0):
    query = db.query(Job).filter(Job.status.in_(ACTIVE_STATUSES))
    if min_score:
        query = query.filter(Job.score >= min_score)
    if status:
        query = query.filter(Job.status == status)
    if q:
        like = f"%{q.strip()}%"
        from sqlalchemy import or_
        query = query.filter(or_(
            Job.title.ilike(like),
            Job.company.ilike(like),
            Job.location.ilike(like),
        ))
    jobs = query.order_by(Job.date_scraped.desc(), Job.score.desc().nullslast()).all()

    rows = _attach_pdf_flag(db, jobs)

    # Flaw 2 review queue: show only resumes flagged by the tailoring checks.
    if review:
        rows = [r for r in rows if r["confidence"] in ("unchanged", "review")]

    # Group by date scraped (newest first, already ordered)
    grouped = OrderedDict()
    for r in rows:
        key = r["date_scraped"].strftime("%Y-%m-%d") if r["date_scraped"] else "unknown"
        grouped.setdefault(key, []).append(r)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "grouped": grouped.items(),
        "counts": _counts(db),
        "filters": {"min_score": min_score, "status": status, "q": q, "review": review},
        "score_class": _score_class,
    })


@app.get("/archive", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def archive_view(request: Request, db: Session = Depends(get_db)):
    jobs = (
        db.query(Job).filter(Job.status == "applied")
        .order_by(Job.date_applied.desc().nullslast(), Job.id.desc()).all()
    )
    rows = _attach_pdf_flag(db, jobs)
    return templates.TemplateResponse("archive.html", {
        "request": request,
        "jobs": rows,
        "counts": _counts(db),
        "score_class": _score_class,
    })


@app.get("/filtered", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def filtered_view(request: Request, db: Session = Depends(get_db)):
    jobs = (
        db.query(Job).filter(Job.status == "filtered_out")
        .order_by(Job.date_scraped.desc()).all()
    )
    rows = []
    for j in jobs:
        rows.append({
            "id": j.id, "title": j.title, "company": j.company,
            "location": j.location, "score": j.score, "apply_url": j.apply_url,
            "date_scraped": j.date_scraped, "top_gaps": j.top_gaps or [],
        })
    return templates.TemplateResponse("filtered.html", {
        "request": request,
        "jobs": rows,
        "counts": _counts(db),
        "score_class": _score_class,
    })


# ---------------- Job actions ----------------

@app.post("/jobs/{job_id}/applied", dependencies=[Depends(require_login)])
def mark_applied(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    job.status = "applied"
    job.date_applied = datetime.utcnow()
    db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/jobs/{job_id}/unapply", dependencies=[Depends(require_login)])
def unapply(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    # Restore prior status. If we have a Resume with a PDF, "ready"; else "scored".
    has_resume = db.query(Resume).filter(Resume.job_id == job.id).first() is not None
    job.status = "ready" if has_resume else "scored"
    job.date_applied = None
    db.commit()
    return RedirectResponse(url="/archive", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/jobs/{job_id}/calendar", dependencies=[Depends(require_login)])
def add_calendar_event(
    job_id: int,
    event_type: str = Form(...),
    event_date: str = Form(...),     # YYYY-MM-DD
    event_time: str = Form(...),     # HH:MM
    notes: str | None = Form(None),
    next_url: str = Form(default="/archive"),
    db: Session = Depends(get_db),
):
    from services.calendar_service import create_event  # lazy import (Google libs heavy)
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    try:
        d = datetime.strptime(event_date, "%Y-%m-%d").date()
        h, m = (int(x) for x in event_time.split(":"))
        event_dt = datetime.combine(d, dtime(h, m, tzinfo=IST))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"bad date/time: {e}")

    create_event(scheduler, job, event_type, event_dt, notes=notes)
    return RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)
