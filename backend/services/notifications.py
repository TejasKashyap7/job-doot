"""In-app notification centre (the bell). Spec: .claude/specs/notifications/approach.md

user_id=None → system event (admins see it); user_id=N → that user's own event.
Writers must never break the caller: every public writer swallows its own errors.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import or_

from database.db import SessionLocal
from database.models import Notification

log = logging.getLogger(__name__)

KEEP_PER_AUDIENCE = 200
APPLIER_DIR = Path(os.getenv("APPLIER_DATA_DIR", "/app/data/applier"))
OWNER_USER_ID = int(os.getenv("SUMMARY_USER_ID", "1"))


# ---------- write ----------

def notify(user_id: int | None, key: str, level: str, title: str,
           detail: str = "", fix: str = "", action_url: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(Notification(user_id=user_id, key=key, level=level, title=title[:300],
                            detail=detail or None, fix=fix or None, action_url=action_url))
        db.flush()
        # prune: keep the newest KEEP_PER_AUDIENCE for this audience
        q = db.query(Notification.id).filter(
            Notification.user_id.is_(None) if user_id is None else Notification.user_id == user_id)
        old = [r.id for r in q.order_by(Notification.id.desc()).offset(KEEP_PER_AUDIENCE).all()]
        if old:
            db.query(Notification).filter(Notification.id.in_(old)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("notify failed (%s)", key)
    finally:
        db.close()


# ---------- read (per viewer) ----------

def _visible(q, user):
    if user.is_admin:
        return q.filter(or_(Notification.user_id.is_(None), Notification.user_id == user.id))
    return q.filter(Notification.user_id == user.id)


def unread_count(user) -> int:
    if not user:
        return 0
    db = SessionLocal()
    try:
        return _visible(db.query(Notification), user).filter(Notification.read_at.is_(None)).count()
    except Exception:
        return 0
    finally:
        db.close()


def list_for(db, user, limit: int = 100) -> list[Notification]:
    return (_visible(db.query(Notification), user)
            .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).all())


def mark_all_read(db, user) -> None:
    _visible(db.query(Notification), user).filter(Notification.read_at.is_(None)) \
        .update({Notification.read_at: datetime.utcnow()}, synchronize_session=False)
    db.commit()


def clear_all(db, user) -> None:
    _visible(db.query(Notification), user).delete(synchronize_session=False)
    db.commit()


# ---------- applier watcher (scheduler job, every 5 min) ----------
# The applier runs on the Pi host (~/job-doot-applier) and is NOT modified; we read its
# mounted data dir and turn new rows / pause-flag flips into notifications.

_SCRIPT = ("A fixed script (not the AI) was deciding where to click. Haiku never saw the whole "
           "page — it only got the boxes the script picked — so nothing could notice what was "
           "really on the screen and react. ")
_REASONS = {
    "offsite_no_submit_button": _SCRIPT + "Here the script took the site's job-search bar for the "
        "application form, never pressed the 'Apply' button to open the real form, and then "
        "couldn't find a Submit button.",
    "offsite_stuck": _SCRIPT + "The company form refused the answers (something required was "
        "missing or in the wrong format) and the script could not see what the form wanted.",
    "stuck": _SCRIPT + "The LinkedIn form would not go to the next page — some answer was "
        "missing or not accepted — and the script couldn't tell which one.",
    "too_many_steps": _SCRIPT + "The form kept going past the script's page limit, so it stopped.",
    "no_primary_button": _SCRIPT + "It couldn't find the Next / Submit button in the form.",
    "offsite_too_many_pages": _SCRIPT + "The company site kept going past the script's page limit.",
    "brain": "Claude (the AI that answers the form questions) returned an error, so the "
             "application was stopped.",
    "site": "Haiku looked at the page and gave up. In its own words:",
    "crash": "The applier program itself crashed on this job (a bug, not the website).",
    "modal_missing": "The LinkedIn Easy Apply window didn't open.",
}


def _human_reason(detail: str) -> tuple[str, str | None]:
    """'offsite_stuck:msg | url' -> (plain-language explanation, url)"""
    detail = detail or ""
    url = None
    if " | " in detail:
        detail, url = detail.rsplit(" | ", 1)
    code, _, extra = detail.partition(":")
    code, extra = code.strip(), extra.strip()
    text = _REASONS.get(code, code or "unknown error")
    if extra:
        if "weekly limit" in extra or "429" in extra:
            extra = "Claude's weekly usage limit was reached"
        if code == "site":
            text += f" \u201c{extra[:600]}\u201d"
        elif code not in ("offsite_stuck", "stuck"):   # those raw messages add nothing
            text += f" ({extra[:200]})"
    return text, (url if url and url.startswith("http") else None)


def _state_path() -> Path:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/jobs.db")
    return Path(db_url.split("///", 1)[-1]).parent / "notify_state.json"


def _load_state() -> dict | None:
    try:
        return json.loads(_state_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_state(s: dict) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s))


def _where(t: str | None, c: str | None) -> str:
    return " @ ".join(x for x in (t, c) if x) or "a job"


def watch_applier() -> None:
    try:
        _watch_applier()
    except Exception:
        log.exception("applier watcher failed")


def _watch_applier() -> None:
    pause_file = APPLIER_DIR / "PAUSED"
    paused = pause_file.exists()
    reason = (pause_file.read_text().strip()[:200] or "paused") if paused else ""
    rows, max_id, recent_fail = [], 0, []
    db_path = APPLIER_DIR / "applier.db"
    if db_path.exists():
        c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='attempts'").fetchone():
                max_id = c.execute("SELECT coalesce(max(id),0) FROM attempts").fetchone()[0]
                state = _load_state()
                since = state["last_attempt_id"] if state else max_id
                rows = c.execute(
                    "SELECT id, status, detail, title, company, url FROM attempts "
                    "WHERE id > ? ORDER BY id", (since,)).fetchall()
                recent_fail = c.execute(
                    "SELECT detail, title, company FROM attempts WHERE status='failed' "
                    "ORDER BY id DESC LIMIT 3").fetchall()
        finally:
            c.close()

    state = _load_state()
    first_run = state is None
    was_paused = bool(state and state.get("paused"))

    if not first_run:
        for _id, st, detail, title, company, url in rows:
            detail = detail or ""
            if st == "failed":
                why, link = _human_reason(detail)
                notify(OWNER_USER_ID, "applier_failed", "warning",
                       f"Couldn't apply: {_where(title, company)}", detail=f"What happened: {why}",
                       action_url=link or url)
            elif detail.startswith("needs_human:"):
                notify(OWNER_USER_ID, "applier_needs_you", "warning",
                       f"Needs you: {_where(title, company)}",
                       detail=detail.split(":", 1)[1].strip()[:400], action_url=url)

    if paused and (first_run or not was_paused):
        reasons = [_human_reason(d)[0] for d, t, co in recent_fail]
        lines = [f"• {_where(t, co)}" for d, t, co in recent_fail]
        # same explanation for every job? say it once
        if reasons and len(set(reasons)) == 1:
            lines.append(f"\nWhat happened: {reasons[0]}")
        else:
            lines = [f"{l} — {r}" for l, r in zip(lines, reasons)]
        notify(OWNER_USER_ID, "applier_paused", "error", f"Applier paused: {reason}",
               detail=("Last failures:\n" + "\n".join(lines)) if lines else "",
               fix="It won't apply to anything until resumed. On the Pi: "
                   "cd ~/job-doot-applier && python -m applier.run resume")
    elif was_paused and not paused:
        notify(OWNER_USER_ID, "applier_resumed", "success", "Applier resumed",
               detail="The pause flag was cleared; applying continues at the next slot.")

    _save_state({"last_attempt_id": max_id, "paused": paused})
