import calendar as calendar_module
import logging
import logging.handlers
import os
import secrets
from collections import Counter, OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from database.db import init_db, get_db, SessionLocal
from database.models import GroqKey, InviteToken, Job, JobUserState, Resume, User
from services.ingest import ingest_rows, load_csv
from services.auth import (
    COOKIE_NAME, hash_password, make_cookie_value, require_admin, require_login, verify_password,
)
from services.profile_import import parse_profile_export, ProfileImportError
import services.alerts as alerts_svc
from services.scraper import save_li_at, has_li_at
from services.watcher_health import watcher_status
from agents.scorer import score_job_for_user, score_pending
from agents.tailor_loop import tailor_pending, tailor_for_job
from agents.quality_check import confidence_label
from scheduler import start_scheduler, CSV_PATH

# Persistent, rotating logs — survive container rebuilds/restarts (unlike `docker
# logs`, which resets every time the container is recreated). Kept 30 days, one
# file per day, written to the bind-mounted data/ dir so they're SSH-readable.
# /app only exists in the container; local Mac dev (see CLAUDE.md's local-dev
# prelude) falls back to ./data/logs relative to the backend/ cwd.
_LOG_DIR = Path("/app/data/logs")
try:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    _LOG_DIR = Path("data/logs")
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
        stuck = (
            db.query(JobUserState).filter(JobUserState.status == "tailoring")
            .update({"status": "scored"})
        )
        db.commit()
        if stuck:
            log.warning("Reset %d job/user state(s) stuck at 'tailoring' from a previous crashed run", stuck)
    finally:
        db.close()
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


@app.get("/api/summary")
def api_summary(request: Request, db: Session = Depends(get_db)):
    """Today's numbers for the iPhone widget. Needs ?key=<WIDGET_KEY> (set in .env).
    Docker's port proxy hides the caller IP (everything arrives as the bridge gateway),
    so access is by key, not by Tailscale address."""
    from services.daily_summary import build_summary
    expected = os.getenv("WIDGET_KEY", "")
    if not expected or not secrets.compare_digest(request.query_params.get("key", ""), expected):
        raise HTTPException(status_code=403, detail="key required")
    return build_summary(db)


@app.post("/webhook/jobs")
def webhook_jobs(request: Request, payload: dict, db: Session = Depends(get_db)):
    secret = os.getenv("WEBHOOK_SECRET", "")
    if secret and request.headers.get("Authorization") != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    rows = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="Expected JSON {'jobs': [...]}")
    return ingest_rows(db, rows)


# ---------------- Admin operational triggers ----------------
# Shared/global actions (scraping, cross-user scoring/tailoring passes) — gated to
# admins, not wired into the regular dashboard UI. See .claude/specs/multi-user.

