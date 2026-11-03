"""Today's numbers in one place — feeds the iPhone widget (/api/summary) and the daily
09:30 calendar event. Spec: .claude/specs/dashboard/phone-widget.md"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from database.models import CalendarEvent, Job, JobUserState
import services.alerts as alerts_svc

IST = ZoneInfo("Asia/Kolkata")
OWNER_USER_ID = int(os.getenv("SUMMARY_USER_ID", "1"))
APPLIER_DIR = Path(os.getenv("APPLIER_DATA_DIR", "/app/data/applier"))
SICK_KEYS = ("linkedin_spy_sick", "linkedin_cookie_expired", "linkedin_drip_crashed")


def _applier_numbers(start_local: str, end_local: str) -> dict:
    out = {"applied": 0, "applied_easy": 0, "applied_company_site": 0, "needs_you": 0,
           "failed": 0, "open_questions": 0, "last_activity": None, "paused": None}
    pause = APPLIER_DIR / "PAUSED"
    if pause.exists():
        out["paused"] = pause.read_text().strip()[:120] or "paused"
    db = APPLIER_DIR / "applier.db"
    if not db.exists():
        return out
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
    try:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='attempts'").fetchone():
            return out
        for status, detail in c.execute(
                "SELECT status, detail FROM attempts WHERE created_at >= ? AND created_at < ?",
                (start_local, end_local)):
            detail = detail or ""
            if status == "applied":
                out["applied"] += 1
                out["applied_company_site" if detail.startswith("offsite:") else "applied_easy"] += 1
            elif status == "failed":
                out["failed"] += 1
            elif detail.startswith("needs_human:"):
                out["needs_you"] += 1
        out["open_questions"] = c.execute(
            "SELECT count(*) FROM qa_bank WHERE status='UNANSWERED'").fetchone()[0]
        out["last_activity"] = c.execute("SELECT max(created_at) FROM attempts").fetchone()[0]
    finally:
        c.close()
    return out


def build_summary(db, days_ago: int = 0) -> dict:
    """days_ago=0 → today so far (widget); 1 → the whole of yesterday (morning event)."""
    now_ist = datetime.now(IST)
    start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    end_ist = start_ist + timedelta(days=1)
    # jobs.date_scraped / job_user_state.created_at are naive UTC (datetime.utcnow)
    start_utc = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_ist.astimezone(timezone.utc).replace(tzinfo=None)
    day_ago_utc = datetime.utcnow() - timedelta(hours=24)

    fetched = db.query(Job).filter(Job.date_scraped >= start_utc, Job.date_scraped < end_utc).count()
    collected_24h = db.query(Job).filter(Job.date_scraped >= day_ago_utc).count()
    scored = (db.query(JobUserState)
              .filter(JobUserState.user_id == OWNER_USER_ID, JobUserState.created_at >= start_utc,
                      JobUserState.created_at < end_utc, JobUserState.score.isnot(None)).count())
    interviews = (db.query(CalendarEvent)
                  .filter(CalendarEvent.event_time >= now_ist.replace(tzinfo=None),
                          CalendarEvent.event_time <= (now_ist + timedelta(days=7)).replace(tzinfo=None))
                  .count())

    alerts = alerts_svc.get_alerts()
    if "linkedin_spy_sick" in alerts:
        scraper = "sick"
    elif any(k in alerts for k in SICK_KEYS):
        scraper = "paused"
    elif collected_24h == 0:
        scraper = "collected 0 in 24h"
    else:
        scraper = "healthy"

    # applier timestamps are local (IST) naive ISO strings written on the Pi host
    ap = _applier_numbers(start_ist.replace(tzinfo=None).isoformat(timespec="seconds"),
                          end_ist.replace(tzinfo=None).isoformat(timespec="seconds"))
    if ap["paused"]:
        applier = f"paused: {ap['paused']}"
    elif ap["last_activity"] and datetime.fromisoformat(ap["last_activity"]) < (
            now_ist.replace(tzinfo=None) - timedelta(hours=26)):
        applier = "quiet for over a day"
    else:
        applier = "running"

    if scraper in ("sick", "paused") or ap["paused"]:
        status = "red"
    elif scraper != "healthy" or applier != "running" or ap["open_questions"]:
        status = "yellow"
    else:
        status = "green"

    line = (f"📊 Fetched {fetched} · Applied {ap['applied']} · Need you {ap['needs_you']}"
            + (f" · Interviews {interviews}" if interviews else "")
            + ("" if status == "green" else f" · ⚠️ {scraper if scraper != 'healthy' else applier}"))
    return {
        "date": start_ist.strftime("%Y-%m-%d"),
        "updated": now_ist.strftime("%H:%M"),
        "status": status,
        "line": line,
        "fetched": fetched,
        "scored": scored,
        "applied": ap["applied"],
        "applied_easy": ap["applied_easy"],
        "applied_company_site": ap["applied_company_site"],
        "needs_you": ap["needs_you"],
        "failed": ap["failed"],
        "open_questions": ap["open_questions"],
        "interviews_7d": interviews,
        "scraper": scraper,
        "applier": applier,
        "alerts": [a["message"] for a in alerts.values()][:5],
    }


def summary_text(s: dict) -> str:
    return "\n".join([
        s["line"],
        f"Date: {s['date']} (as of {s['updated']} IST)",
        f"Jobs fetched today: {s['fetched']} | scored: {s['scored']}",
        f"Applied today: {s['applied']} (Easy Apply {s['applied_easy']}, company site {s['applied_company_site']})",
        f"Need you (apply by hand): {s['needs_you']} | failed: {s['failed']} | open questions: {s['open_questions']}",
        f"Interviews in next 7 days: {s['interviews_7d']}",
        f"Scraper: {s['scraper']} | Applier: {s['applier']}",
    ] + ([f"Alerts: {'; '.join(s['alerts'])}"] if s["alerts"] else []))
