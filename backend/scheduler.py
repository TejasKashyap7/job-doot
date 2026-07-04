import os
import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from database.db import SessionLocal, DATABASE_URL
from services.ingest import load_csv
from services.scraper import scrape_naukri, linkedin_drip_loop, schedule_daily_activity
from agents.scorer import score_pending
from agents.tailor_loop import tailor_pending

log = logging.getLogger(__name__)

TZ = os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata")
HOUR = int(os.getenv("SCRAPE_HOUR", "6"))
MINUTE = int(os.getenv("SCRAPE_MINUTE", "0"))
CSV_PATH = os.getenv("JOBS_CSV_PATH", "/app/dummy_jobs.csv")

# Module-level handle so jobs saved in the persistent (SQLAlchemy) jobstore can reach
# the running scheduler without a lambda/closure — APScheduler must pickle every job
# it persists, and lambdas/closures are not picklable. Set in start_scheduler().
_scheduler: BackgroundScheduler | None = None


def daily_scrape_job():
    """6am IST: scrape Naukri API and ingest new jobs."""
    log.info("Daily scrape tick — running Naukri batch")
    db = SessionLocal()
    try:
        ingest_result = scrape_naukri(db)
        log.info("Daily ingest result: %s", ingest_result)

        if ingest_result.get("inserted", 0) > 0:
            score_result = score_pending(db)
            log.info("Daily score result: %s", score_result)

            tailor_result = tailor_pending(db)
            log.info("Daily tailor result: %s", tailor_result)
    finally:
        db.close()


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