@app.post("/admin/trigger-scrape")
def trigger_scrape(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return load_csv(db, CSV_PATH)


@app.post("/admin/score-pending")
def admin_score_pending(limit: int | None = None, current_user: User = Depends(require_admin),
                         db: Session = Depends(get_db)):
    return score_pending(db, limit=limit)


@app.post("/admin/score-one/{job_id}")
def admin_score_one(job_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    results = {}
    for u in db.query(User).all():
        results[u.username] = score_job_for_user(db, job, u)
    return results


@app.post("/admin/tailor-pending")
def admin_tailor_pending(limit: int | None = None, current_user: User = Depends(require_admin),
                          db: Session = Depends(get_db)):
    return tailor_pending(db, limit=limit)


@app.post("/admin/tailor/{job_id}")
def admin_tailor_one(job_id: int, user_id: int, current_user: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    target_user = db.get(User, user_id)
    if not job or not target_user:
        raise HTTPException(404, "job or user not found")
    if not job.raw_description:
        raise HTTPException(400, "job has no description")
    resume = tailor_for_job(db, job, target_user)
    state = (
        db.query(JobUserState)
        .filter(JobUserState.job_id == job.id, JobUserState.user_id == target_user.id).first()
    )
    return {
        "job_id": job.id, "user": target_user.username, "status": state.status if state else None,
        "iterations": resume.iteration_count,
        "verdict": resume.critic_verdict, "pdf_path": resume.pdf_path,
        "unfixable": resume.unfixable_items,
        "similarity_to_master": resume.similarity_to_master,
        "jd_skill_coverage": resume.jd_skill_coverage,
        "tailoring_confidence": confidence_label(
            resume.similarity_to_master, resume.jd_skill_coverage),
    }


@app.get("/admin/pdf/{job_id}")
def user_pdf(job_id: int, current_user: User = Depends(require_login), db: Session = Depends(get_db)):
    """Any logged-in user can fetch THEIR OWN latest resume for a job — scoped by
    user_id so one user can never pull another's tailored PDF by guessing job ids."""
    resume = (
        db.query(Resume)
        .filter(Resume.job_id == job_id, Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc()).first()
    )
    if not resume or not resume.pdf_path:
        raise HTTPException(404, "no PDF for this job")
    return FileResponse(resume.pdf_path, media_type="application/pdf",
                        filename=f"resume_{job_id}.pdf")


@app.get("/admin/jobs")
def list_jobs(current_user: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = 50):
    rows = db.query(Job).order_by(Job.date_scraped.desc()).limit(limit).all()
    return [
        {"id": j.id, "title": j.title, "company": j.company, "location": j.location,
         "salary": j.salary, "easy_apply": j.easy_apply,
         "date_scraped": j.date_scraped.isoformat() if j.date_scraped else None}
        for j in rows
    ]


# ---------------- LinkedIn cookie (shared scrape infra — admin only) ----------------

@app.get("/admin/linkedin-cookie", response_class=HTMLResponse)
def linkedin_cookie_form(request: Request, saved: int = 0, current_user: User = Depends(require_admin)):
    return templates.TemplateResponse("linkedin_cookie.html", {
        "request": request, "has_cookie": has_li_at(),
        "saved": bool(saved), "error": None, "current_user": current_user,
    })


@app.post("/admin/linkedin-cookie")
def linkedin_cookie_save(request: Request, li_at: str = Form(...),
                          current_user: User = Depends(require_admin)):
    value = (li_at or "").strip()
    if len(value) < 20:
        return templates.TemplateResponse("linkedin_cookie.html", {
            "request": request, "has_cookie": has_li_at(), "saved": False,
            "current_user": current_user,
            "error": "That doesn't look like a valid li_at value — paste the full "
                     "string from the Cookie Value pane (it starts with AQED…).",
        }, status_code=400)
    save_li_at(value)
    alerts_svc.clear_alert("linkedin_cookie_expired")
    return RedirectResponse(url="/admin/linkedin-cookie?saved=1",
                            status_code=status.HTTP_303_SEE_OTHER)


# ---------------- Auth ----------------

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...),
                  db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Wrong username or password."},
            status_code=401,
        )
    resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        COOKIE_NAME, make_cookie_value(user.id),
        httponly=True, samesite="lax", secure=False, path="/",
    )
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


# ---------------- Signup (invite-token only) ----------------

@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request, token: str = "", db: Session = Depends(get_db)):
    invite = db.query(InviteToken).filter(InviteToken.token == token).first() if token else None
    if not invite or invite.used_at is not None:
        # Don't reveal whether the route exists for an invalid/missing token.
        raise HTTPException(404)
    return templates.TemplateResponse("signup.html", {"request": request, "token": token, "error": None})


@app.post("/signup")
async def signup_submit(
    request: Request,
    token: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    profile_export: str = Form(...),
    resume_tex: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    invite = db.query(InviteToken).filter(InviteToken.token == token).first()
    if not invite or invite.used_at is not None:
        raise HTTPException(404)

    def err(message: str):
        return templates.TemplateResponse(
            "signup.html", {"request": request, "token": token, "error": message},
            status_code=400,
        )

    username = username.strip()
    if not username or " " in username:
        return err("Username must be non-empty with no spaces.")
    if db.query(User.id).filter(User.username == username).first():
        return err("That username is already taken.")
    if len(password) < 8:
        return err("Password must be at least 8 characters.")
    if password != password_confirm:
        return err("Passwords don't match.")

    try:
        parsed = parse_profile_export(profile_export)
    except ProfileImportError as e:
        return err(f"Profile export problem: {e}")

    resume_bytes = await resume_tex.read()
    try:
        resume_text = resume_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return err("Resume file must be a plain-text .tex file (UTF-8).")
    if not resume_text.strip():
        return err("Resume file is empty.")

    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=False,
        telegram_enabled=parsed["telegram_enabled"],
        telegram_bot_token=parsed["telegram_bot_token"],
        telegram_chat_id=parsed["telegram_chat_id"],
        candidate_profile=parsed["candidate_profile"],
        locked_skill_set=parsed["locked_skill_set"],
        project_library=parsed["project_library"],
        role_type_prefs=parsed["role_type_prefs"],
        location_prefs=parsed["location_prefs"],
        salary_pref=parsed["salary_pref"],
        master_resume_tex=resume_text,
    )
    db.add(user)
    db.flush()  # need user.id before inserting groq keys
    for i, key in enumerate(parsed["groq_keys"]):
        db.add(GroqKey(user_id=user.id, key=key, label=f"key {i + 1}"))
    invite.used_by_user_id = user.id
    invite.used_at = datetime.utcnow()
    db.commit()

    resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        COOKIE_NAME, make_cookie_value(user.id),
        httponly=True, samesite="lax", secure=False, path="/",
    )
    return resp


