import calendar as calendar_module
import logging
import logging.handlers
import os
from collections import Counter, OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, time as dtime
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
from services.scraper import save_li_at, has_li_at
from services.watcher_health import watcher_status
from agents.scorer import score_pending, score_job
from agents.tailor_loop import tailor_pending, tailor_for_job
from agents.quality_check import confidence_label
from scheduler import start_scheduler, CSV_PATH

# Persistent, rotating logs — survive container rebuilds/restarts (unlike `docker
# logs`, which resets every time the container is recreated). Kept 30 days, one
# file per day, written to the bind-mounted data/ dir so they're SSH-readable.
_LOG_DIR = Path("/app/data/logs")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_file_handler = logging.handlers.TimedRotatingFileHandler(
    _LOG_DIR / "backend.log", when="midnight", backupCount=30, utc=True,
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), _file_handler],
)
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


# ---------------- LinkedIn cookie ----------------

@app.get("/admin/linkedin-cookie", response_class=HTMLResponse,
         dependencies=[Depends(require_login)])
def linkedin_cookie_form(request: Request, saved: int = 0):
    return templates.TemplateResponse("linkedin_cookie.html", {
        "request": request, "has_cookie": has_li_at(),
        "saved": bool(saved), "error": None,
    })


@app.post("/admin/linkedin-cookie", dependencies=[Depends(require_login)])
def linkedin_cookie_save(request: Request, li_at: str = Form(...)):
    value = (li_at or "").strip()
    if len(value) < 20:
        return templates.TemplateResponse("linkedin_cookie.html", {
            "request": request, "has_cookie": has_li_at(), "saved": False,
            "error": "That doesn't look like a valid li_at value — paste the full "
                     "string from the Cookie Value pane (it starts with AQED…).",
        }, status_code=400)
    save_li_at(value)
    # Clear the paused banner now; if the value is bad, the drip loop re-flags it.
    alerts_svc.clear_alert("linkedin_cookie_expired")
    return RedirectResponse(url="/admin/linkedin-cookie?saved=1",
                            status_code=status.HTTP_303_SEE_OTHER)


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
            # Score transparency — shown in the per-row "why?" dropdown
            "top_matches": j.top_matches or [],
            "top_gaps": j.top_gaps or [],
        })
    return out


def _sources_status() -> list[dict]:
    """Per-source cookie health for the dashboard 'Sources' strip. Generalises to
    future sources — each gets a row with its own status light + cookie page."""
    alerts = alerts_svc.get_alerts()
    if not has_li_at():
        state, label = "missing", "No cookie"
    elif "linkedin_cookie_expired" in alerts:
        state, label = "expired", "Expired"
    else:
        state, label = "active", "Active"
    w = watcher_status()
    return [
        {"name": "LinkedIn", "state": state, "label": label,
         "cookie_url": "/admin/linkedin-cookie"},
        {"name": "Gmail watcher",
         "state": "active" if w["state"] == "running" else "down",
         "label": w["label"], "cookie_url": None},
    ]


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
    # Collected but not yet scored — visible so a Groq backlog never looks like "missing jobs".
    pending = db.query(Job).filter(Job.status == "scraped").count()
    return {"active": active, "archive": archive, "filtered": filtered,
            "pending": pending, "needs_review": _needs_review_count(db)}


# ---------------- Dashboard pages ----------------

@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def home(request: Request, db: Session = Depends(get_db),
         year: int | None = None, month: int | None = None):
    """Calendar home page — how many jobs were fetched each day, by month."""
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    month = max(1, min(12, month))

    month_start = datetime(year, month, 1)
    next_month_start = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    rows = (
        db.query(Job.date_scraped)
        .filter(Job.date_scraped >= month_start, Job.date_scraped < next_month_start)
        .all()
    )
    counts_by_day: dict[int, int] = {}
    for (dt,) in rows:
        if dt:
            counts_by_day[dt.day] = counts_by_day.get(dt.day, 0) + 1

    weeks = calendar_module.Calendar(firstweekday=0).monthdayscalendar(year, month)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    return templates.TemplateResponse("home.html", {
        "request": request,
        "counts": _counts(db),
        "year": year, "month": month,
        "month_name": month_start.strftime("%B %Y"),
        "weeks": weeks,
        "counts_by_day": counts_by_day,
        "max_day_count": max(counts_by_day.values()) if counts_by_day else 0,
        "total_month": sum(counts_by_day.values()),
        "today": now.day if (now.year == year and now.month == month) else None,
        "prev_year": prev_year, "prev_month": prev_month,
        "next_year": next_year, "next_month": next_month,
    })


