import os
import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from database.db import SessionLocal, DATABASE_URL
from services.ingest import load_csv
from services.scraper import scrape_naukri, linkedin_drip_loop, schedule_daily_activity, has_li_at
from agents.scorer import score_pending
from agents.tailor_loop import tailor_pending, TAILOR_MAX_PER_PASS
from datetime import datetime, timedelta
from database.models import Job
from services.telegram import send as tg_send
from services.watcher_health import watcher_status
import services.alerts as alerts_svc

log = logging.getLogger(__name__)

TZ = os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata")
HOUR = int(os.getenv("SCRAPE_HOUR", "6"))
MINUTE = int(os.getenv("SCRAPE_MINUTE", "0"))
CSV_PATH = os.getenv("JOBS_CSV_PATH", "/app/dummy_jobs.csv")
# Consumer cadence: how often the score/tailor pass drains the scraped queue, and how
# many jobs it processes per pass (bounded so a Groq retry-storm can't run away).
SCORE_INTERVAL_MIN = int(os.getenv("SCORE_INTERVAL_MIN", "20"))
SCORE_BATCH = int(os.getenv("SCORE_BATCH", "10"))
# Daily heartbeat hour (IST) — end of active hours so it summarises the day (Flaws 3/6/15).
HEARTBEAT_HOUR = int(os.getenv("HEARTBEAT_HOUR", "21"))

# Module-level handle so jobs saved in the persistent (SQLAlchemy) jobstore can reach
# the running scheduler without a lambda/closure — APScheduler must pickle every job
# it persists, and lambdas/closures are not picklable. Set in start_scheduler().
_scheduler: BackgroundScheduler | None = None


def daily_scrape_job():
    """PRODUCER — 6am IST Naukri batch: scrape + ingest ONLY. Scoring/tailoring is the
    consumer's job (score_and_tailor_job), so a Groq outage never blocks scraping."""
    log.info("Daily scrape tick — running Naukri batch (ingest only)")
    db = SessionLocal()
    try:
        ingest_result = scrape_naukri(db)
        log.info("Daily ingest result: %s", ingest_result)
    finally:
        db.close()


def score_and_tailor_job():
    """CONSUMER — drains the scraped queue on an interval, independent of the scrapers.
    Groq-gated: score_pending stops the batch after repeated Groq failures and retries
    next tick, so the producers keep collecting even when the free tier is exhausted."""
    db = SessionLocal()
    try:
        score_result = score_pending(db, limit=SCORE_BATCH)
        tailor_result = tailor_pending(db, limit=TAILOR_MAX_PER_PASS)
        log.info("Score/tailor pass: score=%s tailor=%s", score_result, tailor_result)
    finally:
        db.close()


def heartbeat_job():
    """Daily health ping (Flaws 3, 6, 15). Fires from INSIDE the backend, so if the
    backend is down the message never arrives — silence itself is the alarm."""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(hours=24)
        collected = db.query(Job).filter(Job.date_scraped >= since).count()
        pending = db.query(Job).filter(Job.status == "scraped").count()
        scored = db.query(Job).filter(Job.status == "scored").count()
        ready = db.query(Job).filter(Job.status.in_(("ready", "review_needed"))).count()
    finally:
        db.close()

    li_ok = has_li_at() and "linkedin_cookie_expired" not in alerts_svc.get_alerts()
    w = watcher_status()
    alerts = alerts_svc.get_alerts()
    alert_line = "; ".join(a["message"] for a in alerts.values()) if alerts else "none"
    msg = (
        "📊 job-doot daily heartbeat\n"
        f"• Collected (24h): {collected}\n"
        f"• Awaiting scoring: {pending} | Scored: {scored} | CVs ready: {ready}\n"
        f"• LinkedIn scraper: {'🟢 active' if li_ok else '🔴 paused'}\n"
        f"• Gmail watcher: {'🟢 running' if w['state'] == 'running' else '🔴 ' + w['label']}\n"
        f"• Alerts: {alert_line}"
    )
    tg_send(msg)
    log.info("Heartbeat sent (collected=%d pending=%d watcher=%s)", collected, pending, w["state"])


def _reschedule_activity_job():
    """Daily 00:01 tick: schedule that day's LinkedIn activity jobs. Defined at module
    level (not a lambda) so the persistent jobstore can serialize it; reaches the live
    scheduler via the module global set in start_scheduler()."""
    if _scheduler is not None:
        schedule_daily_activity(_scheduler, TZ)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    # Persist scheduled jobs (calendar reminders!) in the same SQLite file so
    # they survive backend restarts. Daily cron is re-registered explicitly.
    jobstores = {
        "default": SQLAlchemyJobStore(url=DATABASE_URL, tablename="apscheduler_jobs"),
    }
    sched = BackgroundScheduler(timezone=TZ, jobstores=jobstores)
    _scheduler = sched
    sched.add_job(
        daily_scrape_job,
        trigger=CronTrigger(hour=HOUR, minute=MINUTE, timezone=TZ),
        id="daily_scrape",
        replace_existing=True,
    )
    sched.add_job(
        score_and_tailor_job,
        trigger=IntervalTrigger(minutes=SCORE_INTERVAL_MIN),
        id="score_and_tailor",
        replace_existing=True,
    )
    sched.add_job(
        heartbeat_job,
        trigger=CronTrigger(hour=HEARTBEAT_HOUR, minute=0, timezone=TZ),
        id="heartbeat",
        replace_existing=True,
    )
    sched.start()
    log.info("Scheduler started — daily_scrape at %02d:%02d %s", HOUR, MINUTE, TZ)

    drip = threading.Thread(
        target=linkedin_drip_loop, args=(SessionLocal,),
        daemon=True, name="linkedin-drip",
    )
    drip.start()
    log.info("LinkedIn drip thread started")

    schedule_daily_activity(sched, TZ)
    sched.add_job(
        _reschedule_activity_job,
        trigger=CronTrigger(hour=0, minute=1, timezone=TZ),
        id="reschedule_activity", replace_existing=True,
    )

    return sched