# ---------------- Admin dashboard ----------------

def _admin_redirect(msg: str = "", level: str = "ok") -> RedirectResponse:
    url = "/admin"
    if msg:
        url += f"?msg={quote(msg)}&level={level}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin", response_class=HTMLResponse)
def admin_view(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db),
               msg: str = "", level: str = "ok"):
    users = db.query(User).order_by(User.id).all()
    rows = []
    for u in users:
        keys = db.query(GroqKey).filter(GroqKey.user_id == u.id).all()
        state_counts = dict(
            db.query(JobUserState.status, func.count(JobUserState.id))
            .filter(JobUserState.user_id == u.id)
            .group_by(JobUserState.status).all()
        )
        last_resume_row = (
            db.query(Resume.created_at).filter(Resume.user_id == u.id)
            .order_by(Resume.created_at.desc()).first()
        )
        rows.append({
            "id": u.id, "username": u.username, "is_admin": u.is_admin,
            "created_at": u.created_at, "telegram_enabled": u.telegram_enabled,
            "groq_key_count": len(keys),
            "groq_keys_active": sum(1 for k in keys if k.is_active),
            "scored": sum(v for k, v in state_counts.items() if k not in ("filtered_out", "rejected")),
            "tailored": state_counts.get("ready", 0) + state_counts.get("review_needed", 0),
            "applied": state_counts.get("applied", 0),
            "last_activity": last_resume_row[0] if last_resume_row else None,
        })
    invites = db.query(InviteToken).order_by(InviteToken.created_at.desc()).all()
    alerts = alerts_svc.get_alerts()
    total_jobs = db.query(Job).count()
    return templates.TemplateResponse("admin.html", {
        "request": request, "current_user": current_user, "users": rows, "invites": invites,
        "alerts": alerts, "sources": _sources_status(), "total_jobs": total_jobs,
        "admin_count": sum(1 for u in users if u.is_admin),
        "msg": msg, "level": level if level in ("ok", "warn", "err") else "ok",
    })