@app.get("/jobs", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def dashboard(request: Request, db: Session = Depends(get_db),
              min_score: int = 0, status: str = "", q: str = "", review: int = 0,
              date: str = ""):
    query = db.query(Job).filter(Job.status.in_(ACTIVE_STATUSES))
    if date:
        try:
            day_start = datetime.strptime(date, "%Y-%m-%d")
            query = query.filter(Job.date_scraped >= day_start,
                                  Job.date_scraped < day_start + timedelta(days=1))
        except ValueError:
            date = ""
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

    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "grouped": grouped.items(),
        "counts": _counts(db),
        "sources": _sources_status(),
        "filters": {"min_score": min_score, "status": status, "q": q, "review": review, "date": date},
        "score_class": _score_class,
    })


@app.get("/insights", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def insights_view(request: Request, db: Session = Depends(get_db), days: int = 180):
    """Market-insights charts aggregated from data the scorer already collected.
    No extra API calls — see .claude/specs/market-insights/approach.md."""
    q = db.query(Job)
    if days > 0:
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(Job.date_scraped >= since)
    jobs = q.all()
    total_jobs = len(jobs)

    # The scorer sometimes writes a role-fit reasoning sentence into top_gaps
    # (e.g. "Role-type: applied AI at a consulting firm, not core R&D — capped")
    # instead of an actual skill. Those aren't skills — exclude them from the
    # skill charts so they don't drown out real signal. Nothing is deleted from
    # the DB; this only affects what gets plotted here.
    def _is_skill(s: str) -> bool:
        return bool(s) and not s.lower().startswith("role-type")

    matches_counter: Counter = Counter()
    gaps_counter: Counter = Counter()
    all_skills_counter: Counter = Counter()
    for j in jobs:
        for s in (j.top_matches or []):
            s = (s or "").strip()
            if _is_skill(s):
                matches_counter[s] += 1
                all_skills_counter[s] += 1
        for s in (j.top_gaps or []):
            s = (s or "").strip()
            if _is_skill(s):
                gaps_counter[s] += 1
                all_skills_counter[s] += 1

    top_skills = all_skills_counter.most_common(20)
    top_gaps = gaps_counter.most_common(20)

    # Skills-over-time: weekly buckets for the 5 most common skills overall.
    top5_names = [name for name, _ in all_skills_counter.most_common(5)]
    weekly: "OrderedDict[str, dict[str, int]]" = OrderedDict()
    for j in sorted((j for j in jobs if j.date_scraped), key=lambda j: j.date_scraped):
        week_key = j.date_scraped.strftime("%Y-W%W")
        bucket = weekly.setdefault(week_key, {name: 0 for name in top5_names})
        for s in list(j.top_matches or []) + list(j.top_gaps or []):
            s = (s or "").strip()
            if s in bucket:
                bucket[s] += 1
    week_labels = list(weekly.keys())
    weekly_series = {name: [weekly[w][name] for w in week_labels] for name in top5_names}

    # domain_flag is meant to be one of a handful of short categories, but the
    # scorer occasionally writes a full sentence instead — bucket anything
    # off-vocabulary as "other" so the chart stays readable (raw value is
    # still on the Job row, this only affects this chart's grouping).
    CANONICAL_DOMAINS = {"in-scope", "out-of-scope", "borderline", "unclassified"}
    domain_counter: Counter = Counter()
    for j in jobs:
        flag = (j.domain_flag or "unclassified").strip()
        domain_counter[flag if flag in CANONICAL_DOMAINS else "other"] += 1

    company_counter = Counter(j.company for j in jobs if j.company)
    location_counter = Counter((j.location or "unspecified").strip() for j in jobs)

    score_buckets = [0] * 11
    for j in jobs:
        if j.score is not None:
            score_buckets[max(0, min(10, round(j.score)))] += 1

    domain_items = domain_counter.most_common()
    top_companies = company_counter.most_common(15)
    top_locations = location_counter.most_common(15)
    chart_colors = ["#7c5cff", "#3ddc97", "#ffb86b", "#5db8ff", "#ff5d6c"]

    return templates.TemplateResponse("insights.html", {
        "request": request,
        "counts": _counts(db),
        "days": days,
        "total_jobs": total_jobs,
        "chart_data": {
            "skillLabels": [s for s, _ in top_skills],
            "skillValues": [c for _, c in top_skills],
            "gapLabels": [s for s, _ in top_gaps],
            "gapValues": [c for _, c in top_gaps],
            "weekLabels": week_labels,
            "weeklySeries": [
                {"label": name, "data": weekly_series[name],
                 "color": chart_colors[i % len(chart_colors)]}
                for i, name in enumerate(top5_names)
            ],
            "domainLabels": [d for d, _ in domain_items],
            "domainValues": [c for _, c in domain_items],
            "companyLabels": [c for c, _ in top_companies],
            "companyValues": [n for _, n in top_companies],
            "locationLabels": [l for l, _ in top_locations],
            "locationValues": [n for _, n in top_locations],
            "scoreBuckets": score_buckets,
        },
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
    return RedirectResponse(url="/jobs", status_code=status.HTTP_303_SEE_OTHER)


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
