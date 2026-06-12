"""Google Calendar event creation with disguise + APScheduler-driven Telegram reminders.

Naming module `calendar_service` (not `calendar`) so it doesn't shadow stdlib.

Disguise mapping:
  interview     → "{name}'s Birthday 🎂"     (most common — looks normal in feed)
  assessment    → "Dentist Appointment 🦷"
  hr_call       → "Coffee with {name} ☕"
  deadline      → "Car Service 🔧"

Names: random pick from a list of common Hindu Gen-Z boy names. Deterministic
per (job, event_type) — same job + same type → same friend name, so calendar
stays internally consistent if you reschedule.

Three Telegram reminders per event, all scheduled at creation time:
  T-1 day @ 19:00 IST   — "Heads up tomorrow"
  T-day  @ 08:00 IST    — "Today"
  T-30 min              — "In 30 min"
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from database.db import SessionLocal
from database.models import CalendarEvent, Job
from services.telegram import send as tg_send

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "/app/data/credentials.json")
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "/app/data/token.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
]

# Hindu Gen-Z boy names — common, decent, friend-vibe.
BOY_NAMES = [
    "Aarav", "Arjun", "Rohan", "Kabir", "Ishaan", "Vihaan", "Aditya",
    "Yash", "Dev", "Aryan", "Krish", "Atharv", "Veer", "Kartik",
    "Manav", "Pranav", "Harsh", "Aman", "Sahil", "Rishabh", "Daksh",
    "Lakshya", "Reyansh", "Karan", "Shaurya", "Tanmay", "Naman",
    "Ansh", "Vivaan", "Rudra", "Hardik", "Parth", "Raghav", "Nikhil",
]

EVENT_TYPES = ("interview", "assessment", "hr_call", "deadline")


def _pick_name(job_id: int, event_type: str) -> str:
    h = hashlib.sha256(f"{job_id}|{event_type}".encode()).digest()
    return BOY_NAMES[h[0] % len(BOY_NAMES)]


def _disguise(event_type: str, name: str) -> str:
    if event_type == "interview":
        return f"{name}'s Birthday 🎂"
    if event_type == "assessment":
        return "Dentist Appointment 🦷"
    if event_type == "hr_call":
        return f"Coffee with {name} ☕"
    if event_type == "deadline":
        return "Car Service 🔧"
    raise ValueError(f"unknown event_type: {event_type}")


def _load_creds() -> Credentials:
    p = Path(TOKEN_PATH)
    if not p.exists():
        raise FileNotFoundError(f"{TOKEN_PATH} missing — run tools/oauth_bootstrap.py")
    creds = Credentials.from_authorized_user_file(str(p), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        p.write_text(creds.to_json())
    return creds


# ---------- Telegram alert callbacks (run by APScheduler) ----------

def _alert_t_minus_1day(job_id: int, event_id: int, real_summary: str, when_str: str):
    tg_send(
        f"📅 Tomorrow: {real_summary}\n"
        f"Time: {when_str}\n\n"
        f"(In your calendar this is disguised — see the event description for full details.)"
    )


def _alert_t_minus_morning(job_id: int, event_id: int, real_summary: str, when_str: str):
    tg_send(
        f"☀️ Today: {real_summary}\n"
        f"Time: {when_str}\n\n"
        f"Get ready. Detailed brief is in your inbox."
    )


def _alert_t_minus_30(job_id: int, event_id: int, real_summary: str, when_str: str):
    tg_send(
        f"⏰ In 30 minutes: {real_summary}\n"
        f"Time: {when_str}"
    )


def _schedule_reminders(scheduler, event_row: CalendarEvent, job: Job, event_type: str,
                       event_dt_ist: datetime) -> None:
    """Schedule 3 Telegram reminders. event_dt_ist is timezone-aware (IST)."""
    real_summary = f"{job.title} @ {job.company} ({event_type.replace('_', ' ')})"
    when_str = event_dt_ist.strftime("%a %b %d, %I:%M %p IST")
    args = [job.id, event_row.id, real_summary, when_str]

    now = datetime.now(IST)

    t_minus_1d = (event_dt_ist - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    t_minus_morning = event_dt_ist.replace(hour=8, minute=0, second=0, microsecond=0)
    t_minus_30 = event_dt_ist - timedelta(minutes=30)

    # Only schedule reminders that haven't already passed.
    for label, fire_at, fn in [
        ("1day", t_minus_1d, _alert_t_minus_1day),
        ("morning", t_minus_morning, _alert_t_minus_morning),
        ("30min", t_minus_30, _alert_t_minus_30),
    ]:
        if fire_at <= now:
            log.info("Skipping past reminder %s for event %d (would fire at %s)",
                     label, event_row.id, fire_at)
            continue
        scheduler.add_job(
            fn, trigger="date", run_date=fire_at, args=args,
            id=f"reminder-{event_row.id}-{label}",
            replace_existing=True,
        )
        log.info("Scheduled reminder %s for event %d at %s", label, event_row.id, fire_at)


# ---------- Public: create event from dashboard ----------

def create_event(scheduler, job: Job, event_type: str, event_dt_ist: datetime,
                 notes: str | None = None) -> CalendarEvent:
    """Create one-off (non-recurring) Google Calendar event with disguised name,
    persist a CalendarEvent row, and schedule 3 Telegram reminders."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of {EVENT_TYPES}")
    if event_dt_ist.tzinfo is None:
        event_dt_ist = event_dt_ist.replace(tzinfo=IST)

    name = _pick_name(job.id, event_type)
    disguised = _disguise(event_type, name)

    real_details = (
        f"{job.title} @ {job.company}\n"
        f"Type: {event_type.replace('_', ' ').title()}\n"
        f"Apply URL: {job.apply_url or '(none)'}\n"
    )
    if notes:
        real_details += f"\nNotes: {notes}"

    creds = _load_creds()
    cal = build("calendar", "v3", credentials=creds, cache_discovery=False)

    end_dt = event_dt_ist + timedelta(hours=1)
    body = {
        "summary": disguised,
        "description": real_details,  # real info hidden in description
        "start": {"dateTime": event_dt_ist.isoformat(), "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": end_dt.isoformat(),       "timeZone": "Asia/Kolkata"},
        # No 'recurrence' field — Google defaults to single-occurrence.
        "reminders": {"useDefault": False, "overrides": []},  # we drive alerts via Telegram
    }
    created = cal.events().insert(calendarId="primary", body=body).execute()
    google_event_id = created.get("id")
    log.info("Created Google Calendar event %s for job %d", google_event_id, job.id)

    # Persist
    db = SessionLocal()
    try:
        row = CalendarEvent(
            job_id=job.id,
            disguised_name=disguised,
            real_details=real_details,
            event_time=event_dt_ist.astimezone(IST).replace(tzinfo=None),  # naive UTC-ish for SQLite
            google_event_id=google_event_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        _schedule_reminders(scheduler, row, job, event_type, event_dt_ist)
        return row
    finally:
        db.close()