@app.post("/admin/invite")
def admin_create_invite(label: str = Form(""), current_user: User = Depends(require_admin),
                         db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(24)
    db.add(InviteToken(token=token, label=label.strip() or None, created_by_user_id=current_user.id))
    db.commit()
    return _admin_redirect(f"Invite link created for {label.strip() or 'unlabelled'}.")


@app.post("/admin/invite/{invite_id}/delete")
def admin_delete_invite(invite_id: int, current_user: User = Depends(require_admin),
                         db: Session = Depends(get_db)):
    invite = db.get(InviteToken, invite_id)
    if invite:
        db.delete(invite)
        db.commit()
    return _admin_redirect("Invite link deleted.")


@app.post("/admin/users/{user_id}/delete")
def admin_delete_user(user_id: int, current_user: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    if user_id == current_user.id:
        return _admin_redirect("You can't remove your own account.", "err")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404)
    # Cascades to their groq_keys, job_user_state rows, and resumes (ORM cascade).
    # Shared Job rows are untouched — they belong to everyone.
    db.delete(target)
    db.commit()
    return _admin_redirect(f"Removed user {target.username} and all their data.", "warn")


@app.post("/admin/alerts/{key}/clear")
def admin_clear_alert(key: str, current_user: User = Depends(require_admin)):
    alerts_svc.clear_alert(key)
    return _admin_redirect(f"Cleared alert: {key}.")


# Quick actions — same operations as the JSON API routes above, but redirect back
# to /admin with a one-line result so they can be driven from the dashboard buttons.

@app.post("/admin/run/scrape")
def admin_run_scrape(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = load_csv(db, CSV_PATH)
    return _admin_redirect(f"Scrape done: {r.get('inserted', 0)} new, {r.get('skipped', 0)} skipped.")


@app.post("/admin/run/score")
def admin_run_score(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = score_pending(db)
    level = "warn" if r.get("errors") else "ok"
    return _admin_redirect(
        f"Scoring done: {r.get('scored', 0)} scored, {r.get('filtered_out', 0)} filtered, "
        f"{r.get('rejected', 0)} rejected, {r.get('errors', 0)} errors.", level)


@app.post("/admin/run/tailor")
def admin_run_tailor(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = tailor_pending(db)
    level = "warn" if r.get("errors") else "ok"
    return _admin_redirect(
        f"Tailoring done: {r.get('ready', 0)} ready, {r.get('review_needed', 0)} need review, "
        f"{r.get('errors', 0)} errors.", level)


# ---------------- Dashboard helpers (all scoped to current_user) ----------------

ACTIVE_STATUSES = {"ready", "review_needed", "scored", "tailoring"}


def _score_class(score: float | None) -> str:
    if score is None:
        return "grey"
    if score >= 8:
        return "green"
    if score >= 6:
        return "yellow"
    return "grey"


def _attach_pdf_flag(db: Session, pairs: list[tuple[JobUserState, Job]], user_id: int) -> list[dict]:
    """Convert (JobUserState, Job) pairs to dicts the templates use, adding has_pdf.
    Resume lookup is scoped to user_id — Resume now has one row per (job, user)."""
    if not pairs:
        return []
    job_ids = [job.id for _, job in pairs]
    latest_ids = (
        db.query(Resume.job_id, func.max(Resume.id).label("max_id"))
        .filter(Resume.job_id.in_(job_ids), Resume.user_id == user_id)
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
    for state, job in pairs:
        has_pdf, sim, cov = latest_resumes.get(job.id, (False, None, None))
        out.append({
            "id": job.id, "title": job.title, "company": job.company,
            "location": job.location, "salary": job.salary, "remote_flag": job.remote_flag,
            "score": state.score, "status": state.status, "apply_url": job.apply_url,
            "date_scraped": job.date_scraped, "date_applied": state.date_applied,
            "has_pdf": has_pdf,
            "confidence": confidence_label(sim, cov) if has_pdf else None,
            "top_matches": state.top_matches or [],
            "top_gaps": state.top_gaps or [],
        })
    return out


def _sources_status() -> list[dict]:
    """Per-source cookie health for the dashboard 'Sources' strip — shared scrape
    infra, same for every user."""
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


def _needs_review_count(db: Session, user_id: int) -> int:
    active_ids = [
        row[0] for row in
        db.query(JobUserState.job_id)
        .filter(JobUserState.user_id == user_id, JobUserState.status.in_(ACTIVE_STATUSES)).all()
    ]
    if not active_ids:
        return 0
    latest_ids = (
        db.query(Resume.job_id, func.max(Resume.id).label("max_id"))
        .filter(Resume.job_id.in_(active_ids), Resume.user_id == user_id)
        .group_by(Resume.job_id).subquery()
    )
    rows = (
        db.query(Resume.similarity_to_master, Resume.jd_skill_coverage)
        .join(latest_ids, Resume.id == latest_ids.c.max_id).all()
    )
    return sum(1 for (sim, cov) in rows
               if confidence_label(sim, cov) in ("unchanged", "review"))


def _counts(db: Session, user_id: int) -> dict:
    base = db.query(JobUserState).filter(JobUserState.user_id == user_id)
    active = base.filter(JobUserState.status.in_(ACTIVE_STATUSES)).count()
    archive = base.filter(JobUserState.status == "applied").count()
    filtered = base.filter(JobUserState.status == "filtered_out").count()
    # Collected but not yet scored for THIS user — visible so a scoring backlog
    # never looks like "missing jobs".
    scored_job_ids = db.query(JobUserState.job_id).filter(JobUserState.user_id == user_id)
    pending = db.query(Job).filter(~Job.id.in_(scored_job_ids)).count()
    return {"active": active, "archive": archive, "filtered": filtered,
            "pending": pending, "needs_review": _needs_review_count(db, user_id)}


# ---------------- Dashboard pages ----------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, current_user: User = Depends(require_login), db: Session = Depends(get_db),
         year: int | None = None, month: int | None = None):
    """Calendar home page — how many jobs were fetched each day, by month. Scrape
    activity is shared (same job pool for everyone); the counts strip is per-user."""
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
        "request": request, "current_user": current_user,
        "counts": _counts(db, current_user.id),
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


@app.get("/jobs", response_class=HTMLResponse)
def dashboard(request: Request, current_user: User = Depends(require_login), db: Session = Depends(get_db),
              min_score: int = 0, status: str = "", q: str = "", review: int = 0, date: str = ""):
    query = (
        db.query(JobUserState, Job)
        .join(Job, JobUserState.job_id == Job.id)
        .filter(JobUserState.user_id == current_user.id, JobUserState.status.in_(ACTIVE_STATUSES))
    )
    if date:
        try:
            day_start = datetime.strptime(date, "%Y-%m-%d")
            query = query.filter(Job.date_scraped >= day_start,
                                  Job.date_scraped < day_start + timedelta(days=1))
        except ValueError:
            date = ""
    if min_score:
        query = query.filter(JobUserState.score >= min_score)
    if status:
        query = query.filter(JobUserState.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            Job.title.ilike(like), Job.company.ilike(like), Job.location.ilike(like),
        ))
    pairs = query.order_by(Job.date_scraped.desc(), JobUserState.score.desc().nullslast()).all()

    rows = _attach_pdf_flag(db, pairs, current_user.id)

    # Flaw 2 review queue: show only resumes flagged by the tailoring checks.
    if review:
        rows = [r for r in rows if r["confidence"] in ("unchanged", "review")]

    grouped = OrderedDict()
    for r in rows:
        key = r["date_scraped"].strftime("%Y-%m-%d") if r["date_scraped"] else "unknown"
        grouped.setdefault(key, []).append(r)

    return templates.TemplateResponse("jobs.html", {
        "request": request, "current_user": current_user,
        "grouped": grouped.items(),
        "counts": _counts(db, current_user.id),
        "sources": _sources_status(),
        "filters": {"min_score": min_score, "status": status, "q": q, "review": review, "date": date},
        "score_class": _score_class,
    })


@app.get("/insights", response_class=HTMLResponse)
def insights_view(request: Request, current_user: User = Depends(require_login), db: Session = Depends(get_db),
                   days: int = 180):
    """Market-insights charts aggregated from THIS user's own scoring data — the
    same job can score differently for different users, so this is per-user, not
    global. See .claude/specs/market-insights/approach.md."""
    q = (
        db.query(JobUserState, Job)
        .join(Job, JobUserState.job_id == Job.id)
        .filter(JobUserState.user_id == current_user.id)
    )
    if days > 0:
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(Job.date_scraped >= since)
    pairs = q.all()
    total_jobs = len(pairs)

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
    for state, j in pairs:
        for s in (state.top_matches or []):
            s = (s or "").strip()
            if _is_skill(s):
                matches_counter[s] += 1
                all_skills_counter[s] += 1
        for s in (state.top_gaps or []):
            s = (s or "").strip()
            if _is_skill(s):
                gaps_counter[s] += 1
                all_skills_counter[s] += 1

    top_skills = all_skills_counter.most_common(20)
    top_gaps = gaps_counter.most_common(20)

    # Skills-over-time: weekly buckets for the 5 most common skills overall.
    top5_names = [name for name, _ in all_skills_counter.most_common(5)]
    weekly: "OrderedDict[str, dict[str, int]]" = OrderedDict()
    for state, j in sorted((p for p in pairs if p[1].date_scraped), key=lambda p: p[1].date_scraped):
        week_key = j.date_scraped.strftime("%Y-W%W")
        bucket = weekly.setdefault(week_key, {name: 0 for name in top5_names})
        for s in list(state.top_matches or []) + list(state.top_gaps or []):
            s = (s or "").strip()
            if s in bucket:
                bucket[s] += 1
    week_labels = list(weekly.keys())
    weekly_series = {name: [weekly[w][name] for w in week_labels] for name in top5_names}

    # domain_flag is meant to be one of a handful of short categories, but the
    # scorer occasionally writes a full sentence instead — bucket anything
    # off-vocabulary as "other" so the chart stays readable.
    CANONICAL_DOMAINS = {"in-scope", "out-of-scope", "borderline", "unclassified"}
    domain_counter: Counter = Counter()
    for state, j in pairs:
        flag = (state.domain_flag or "unclassified").strip()
        domain_counter[flag if flag in CANONICAL_DOMAINS else "other"] += 1

    company_counter = Counter(j.company for _, j in pairs if j.company)
    location_counter = Counter((j.location or "unspecified").strip() for _, j in pairs)

    score_buckets = [0] * 11
    for state, j in pairs:
        if state.score is not None:
            score_buckets[max(0, min(10, round(state.score)))] += 1

    domain_items = domain_counter.most_common()
    top_companies = company_counter.most_common(15)
    top_locations = location_counter.most_common(15)
    chart_colors = ["#7c5cff", "#3ddc97", "#ffb86b", "#5db8ff", "#ff5d6c"]

    return templates.TemplateResponse("insights.html", {
        "request": request, "current_user": current_user,
        "counts": _counts(db, current_user.id),
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


@app.get("/archive", response_class=HTMLResponse)
def archive_view(request: Request, current_user: User = Depends(require_login), db: Session = Depends(get_db)):
    pairs = (
        db.query(JobUserState, Job)
        .join(Job, JobUserState.job_id == Job.id)
        .filter(JobUserState.user_id == current_user.id, JobUserState.status == "applied")
        .order_by(JobUserState.date_applied.desc().nullslast(), Job.id.desc()).all()
    )
    rows = _attach_pdf_flag(db, pairs, current_user.id)
    return templates.TemplateResponse("archive.html", {
        "request": request, "current_user": current_user,
        "jobs": rows,
        "counts": _counts(db, current_user.id),
        "score_class": _score_class,
    })


@app.get("/filtered", response_class=HTMLResponse)
def filtered_view(request: Request, current_user: User = Depends(require_login), db: Session = Depends(get_db)):
    pairs = (
        db.query(JobUserState, Job)
        .join(Job, JobUserState.job_id == Job.id)
        .filter(JobUserState.user_id == current_user.id, JobUserState.status == "filtered_out")
        .order_by(Job.date_scraped.desc()).all()
    )
    rows = []
    for state, j in pairs:
        rows.append({
            "id": j.id, "title": j.title, "company": j.company,
            "location": j.location, "score": state.score, "apply_url": j.apply_url,
            "date_scraped": j.date_scraped, "top_gaps": state.top_gaps or [],
        })
    return templates.TemplateResponse("filtered.html", {
        "request": request, "current_user": current_user,
        "jobs": rows,
        "counts": _counts(db, current_user.id),
        "score_class": _score_class,
    })


# ---------------- Job actions (scoped to current_user's own JobUserState) ----------------

@app.post("/jobs/{job_id}/applied")
def mark_applied(job_id: int, current_user: User = Depends(require_login), db: Session = Depends(get_db)):
    state = (
        db.query(JobUserState)
        .filter(JobUserState.job_id == job_id, JobUserState.user_id == current_user.id).first()
    )
    if not state:
        raise HTTPException(404)
    state.status = "applied"
    state.date_applied = datetime.utcnow()
    db.commit()
    return RedirectResponse(url="/jobs", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/jobs/{job_id}/unapply")
def unapply(job_id: int, current_user: User = Depends(require_login), db: Session = Depends(get_db)):
    state = (
        db.query(JobUserState)
        .filter(JobUserState.job_id == job_id, JobUserState.user_id == current_user.id).first()
    )
    if not state:
        raise HTTPException(404)
    has_resume = (
        db.query(Resume)
        .filter(Resume.job_id == job_id, Resume.user_id == current_user.id).first() is not None
    )
    state.status = "ready" if has_resume else "scored"
    state.date_applied = None
    db.commit()
    return RedirectResponse(url="/archive", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/jobs/{job_id}/calendar")
def add_calendar_event(
    job_id: int,
    event_type: str = Form(...),
    event_date: str = Form(...),     # YYYY-MM-DD
    event_time: str = Form(...),     # HH:MM
    notes: str | None = Form(None),
    next_url: str = Form(default="/archive"),
    # Google Calendar uses ONE shared OAuth token (token.json) — same single-account
    # limitation as the Gmail watcher (see .claude/specs/multi-user/approach.md,
    # "explicitly out of scope"). Gating to admin only so a non-admin user can't
    # accidentally create an event on the admin's real personal calendar.
    current_user: User = Depends(require_admin),
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
